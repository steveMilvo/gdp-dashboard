"""Agent 2 — Offer Synthesiser.

Clusters verified pain signals into candidate offers, each with a promise, a
target buyer, a format, a price, and three named competitors with their prices.

The negative-example store matters more than it looks. Without it, the same
plausible-sounding dead end gets re-proposed every time the niche is re-mined,
and the operator burns their attention rejecting it again. Rejections are
fed back into the prompt as explicit "do not propose these" context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..llm import client as llm
from ..models import (
    ClusterMember,
    Competitor,
    NegativeExample,
    OfferCandidate,
    PainSignal,
    ProductFormat,
    SignalCluster,
)
from .demand_miner import verified_signals

log = logging.getLogger("product_factory.agent2")

SYNTHESIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "clusters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "summary": {"type": "string"},
                    "signal_ids": {"type": "array", "items": {"type": "string"}},
                    "offer": {
                        "type": "object",
                        "properties": {
                            "promise": {
                                "type": "string",
                                "description": "One line. What the buyer can do "
                                "after buying that they could not do before.",
                            },
                            "target_buyer": {"type": "string"},
                            "format": {
                                "type": "string",
                                "enum": [f.value for f in ProductFormat],
                            },
                            "price_cents": {"type": "integer"},
                            "rationale": {"type": "string"},
                            "competitors": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "url": {"type": "string"},
                                        "price_cents": {"type": "integer"},
                                        "positioning": {"type": "string"},
                                    },
                                    "required": [
                                        "name",
                                        "url",
                                        "price_cents",
                                        "positioning",
                                    ],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": [
                            "promise",
                            "target_buyer",
                            "format",
                            "price_cents",
                            "rationale",
                            "competitors",
                        ],
                        "additionalProperties": False,
                    },
                },
                "required": ["label", "summary", "signal_ids", "offer"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clusters"],
    "additionalProperties": False,
}


@dataclass
class SynthesisResult:
    candidate_ids: list[str]
    cluster_ids: list[str]


def synthesise(
    session: Session,
    *,
    niche_id: str,
    max_candidates: int = 5,
    run_id: str | None = None,
    step_name: str | None = None,
) -> SynthesisResult:
    signals = verified_signals(session, niche_id, limit=60)
    if not signals:
        raise ValueError(
            "no recurrence-verified signals for this niche — run the demand "
            "miner first, or lower min_recurrence if the niche is genuinely thin"
        )

    payload = llm.complete_json(
        prompt_name="offer_synthesiser",
        variables={
            "max_candidates": max_candidates,
            "signals": _render_signals(signals),
            "negative_examples": _render_negatives(session, niche_id),
            "currency": "AUD",
        },
        schema=SYNTHESIS_SCHEMA,
        agent="offer_synthesiser",
        run_id=run_id,
        step_name=step_name,
        session=session,
    )

    valid_ids = {s.id for s in signals}
    candidate_ids: list[str] = []
    cluster_ids: list[str] = []

    for entry in payload.get("clusters", [])[:max_candidates]:
        members = [sid for sid in entry.get("signal_ids", []) if sid in valid_ids]
        if not members:
            log.info("skipping cluster %r — no valid signal ids", entry.get("label"))
            continue

        cluster = SignalCluster(
            niche_id=niche_id,
            label=entry["label"],
            summary=entry.get("summary"),
        )
        session.add(cluster)
        session.flush()
        for sid in members:
            session.add(ClusterMember(cluster_id=cluster.id, pain_signal_id=sid))

        offer = entry["offer"]
        candidate = OfferCandidate(
            niche_id=niche_id,
            cluster_id=cluster.id,
            promise=offer["promise"],
            target_buyer=offer["target_buyer"],
            format=offer["format"],
            price_cents=int(offer["price_cents"]),
            rationale=offer.get("rationale"),
        )
        session.add(candidate)
        session.flush()

        for comp in offer.get("competitors", [])[:3]:
            session.add(
                Competitor(
                    offer_candidate_id=candidate.id,
                    name=comp["name"],
                    url=comp.get("url"),
                    price_cents=comp.get("price_cents"),
                    positioning=comp.get("positioning"),
                )
            )
        candidate_ids.append(candidate.id)
        cluster_ids.append(cluster.id)

    session.flush()
    return SynthesisResult(candidate_ids=candidate_ids, cluster_ids=cluster_ids)


def select_candidate(session: Session, candidate_id: str) -> OfferCandidate:
    candidate = session.get(OfferCandidate, candidate_id)
    if candidate is None:
        raise KeyError(f"no such offer candidate {candidate_id!r}")
    candidate.selected = True
    session.flush()
    return candidate


def reject_all(
    session: Session, *, niche_id: str, candidate_ids: list[str], reason: str
) -> int:
    """Feed rejections into the negative-example store so Agent 2 stops
    proposing them."""
    count = 0
    for candidate_id in candidate_ids:
        candidate = session.get(OfferCandidate, candidate_id)
        if candidate is None:
            continue
        session.add(
            NegativeExample(
                niche_id=niche_id,
                promise=candidate.promise,
                format=candidate.format,
                reason=reason,
            )
        )
        count += 1
    session.flush()
    return count


def _render_signals(signals: list[PainSignal]) -> str:
    return "\n".join(
        f"- id={s.id} | seen {s.recurrence_count}x across {s.independent_sources} "
        f"source kinds | willingness-to-pay: {s.wtp_tier}\n"
        f'  problem: {s.normalised}\n  verbatim: "{s.quote}"'
        for s in signals
    )


def _render_negatives(session: Session, niche_id: str) -> str:
    rows = session.scalars(
        select(NegativeExample)
        .where(NegativeExample.niche_id == niche_id)
        .order_by(NegativeExample.created_at.desc())
        .limit(30)
    ).all()
    if not rows:
        return "(none yet)"
    return "\n".join(
        f"- {row.promise} [{row.format}] — rejected because: {row.reason}"
        for row in rows
    )
