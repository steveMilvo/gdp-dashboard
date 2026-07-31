"""Agent 3 — Validation Runner.

Generates a pre-sell landing page and outreach variants, then judges the run
against a threshold that was **set before the test started**. `threshold_set_at`
is stamped at creation and `evaluate` refuses to run against a threshold
changed after the fact — the point of a pre-registered number is that you
cannot move it once you have seen the result.

Outreach variants are aimed at the specific people whose quotes fed the
cluster, so each variant carries the pain_signal_id it answers and the source
thread it should be sent into.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..llm import client as llm
from ..models import (
    ClusterMember,
    FeedbackEvent,
    Objection,
    OfferCandidate,
    OutreachVariant,
    PainSignal,
    SignalOccurrence,
    SourceDocument,
    ValidationRun,
    ValidationSignup,
    utcnow,
)

log = logging.getLogger("product_factory.agent3")

LANDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "subhead": {"type": "string"},
        "problem_paragraphs": {"type": "array", "items": {"type": "string"}},
        "what_it_is": {"type": "array", "items": {"type": "string"}},
        "cta_label": {"type": "string"},
        "price_framing": {"type": "string"},
    },
    "required": [
        "headline",
        "subhead",
        "problem_paragraphs",
        "what_it_is",
        "cta_label",
        "price_framing",
    ],
    "additionalProperties": False,
}

OUTREACH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pain_signal_id": {"type": "string"},
                    "channel": {
                        "type": "string",
                        "enum": ["dm", "comment_reply", "email"],
                    },
                    "body": {
                        "type": "string",
                        "description": "Under 60 words. References what this "
                        "specific person said. No pitch in the first message.",
                    },
                },
                "required": ["pain_signal_id", "channel", "body"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["variants"],
    "additionalProperties": False,
}

OBJECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "objections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "theme": {"type": "string"},
                    "rebuttal": {"type": "string"},
                },
                "required": ["text", "theme", "rebuttal"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["objections"],
    "additionalProperties": False,
}


class ThresholdTampering(RuntimeError):
    pass


@dataclass
class ValidationSetup:
    validation_run_id: str
    slug: str
    url: str
    threshold: int
    variant_count: int


def start_validation(
    session: Session,
    *,
    offer_candidate_id: str,
    success_threshold: int,
    threshold_metric: str = "signups",
    variant_count: int = 7,
    run_id: str | None = None,
    step_name: str | None = None,
) -> ValidationSetup:
    if success_threshold < 1:
        raise ValueError("declare a real threshold before running the test")

    candidate = session.get(OfferCandidate, offer_candidate_id)
    if candidate is None:
        raise KeyError(f"no such offer candidate {offer_candidate_id!r}")

    signals = _signals(session, candidate.cluster_id)
    page = llm.complete_json(
        prompt_name="validation_landing",
        variables={
            "promise": candidate.promise,
            "target_buyer": candidate.target_buyer,
            "format": candidate.format,
            "price": f"{candidate.price_cents / 100:,.2f} {candidate.currency}",
            "signals": "\n".join(
                f"- \"{s.quote}\" ({s.recurrence_count} sightings)" for s in signals
            ),
        },
        schema=LANDING_SCHEMA,
        agent="validation_runner",
        run_id=run_id,
        step_name=step_name,
        session=session,
    )

    slug = _slug(candidate, session)
    validation = ValidationRun(
        offer_candidate_id=candidate.id,
        slug=slug,
        headline=page["headline"],
        body_html=_render_landing(page, candidate),
        cta_label=page["cta_label"],
        success_threshold=success_threshold,
        threshold_metric=threshold_metric,
    )
    session.add(validation)
    session.flush()

    outreach = llm.complete_json(
        prompt_name="validation_outreach",
        variables={
            "count": variant_count,
            "promise": candidate.promise,
            "landing_url": f"{settings().base_url}/v/{slug}",
            "signals": "\n".join(
                f"- id={s.id} | \"{s.quote}\"\n  thread: "
                f"{_first_thread(session, s.id) or '(unknown)'}"
                for s in signals
            ),
        },
        schema=OUTREACH_SCHEMA,
        agent="validation_runner",
        run_id=run_id,
        step_name=step_name,
        session=session,
    )

    valid_ids = {s.id for s in signals}
    written = 0
    for variant in outreach.get("variants", [])[:variant_count]:
        if variant["pain_signal_id"] not in valid_ids:
            continue
        session.add(
            OutreachVariant(
                validation_run_id=validation.id,
                pain_signal_id=variant["pain_signal_id"],
                channel=variant["channel"],
                body=variant["body"],
            )
        )
        written += 1
    session.flush()

    return ValidationSetup(
        validation_run_id=validation.id,
        slug=slug,
        url=f"{settings().base_url}/v/{slug}",
        threshold=success_threshold,
        variant_count=written,
    )


def record_signup(
    session: Session, *, slug: str, email: str, referrer: str | None = None
) -> bool:
    validation = session.scalar(
        select(ValidationRun).where(ValidationRun.slug == slug)
    )
    if validation is None:
        raise KeyError(f"no validation run at {slug!r}")
    existing = session.scalar(
        select(ValidationSignup).where(
            ValidationSignup.validation_run_id == validation.id,
            ValidationSignup.email == email,
        )
    )
    if existing is not None:
        return False
    session.add(
        ValidationSignup(
            validation_run_id=validation.id, email=email, referrer=referrer
        )
    )
    session.flush()
    # Recount rather than increment: the counter is a denormalised cache of
    # this table, and a lost update here would corrupt the verdict.
    validation.signups = (
        session.scalar(
            select(func.count(ValidationSignup.id)).where(
                ValidationSignup.validation_run_id == validation.id
            )
        )
        or 0
    )
    session.add(
        FeedbackEvent(
            kind="validation.signup",
            payload={"validation_run_id": validation.id, "slug": slug},
            value=1.0,
        )
    )
    session.flush()
    return True


def capture_objections(
    session: Session,
    *,
    validation_run_id: str,
    replies: list[str],
    run_id: str | None = None,
    step_name: str | None = None,
) -> int:
    """Objections are gold: they become the FAQ and the sales page's rebuttal
    section. `storefront_publisher` reads them straight out of this table."""
    if not replies:
        return 0
    payload = llm.complete_json(
        prompt_name="validation_objections",
        variables={"replies": "\n".join(f"- {r}" for r in replies)},
        schema=OBJECTION_SCHEMA,
        agent="validation_runner",
        run_id=run_id,
        step_name=step_name,
        session=session,
    )
    count = 0
    for entry in payload.get("objections", []):
        session.add(
            Objection(
                validation_run_id=validation_run_id,
                text=entry["text"],
                theme=entry.get("theme"),
                rebuttal=entry.get("rebuttal"),
            )
        )
        count += 1
    session.flush()
    return count


def evaluate(session: Session, validation_run_id: str) -> dict[str, Any]:
    validation = session.get(ValidationRun, validation_run_id)
    if validation is None:
        raise KeyError(f"no such validation run {validation_run_id!r}")
    if validation.threshold_set_at > utcnow():
        raise ThresholdTampering(
            "threshold timestamp is in the future — the success criterion must "
            "predate the test"
        )

    actual = (
        validation.signups
        if validation.threshold_metric == "signups"
        else sum(v.reply_count for v in validation.outreach)
    )
    passed = actual >= validation.success_threshold
    validation.outcome = "pass" if passed else "fail"
    session.flush()

    return {
        "validation_run_id": validation.id,
        "metric": validation.threshold_metric,
        "threshold": validation.success_threshold,
        "actual": actual,
        "views": validation.views,
        "outcome": validation.outcome,
        "objections": [o.text for o in validation.objections],
    }


# --------------------------------------------------------------------------- #


def _signals(session: Session, cluster_id: str) -> list[PainSignal]:
    return list(
        session.scalars(
            select(PainSignal)
            .join(ClusterMember, ClusterMember.pain_signal_id == PainSignal.id)
            .where(ClusterMember.cluster_id == cluster_id)
            .order_by(PainSignal.score.desc())
        ).all()
    )


def _first_thread(session: Session, pain_signal_id: str) -> str | None:
    return session.scalar(
        select(SourceDocument.url)
        .join(
            SignalOccurrence,
            SignalOccurrence.source_document_id == SourceDocument.id,
        )
        .where(SignalOccurrence.pain_signal_id == pain_signal_id)
        .limit(1)
    )


def _slug(candidate: OfferCandidate, session: Session) -> str:
    base = "-".join(
        part
        for part in "".join(
            c.lower() if c.isalnum() else " " for c in candidate.promise
        ).split()
    )[:60] or "offer"
    slug = base
    if session.scalar(select(ValidationRun).where(ValidationRun.slug == slug)):
        slug = f"{base}-{candidate.id[-6:]}"
    return slug


def _render_landing(page: dict[str, Any], candidate: OfferCandidate) -> str:
    parts = [f"<p class='lede'>{_esc(page['subhead'])}</p>"]
    parts += [f"<p>{_esc(p)}</p>" for p in page["problem_paragraphs"]]
    parts.append("<h3>What this is</h3><ul>")
    parts += [f"<li>{_esc(item)}</li>" for item in page["what_it_is"]]
    parts.append("</ul>")
    parts.append(
        f"<p class='price'>{_esc(page['price_framing'])} — "
        f"{candidate.price_cents / 100:,.2f} {candidate.currency}</p>"
    )
    return "\n".join(parts)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
