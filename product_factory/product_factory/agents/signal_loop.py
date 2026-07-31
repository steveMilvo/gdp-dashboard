"""Agent 7 — Signal Loop.

Without this the system is a one-shot generator, not a factory. It ingests
engagement, landing-page conversion, checkout conversion, refunds and support
themes; attributes revenue back to the originating pain signal; then promotes
high performers into new offer candidates and demotes dead ones.

The ranking metric is **realised revenue per content piece**, not gross
revenue. A signal that made $400 from two pieces is a better bet than one that
made $600 from twenty — the first one scales, the second one is already tapped.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..attribution import revenue_by_signal
from ..llm import client as llm
from ..models import (
    ContentPiece,
    FeedbackEvent,
    NegativeExample,
    Order,
    OrderStatus,
    PainSignal,
    Publication,
    ValidationRun,
    WeeklyReport,
    utcnow,
)

log = logging.getLogger("product_factory.agent7")

PATTERNS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "evidence": {"type": "string"},
                    "action": {"type": "string"},
                },
                "required": ["pattern", "evidence", "action"],
                "additionalProperties": False,
            },
        },
        "narrative": {"type": "string"},
    },
    "required": ["patterns", "narrative"],
    "additionalProperties": False,
}


@dataclass
class LoopResult:
    report_id: str
    rankings: list[dict[str, Any]] = field(default_factory=list)
    promoted: list[str] = field(default_factory=list)
    demoted: list[str] = field(default_factory=list)
    patterns: list[dict[str, Any]] = field(default_factory=list)


def ingest_engagement(
    session: Session,
    *,
    publication_id: str,
    impressions: int = 0,
    engagements: int = 0,
    clicks: int = 0,
) -> None:
    publication = session.get(Publication, publication_id)
    if publication is None:
        raise KeyError(f"no such publication {publication_id!r}")
    publication.impressions = impressions
    publication.engagements = engagements
    publication.clicks = clicks
    session.add(
        FeedbackEvent(
            kind="content.engagement",
            content_piece_id=publication.content_piece_id,
            value=float(engagements),
            payload={
                "publication_id": publication_id,
                "impressions": impressions,
                "clicks": clicks,
            },
        )
    )
    session.flush()


def ingest_support_theme(
    session: Session, *, order_id: str | None, theme: str, detail: str = ""
) -> None:
    order = session.get(Order, order_id) if order_id else None
    session.add(
        FeedbackEvent(
            kind="support.theme",
            order_id=order_id,
            listing_id=order.listing_id if order else None,
            content_piece_id=order.attributed_content_piece_id if order else None,
            payload={"theme": theme, "detail": detail},
        )
    )
    session.flush()


def run_weekly(
    session: Session,
    *,
    niche_id: str,
    period_days: int = 7,
    promote_top: int = 3,
    demote_after_pieces: int = 4,
    run_id: str | None = None,
    step_name: str | None = None,
) -> LoopResult:
    end = utcnow()
    start = end - dt.timedelta(days=period_days)

    rows = revenue_by_signal(session, niche_id)
    engagement = _engagement_by_signal(session, niche_id)

    rankings: list[dict[str, Any]] = []
    for row in rows:
        pieces = int(row["content_pieces"] or 0)
        gross = int(row["gross_cents"] or 0)
        refunded = int(row["refunded_cents"] or 0)
        net = gross - refunded
        stats = engagement.get(row["pain_signal_id"], {})
        rankings.append(
            {
                "pain_signal_id": row["pain_signal_id"],
                "quote": row["pain_quote"],
                "problem": row["pain_problem"],
                "recurrence": row["recurrence"],
                "content_pieces": pieces,
                "orders": int(row["orders"] or 0),
                "gross_cents": gross,
                "refunded_cents": refunded,
                "net_cents": net,
                # The ranking metric. Zero pieces means untested, not failed —
                # it sorts below tested winners but above tested losers.
                "revenue_per_piece_cents": round(net / pieces, 2) if pieces else None,
                "impressions": stats.get("impressions", 0),
                "engagements": stats.get("engagements", 0),
                "clicks": stats.get("clicks", 0),
                "click_through": round(
                    stats.get("clicks", 0) / stats["impressions"], 4
                )
                if stats.get("impressions")
                else None,
            }
        )

    rankings.sort(
        key=lambda r: (
            r["revenue_per_piece_cents"] is not None,
            r["revenue_per_piece_cents"] or 0,
            r["engagements"],
        ),
        reverse=True,
    )

    promoted = [
        r["pain_signal_id"]
        for r in rankings
        if (r["revenue_per_piece_cents"] or 0) > 0
    ][:promote_top]

    demoted = [
        r["pain_signal_id"]
        for r in rankings
        if r["content_pieces"] >= demote_after_pieces
        and r["net_cents"] <= 0
        and r["clicks"] == 0
    ]

    _apply_promotions(session, promoted, demoted, niche_id)

    patterns_payload = _content_patterns(
        session,
        niche_id=niche_id,
        rankings=rankings,
        run_id=run_id,
        step_name=step_name,
    )

    report = WeeklyReport(
        niche_id=niche_id,
        period_start=start,
        period_end=end,
        rankings=rankings,
        promoted=promoted,
        demoted=demoted,
        content_patterns=patterns_payload["patterns"],
        narrative=patterns_payload["narrative"],
    )
    session.add(report)
    session.flush()

    return LoopResult(
        report_id=report.id,
        rankings=rankings,
        promoted=promoted,
        demoted=demoted,
        patterns=patterns_payload["patterns"],
    )


def _apply_promotions(
    session: Session, promoted: list[str], demoted: list[str], niche_id: str
) -> None:
    """Promotion raises a signal's score so Agent 2 clusters around it next
    cycle; demotion records a negative example so it stops being proposed."""
    for signal_id in promoted:
        signal = session.get(PainSignal, signal_id)
        if signal is not None:
            signal.score = round(signal.score * 1.5, 3)

    for signal_id in demoted:
        signal = session.get(PainSignal, signal_id)
        if signal is None:
            continue
        signal.score = round(signal.score * 0.4, 3)
        session.add(
            NegativeExample(
                niche_id=niche_id,
                promise=signal.normalised,
                format=None,
                reason=(
                    "signal loop: content published against this signal produced "
                    "no clicks and no net revenue"
                ),
                source="signal_loop",
            )
        )
    session.flush()


def _engagement_by_signal(session: Session, niche_id: str) -> dict[str, dict[str, int]]:
    rows = session.execute(
        select(
            ContentPiece.pain_signal_id,
            func.coalesce(func.sum(Publication.impressions), 0),
            func.coalesce(func.sum(Publication.engagements), 0),
            func.coalesce(func.sum(Publication.clicks), 0),
        )
        .select_from(ContentPiece)
        .join(Publication, Publication.content_piece_id == ContentPiece.id)
        .join(PainSignal, PainSignal.id == ContentPiece.pain_signal_id)
        .where(PainSignal.niche_id == niche_id)
        .group_by(ContentPiece.pain_signal_id)
    ).all()
    return {
        row[0]: {"impressions": row[1], "engagements": row[2], "clicks": row[3]}
        for row in rows
    }


def _content_patterns(
    session: Session,
    *,
    niche_id: str,
    rankings: list[dict[str, Any]],
    run_id: str | None,
    step_name: str | None,
) -> dict[str, Any]:
    winners = [r for r in rankings if (r["revenue_per_piece_cents"] or 0) > 0][:5]
    losers = [
        r
        for r in rankings
        if r["content_pieces"] > 0 and not (r["revenue_per_piece_cents"] or 0)
    ][:5]

    def _hooks(signal_ids: list[str]) -> str:
        if not signal_ids:
            return "(none)"
        rows = session.scalars(
            select(ContentPiece)
            .where(ContentPiece.pain_signal_id.in_(signal_ids))
            .limit(20)
        ).all()
        return "\n".join(f"- [{p.platform}] {p.hook}" for p in rows) or "(none)"

    return llm.complete_json(
        prompt_name="signal_loop_patterns",
        variables={
            "winning_hooks": _hooks([r["pain_signal_id"] for r in winners]),
            "losing_hooks": _hooks([r["pain_signal_id"] for r in losers]),
            "summary": "\n".join(
                f"- {r['problem'][:120]} | pieces={r['content_pieces']} "
                f"| net={r['net_cents']}c | clicks={r['clicks']}"
                for r in rankings[:12]
            ),
        },
        schema=PATTERNS_SCHEMA,
        agent="signal_loop",
        run_id=run_id,
        step_name=step_name,
        session=session,
    )


def funnel_summary(session: Session, niche_id: str) -> dict[str, Any]:
    """Conversion at each stage, for the operator console."""
    validations = session.execute(
        select(
            func.coalesce(func.sum(ValidationRun.views), 0),
            func.coalesce(func.sum(ValidationRun.signups), 0),
        )
    ).one()
    impressions, clicks = session.execute(
        select(
            func.coalesce(func.sum(Publication.impressions), 0),
            func.coalesce(func.sum(Publication.clicks), 0),
        )
    ).one()
    paid, refunded = session.execute(
        select(
            func.count(Order.id).filter(
                Order.status.in_(
                    [OrderStatus.PAID.value, OrderStatus.DELIVERED.value]
                )
            ),
            func.count(Order.id).filter(Order.status == OrderStatus.REFUNDED.value),
        )
    ).one()
    return {
        "content_impressions": impressions,
        "content_clicks": clicks,
        "landing_views": validations[0],
        "landing_signups": validations[1],
        "orders_paid": paid,
        "orders_refunded": refunded,
        "refund_rate": round(refunded / paid, 4) if paid else None,
    }
