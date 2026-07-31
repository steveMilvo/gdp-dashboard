"""Agent 1 — Demand Miner.

Scrapes public complaint/desire signal and ranks it. The one rule that makes
this agent worth having: **recurrence gates everything**. A single articulate
complaint is noise no matter how well phrased, so a candidate signal must
appear at least `min_recurrence` times across at least `min_sources`
independent source kinds before it is marked verified.

Extraction is per-source-document and structured: the model returns the
verbatim quote plus a normalised restatement. We fingerprint the *normalised*
form for dedup and keep the *verbatim* quote for citation, because customer
copy has to quote a real human, not a paraphrase.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ids import fingerprint
from ..llm import client as llm
from ..models import (
    Niche,
    PainSignal,
    SignalOccurrence,
    SourceDocument,
    WTPTier,
)
from ..sources.adapters import default_sources
from ..sources.base import Fetcher, RawItem, Source, dedupe

log = logging.getLogger("product_factory.agent1")

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {
                        "type": "string",
                        "description": "Verbatim span from the source text. Must "
                        "appear in the source; do not paraphrase.",
                    },
                    "normalised": {
                        "type": "string",
                        "description": "The underlying problem in one neutral "
                        "sentence, phrased so two people describing the same "
                        "problem differently normalise to the same text.",
                    },
                    "wtp_tier": {
                        "type": "string",
                        "enum": [t.value for t in WTPTier],
                    },
                    "wtp_rationale": {"type": "string"},
                },
                "required": ["quote", "normalised", "wtp_tier", "wtp_rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["signals"],
    "additionalProperties": False,
}

_TIER_WEIGHT = {
    WTPTier.FREE.value: 0.25,
    WTPTier.LOW.value: 1.0,
    WTPTier.MID.value: 2.0,
    WTPTier.HIGH.value: 3.5,
}


@dataclass
class MiningResult:
    niche_id: str
    documents_captured: int
    candidates: int
    verified: int
    signal_ids: list[str]


def mine(
    session: Session,
    *,
    niche_id: str,
    limit_per_source: int = 60,
    min_recurrence: int = 3,
    min_sources: int = 2,
    sources: Iterable[Source] | None = None,
    source_config: dict[str, Any] | None = None,
    run_id: str | None = None,
    step_name: str | None = None,
) -> MiningResult:
    niche = session.get(Niche, niche_id)
    if niche is None:
        raise KeyError(f"no such niche {niche_id!r}")

    queries = [niche.hypothesis, *(niche.seed_keywords or [])]
    source_list = list(sources) if sources is not None else default_sources(
        source_config
    )

    raw: list[RawItem] = []
    with Fetcher() as fetcher:
        for source in source_list:
            for query in queries:
                try:
                    raw.extend(
                        source.collect(query, limit=limit_per_source, fetcher=fetcher)
                    )
                except Exception:  # noqa: BLE001 - one hostile host must not
                    # sink the run; the others still produce signal.
                    log.warning(
                        "source %s failed for query %r", source.kind, query,
                        exc_info=True,
                    )
    raw = dedupe(raw)
    log.info("captured %s unique source rows for niche %s", len(raw), niche_id)

    documents = _persist_documents(session, raw)

    # normalised fingerprint -> occurrences
    buckets: dict[str, list[tuple[SourceDocument, dict[str, Any]]]] = defaultdict(list)
    for doc in documents:
        for signal in _extract(
            doc, run_id=run_id, step_name=step_name, session=session
        ):
            key = fingerprint(signal["normalised"])
            buckets[key].append((doc, signal))

    signal_ids: list[str] = []
    verified_count = 0
    for key, entries in buckets.items():
        occurrences = len(entries)
        kinds = {doc.source_kind for doc, _ in entries}
        verified = occurrences >= min_recurrence and len(kinds) >= min_sources

        signal = session.scalar(
            select(PainSignal).where(
                PainSignal.niche_id == niche_id, PainSignal.fingerprint == key
            )
        )
        best = max(entries, key=lambda e: _TIER_WEIGHT.get(e[1]["wtp_tier"], 0.0))
        if signal is None:
            signal = PainSignal(
                niche_id=niche_id,
                quote=best[1]["quote"],
                normalised=best[1]["normalised"],
                fingerprint=key,
            )
            session.add(signal)
            session.flush()

        signal.recurrence_count = occurrences
        signal.independent_sources = len(kinds)
        signal.wtp_tier = best[1]["wtp_tier"]
        signal.wtp_rationale = best[1].get("wtp_rationale")
        signal.verified = verified
        signal.score = _score(occurrences, len(kinds), signal.wtp_tier)

        for doc, entry in entries:
            exists = session.scalar(
                select(SignalOccurrence).where(
                    SignalOccurrence.pain_signal_id == signal.id,
                    SignalOccurrence.source_document_id == doc.id,
                )
            )
            if exists is None:
                session.add(
                    SignalOccurrence(
                        pain_signal_id=signal.id,
                        source_document_id=doc.id,
                        excerpt=entry["quote"],
                    )
                )
        signal_ids.append(signal.id)
        verified_count += int(verified)

    session.flush()
    return MiningResult(
        niche_id=niche_id,
        documents_captured=len(documents),
        candidates=len(buckets),
        verified=verified_count,
        signal_ids=signal_ids,
    )


def _persist_documents(
    session: Session, items: Iterable[RawItem]
) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    for item in items:
        existing = session.scalar(
            select(SourceDocument).where(
                SourceDocument.content_hash == item.content_hash
            )
        )
        if existing is not None:
            docs.append(existing)
            continue
        doc = SourceDocument(
            source_kind=item.source_kind,
            url=item.url,
            title=item.title,
            author=item.author,
            raw_text=item.text,
            meta=item.meta,
            content_hash=item.content_hash,
        )
        session.add(doc)
        session.flush()
        docs.append(doc)
    return docs


def _extract(
    doc: SourceDocument,
    *,
    run_id: str | None,
    step_name: str | None,
    session: Session,
) -> list[dict[str, Any]]:
    try:
        payload = llm.complete_json(
            prompt_name="demand_miner_extract",
            variables={
                "source_kind": doc.source_kind,
                "url": doc.url,
                "text": doc.raw_text[:6000],
            },
            schema=EXTRACTION_SCHEMA,
            agent="demand_miner",
            run_id=run_id,
            step_name=step_name,
            session=session,
        )
    except Exception:  # noqa: BLE001
        log.warning("extraction failed for %s", doc.url, exc_info=True)
        return []

    out = []
    for signal in payload.get("signals", []):
        quote = (signal.get("quote") or "").strip()
        normalised = (signal.get("normalised") or "").strip()
        if len(quote) < 15 or len(normalised) < 10:
            continue
        # The quote must actually be in the source. Every downstream claim
        # traces to this row, so a hallucinated quote is a compliance problem,
        # not a quality one.
        if _normalise_ws(quote) not in _normalise_ws(doc.raw_text):
            log.info("dropping non-verbatim quote from %s", doc.url)
            continue
        out.append(
            {
                "quote": quote,
                "normalised": normalised,
                "wtp_tier": signal.get("wtp_tier", WTPTier.LOW.value),
                "wtp_rationale": signal.get("wtp_rationale", ""),
            }
        )
    return out


def _normalise_ws(text: str) -> str:
    return " ".join(text.split()).lower()


def _score(occurrences: int, source_kinds: int, tier: str) -> float:
    """Recurrence dominates, source diversity multiplies, willingness-to-pay
    breaks ties. A signal seen 20 times in one subreddit should rank below one
    seen 6 times across three surfaces."""
    return round(
        occurrences * (1.0 + 0.5 * (source_kinds - 1)) * _TIER_WEIGHT.get(tier, 1.0),
        3,
    )


def verified_signals(session: Session, niche_id: str, limit: int = 50) -> list[PainSignal]:
    return list(
        session.scalars(
            select(PainSignal)
            .where(PainSignal.niche_id == niche_id, PainSignal.verified.is_(True))
            .order_by(PainSignal.score.desc())
            .limit(limit)
        ).all()
    )
