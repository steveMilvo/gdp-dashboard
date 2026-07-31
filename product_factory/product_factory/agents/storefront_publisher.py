"""Agent 5 — Storefront Publisher.

Builds the listing copy *from the objection log*, not from the promise. The
promise gets the buyer's attention; the objections are what stop them buying,
so the description's job is to answer them in order.

Refuses to publish an artifact whose `quality_passed` is false. That's the
enforcement point for Agent 4's hard rule.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..llm import client as llm
from ..models import (
    ArtifactVersion,
    Competitor,
    Listing,
    Objection,
    OfferCandidate,
    Product,
    ValidationRun,
)
from ..storefront.adapter import ListingSpec
from ..storefront.adapter import get as get_adapter

log = logging.getLogger("product_factory.agent5")

LISTING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "lede": {"type": "string"},
        "what_you_get": {"type": "array", "items": {"type": "string"}},
        "objection_answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "objection": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["objection", "answer"],
                "additionalProperties": False,
            },
        },
        "who_its_not_for": {"type": "string"},
    },
    "required": [
        "title",
        "lede",
        "what_you_get",
        "objection_answers",
        "who_its_not_for",
    ],
    "additionalProperties": False,
}


class NotQualityPassed(RuntimeError):
    pass


@dataclass
class PublishResult:
    listing_id: str
    slug: str
    checkout_url: str
    adapter: str


def publish(
    session: Session,
    *,
    artifact_version_id: str,
    adapter_name: str | None = None,
    live: bool = True,
    run_id: str | None = None,
    step_name: str | None = None,
) -> PublishResult:
    artifact = session.get(ArtifactVersion, artifact_version_id)
    if artifact is None:
        raise KeyError(f"no such artifact version {artifact_version_id!r}")
    if not artifact.quality_passed:
        raise NotQualityPassed(
            f"artifact {artifact.id} has not passed its quality checks; "
            "generated content that has not been mechanically verified does "
            "not reach a buyer"
        )

    product = session.get(Product, artifact.product_id)
    assert product is not None
    candidate = session.get(OfferCandidate, product.offer_candidate_id)
    assert candidate is not None

    objections = _objections(session, candidate.id)
    competitors = session.scalars(
        select(Competitor).where(Competitor.offer_candidate_id == candidate.id)
    ).all()

    copy = llm.complete_json(
        prompt_name="listing_copy",
        variables={
            "promise": candidate.promise,
            "target_buyer": candidate.target_buyer,
            "format": candidate.format,
            "price": f"{candidate.price_cents / 100:,.2f} {candidate.currency}",
            "objections": "\n".join(f"- {o}" for o in objections)
            or "(no validation objections captured)",
            "competitors": "\n".join(
                f"- {c.name} at "
                f"{(c.price_cents or 0) / 100:,.2f} {c.currency}: {c.positioning}"
                for c in competitors
            )
            or "(none identified)",
            "contents": _contents_summary(artifact),
        },
        schema=LISTING_SCHEMA,
        agent="storefront_publisher",
        run_id=run_id,
        step_name=step_name,
        product_id=product.id,
        session=session,
    )

    slug = f"{product.slug}"
    existing = session.scalar(select(Listing).where(Listing.slug == slug))
    if existing is not None:
        slug = f"{product.slug}-v{artifact.version}"

    description_html = _render_description(copy)
    spec = ListingSpec(
        slug=slug,
        title=copy["title"],
        description_html=description_html,
        price_cents=candidate.price_cents,
        currency=candidate.currency,
        preview_assets=[p for p in [artifact.cover_path] if p],
        artifact_path=artifact.path,
        metadata={"product_id": product.id, "artifact_version_id": artifact.id},
    )

    adapter = get_adapter(adapter_name)
    remote = adapter.publish(spec)

    listing = Listing(
        product_id=product.id,
        artifact_version_id=artifact.id,
        adapter=remote.adapter,
        external_id=remote.external_id,
        slug=slug,
        title=copy["title"],
        description_html=description_html,
        price_cents=candidate.price_cents,
        currency=candidate.currency,
        preview_assets=spec.preview_assets,
        checkout_url=remote.checkout_url,
        live=live and remote.live,
    )
    session.add(listing)
    session.flush()

    return PublishResult(
        listing_id=listing.id,
        slug=slug,
        checkout_url=remote.checkout_url,
        adapter=remote.adapter,
    )


def _objections(session: Session, offer_candidate_id: str) -> list[str]:
    rows = session.scalars(
        select(Objection)
        .join(ValidationRun, ValidationRun.id == Objection.validation_run_id)
        .where(ValidationRun.offer_candidate_id == offer_candidate_id)
        .order_by(Objection.created_at)
    ).all()
    return [row.text for row in rows]


def _contents_summary(artifact: ArtifactVersion) -> str:
    meta = artifact.meta or {}
    if "sections" in meta:
        return "\n".join(f"- {s}" for s in meta["sections"])
    if "modules" in meta:
        return "\n".join(f"- Module: {m}" for m in meta["modules"])
    if "files" in meta:
        return "\n".join(f"- {f}" for f in meta["files"])
    if "spec" in meta:
        spec = meta["spec"]
        return f"- {spec.get('name')}: {spec.get('primary_flow')}"
    return "(contents not enumerated)"


def _render_description(copy: dict[str, Any]) -> str:
    parts = [f"<p class='lede'>{_esc(copy['lede'])}</p>", "<h3>What you get</h3><ul>"]
    parts += [f"<li>{_esc(item)}</li>" for item in copy["what_you_get"]]
    parts.append("</ul>")
    if copy["objection_answers"]:
        parts.append("<h3>Straight answers</h3><dl>")
        for entry in copy["objection_answers"]:
            parts.append(f"<dt>{_esc(entry['objection'])}</dt>")
            parts.append(f"<dd>{_esc(entry['answer'])}</dd>")
        parts.append("</dl>")
    parts.append(
        f"<h3>Who this isn't for</h3><p>{_esc(copy['who_its_not_for'])}</p>"
    )
    return "\n".join(parts)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
