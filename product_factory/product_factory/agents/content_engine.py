"""Agent 6 — Content Engine. The load-bearing component.

Two departures from the source material, both deliberate:

1. **Cold start is the default assumption.** The video's economics assume an
   existing audience, where "post consistently" is sufficient. With no
   distribution, posting into the void is not a strategy. So every piece
   carries a `distribution` mode, and the generator is biased toward
   `direct_reply` — answering the *actual threads the signal came from*, at
   the URLs Agent 1 already captured. That is the one distribution channel a
   cold start reliably has: the places where the complaint was made.

2. **The specificity rule is enforced in two stages.** A cheap deterministic
   overlap check kills obviously generic hooks without a model call; a judge
   call then answers the real question — "would this hook make sense for a
   different product in a different niche?" Anything that survives both is
   specific to a complaint someone actually made.

Every piece is anchored to exactly one pain signal. The schema enforces it; so
does this module.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..llm import client as llm
from ..models import (
    ContentPiece,
    PainSignal,
    Product,
    SignalOccurrence,
    SourceDocument,
    utcnow,
)

log = logging.getLogger("product_factory.agent6")

PLATFORMS = ("tiktok", "reels", "shorts", "x", "linkedin", "reddit")

PIECE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "pieces": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "enum": list(PLATFORMS)},
                    "distribution": {
                        "type": "string",
                        "enum": ["direct_reply", "broadcast"],
                        "description": "direct_reply posts into the thread the "
                        "complaint came from; broadcast posts to your own feed.",
                    },
                    "hook": {
                        "type": "string",
                        "description": "First line. Must be unusable for any "
                        "other product in any other niche.",
                    },
                    "body": {"type": "string"},
                    "cta": {"type": "string"},
                    "format_notes": {
                        "type": "string",
                        "description": "Platform-native execution: shot list, "
                        "text-on-screen, thread structure, length.",
                    },
                },
                "required": [
                    "platform",
                    "distribution",
                    "hook",
                    "body",
                    "cta",
                    "format_notes",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["pieces"],
    "additionalProperties": False,
}

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "generic": {
                        "type": "boolean",
                        "description": "True if this hook would make sense for a "
                        "different product in a different niche.",
                    },
                    "score": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["index", "generic", "score", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

# Words that carry no niche information. A hook made mostly of these is
# generic by construction and doesn't need a model call to prove it.
_FILLER = {
    "a", "about", "actually", "all", "an", "and", "are", "as", "at", "be",
    "best", "better", "business", "but", "by", "can", "content", "could",
    "creators", "day", "do", "does", "easy", "entrepreneurs", "every", "fast",
    "for", "free", "from", "get", "getting", "grow", "growth", "guide", "hack",
    "has", "have", "here", "hours", "how", "i", "if", "in", "is", "it", "its",
    "just", "know", "learn", "less", "life", "like", "make", "makes", "making",
    "me", "money", "more", "most", "much", "my", "need", "never", "new", "no",
    "not", "now", "of", "on", "one", "online", "only", "or", "out", "people",
    "power", "quick", "really", "right", "s", "secret", "should", "simple",
    "so", "start", "stop", "system", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "thing", "things", "this",
    "time", "tips", "to", "top", "trick", "try", "up", "use", "using", "very",
    "want", "was", "way", "ways", "we", "what", "when", "why", "will", "with",
    "work", "would", "you", "your",
}

_WORD = re.compile(r"[a-z0-9']+")


@dataclass
class CalendarResult:
    accepted: list[str] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)

    @property
    def rejection_count(self) -> int:
        return len(self.rejected)


def generate_calendar(
    session: Session,
    *,
    niche_id: str,
    product_id: str | None = None,
    target_pieces: int = 30,
    pieces_per_signal: int = 2,
    direct_reply_ratio: float = 0.5,
    run_id: str | None = None,
    step_name: str | None = None,
) -> CalendarResult:
    signals = _signals_for_calendar(session, niche_id, target_pieces, pieces_per_signal)
    if not signals:
        raise ValueError("no verified pain signals to anchor content to")

    product = session.get(Product, product_id) if product_id else None
    result = CalendarResult()

    for signal in signals:
        threads = _threads_for(session, signal.id)
        payload = llm.complete_json(
            prompt_name="content_pieces",
            variables={
                "count": pieces_per_signal,
                "quote": signal.quote,
                "problem": signal.normalised,
                "recurrence": f"{signal.recurrence_count} sightings across "
                f"{signal.independent_sources} independent source kinds",
                "threads": "\n".join(f"- {t}" for t in threads) or "(none captured)",
                "direct_reply_ratio": f"{direct_reply_ratio:.0%}",
                "product_context": (
                    f"{product.name} ({product.format})"
                    if product
                    else "(no product yet — write to the problem only)"
                ),
                "platforms": ", ".join(PLATFORMS),
            },
            schema=PIECE_SCHEMA,
            agent="content_engine",
            run_id=run_id,
            step_name=step_name,
            product_id=product_id,
            session=session,
        )

        candidates = payload.get("pieces", [])[:pieces_per_signal]
        surviving = _apply_specificity_rule(
            candidates,
            signal=signal,
            result=result,
            run_id=run_id,
            step_name=step_name,
            product_id=product_id,
            session=session,
        )

        for piece, score in surviving:
            row = ContentPiece(
                pain_signal_id=signal.id,
                product_id=product_id,
                platform=piece["platform"],
                hook=piece["hook"],
                body=piece["body"],
                cta=piece["cta"],
                format_notes=(
                    f"[{piece['distribution']}] {piece['format_notes']}"
                ),
                specificity_score=score,
            )
            session.add(row)
            session.flush()
            result.accepted.append(row.id)

        if len(result.accepted) >= target_pieces:
            break

    session.flush()
    log.info(
        "content calendar: %s accepted, %s rejected by the specificity rule",
        len(result.accepted),
        result.rejection_count,
    )
    return result


# --------------------------------------------------------------------------- #
# Specificity rule
# --------------------------------------------------------------------------- #


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _FILLER and len(w) > 2}


def local_specificity(hook: str, signal: PainSignal) -> tuple[bool, float, str]:
    """Deterministic pre-filter. Cheap, and it catches the common failure —
    a hook made entirely of marketing filler with no niche vocabulary in it."""
    hook_tokens = _tokens(hook)
    if len(hook_tokens) < 3:
        return False, 0.0, "hook carries almost no niche-specific vocabulary"
    signal_tokens = _tokens(f"{signal.quote} {signal.normalised}")
    overlap = hook_tokens & signal_tokens
    ratio = len(overlap) / max(len(hook_tokens), 1)
    if not overlap:
        return (
            False,
            0.0,
            "hook shares no distinctive vocabulary with the pain signal",
        )
    return True, round(ratio, 3), f"shares {sorted(overlap)[:5]} with the signal"


def _apply_specificity_rule(
    candidates: list[dict[str, Any]],
    *,
    signal: PainSignal,
    result: CalendarResult,
    run_id: str | None,
    step_name: str | None,
    product_id: str | None,
    session: Session,
) -> list[tuple[dict[str, Any], float]]:
    staged: list[tuple[int, dict[str, Any], float]] = []
    for index, piece in enumerate(candidates):
        ok, ratio, reason = local_specificity(piece["hook"], signal)
        if not ok:
            result.rejected.append({"hook": piece["hook"], "reason": reason})
            continue
        staged.append((index, piece, ratio))

    if not staged:
        return []

    verdicts = llm.complete_json(
        prompt_name="content_specificity_judge",
        variables={
            "quote": signal.quote,
            "problem": signal.normalised,
            "hooks": "\n".join(
                f"{i}. {piece['hook']}" for i, (_, piece, _) in enumerate(staged)
            ),
        },
        schema=JUDGE_SCHEMA,
        agent="content_engine.judge",
        run_id=run_id,
        step_name=step_name,
        product_id=product_id,
        session=session,
    )
    by_index = {v["index"]: v for v in verdicts.get("verdicts", [])}

    survivors: list[tuple[dict[str, Any], float]] = []
    for position, (_, piece, ratio) in enumerate(staged):
        verdict = by_index.get(position)
        if verdict is None:
            # No verdict returned — fail closed. An unjudged hook is not an
            # approved hook.
            result.rejected.append(
                {"hook": piece["hook"], "reason": "specificity judge returned no verdict"}
            )
            continue
        if verdict["generic"]:
            result.rejected.append(
                {"hook": piece["hook"], "reason": verdict.get("reason", "generic hook")}
            )
            continue
        survivors.append((piece, round((ratio + float(verdict["score"])) / 2, 3)))
    return survivors


# --------------------------------------------------------------------------- #
# Approval + scheduling
# --------------------------------------------------------------------------- #


def approve_batch(
    session: Session, *, content_piece_ids: list[str], rejected_ids: list[str] | None = None
) -> int:
    rejected = set(rejected_ids or [])
    approved = 0
    for piece_id in content_piece_ids:
        piece = session.get(ContentPiece, piece_id)
        if piece is None:
            continue
        if piece_id in rejected:
            piece.approved = False
            piece.rejected_reason = "rejected by operator at gate 2"
            continue
        piece.approved = True
        approved += 1
    session.flush()
    return approved


def schedule(
    session: Session,
    *,
    content_piece_ids: list[str],
    start: dt.datetime | None = None,
    per_day: int = 3,
    hours: tuple[int, ...] = (8, 13, 19),
) -> int:
    """Spread approved pieces across the calendar. Only approved pieces get a
    slot — Gate 2 is not advisory."""
    start = start or utcnow()
    slot = 0
    scheduled = 0
    for piece_id in content_piece_ids:
        piece = session.get(ContentPiece, piece_id)
        if piece is None or not piece.approved:
            continue
        day, hour_index = divmod(slot, min(per_day, len(hours)))
        piece.scheduled_for = (start + dt.timedelta(days=day)).replace(
            hour=hours[hour_index], minute=0, second=0, microsecond=0
        )
        slot += 1
        scheduled += 1
    session.flush()
    return scheduled


# --------------------------------------------------------------------------- #


def _signals_for_calendar(
    session: Session, niche_id: str, target_pieces: int, pieces_per_signal: int
) -> list[PainSignal]:
    needed = -(-target_pieces // max(pieces_per_signal, 1))
    return list(
        session.scalars(
            select(PainSignal)
            .where(PainSignal.niche_id == niche_id, PainSignal.verified.is_(True))
            .order_by(PainSignal.score.desc())
            # Over-fetch: the specificity rule will kill some, and running out
            # of distinct signals is what forces two pieces onto one signal.
            .limit(needed + 8)
        ).all()
    )


def _threads_for(session: Session, pain_signal_id: str, limit: int = 5) -> list[str]:
    """The URLs the complaint was actually made at. This is the cold-start
    distribution list."""
    rows = session.scalars(
        select(SourceDocument.url)
        .join(
            SignalOccurrence,
            SignalOccurrence.source_document_id == SourceDocument.id,
        )
        .where(SignalOccurrence.pain_signal_id == pain_signal_id)
        .limit(limit)
    ).all()
    return list(rows)
