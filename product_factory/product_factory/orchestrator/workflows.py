"""Workflow definitions — the agents wired onto the spine.

Four workflows, matching the build phases:

* `phase1_build_and_sell` — a manually specified offer, built and listed. This
  is the one that proves the machine works end to end before any of the
  discovery side exists.
* `discover_demand` — mine, cluster, pick an offer, put a validation page up.
* `full_cycle` — everything, gated at stages 2, 4 and 6.
* `weekly_signal_loop` — Agent 7, closing the loop back to Agent 1.

Gates carry the payload the operator needs to decide, because the console
renders straight from `gate.payload` and should never have to go re-query the
run to show a decision screen.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from ..agents import (
    artifact_builder,
    content_engine,
    demand_miner,
    offer_synthesiser,
    signal_loop,
    storefront_publisher,
    validation_runner,
)
from ..models import (
    ArtifactVersion,
    Competitor,
    ContentPiece,
    Listing,
    OfferCandidate,
    ValidationRun,
    utcnow,
)
from ..publishing.adapter import publish_approved
from .spine import GateRejected, GateRequired, StepContext, Workflow, register

log = logging.getLogger("product_factory.workflows")


# --------------------------------------------------------------------------- #
# Shared steps
# --------------------------------------------------------------------------- #


def _mine_demand(ctx: StepContext) -> dict[str, Any]:
    result = demand_miner.mine(
        ctx.session,
        niche_id=ctx.context["niche_id"],
        min_recurrence=ctx.context.get("min_recurrence", 3),
        min_sources=ctx.context.get("min_sources", 2),
        limit_per_source=ctx.context.get("limit_per_source", 60),
        source_config=ctx.context.get("source_config"),
        run_id=ctx.run_id,
        step_name=ctx.step_name,
    )
    return {
        "documents_captured": result.documents_captured,
        "candidates": result.candidates,
        "verified": result.verified,
    }


def _synthesise_offers(ctx: StepContext) -> dict[str, Any]:
    result = offer_synthesiser.synthesise(
        ctx.session,
        niche_id=ctx.context["niche_id"],
        max_candidates=ctx.context.get("max_candidates", 5),
        run_id=ctx.run_id,
        step_name=ctx.step_name,
    )
    return {"candidate_ids": result.candidate_ids, "cluster_ids": result.cluster_ids}


def _select_offer(ctx: StepContext) -> dict[str, Any]:
    """Gate 1. The operator picks one candidate or rejects the lot; rejection
    feeds the negative-example store so the same dead ends aren't re-proposed."""
    candidate_ids = ctx.output_of("synthesise_offers")["candidate_ids"]

    if ctx.gate_decision is None:
        raise GateRequired(
            stage=2,
            title="Select an offer candidate",
            payload={"candidates": _candidate_payload(ctx, candidate_ids)},
        )

    if not ctx.gate_decision.get("candidate_id"):
        offer_synthesiser.reject_all(
            ctx.session,
            niche_id=ctx.context["niche_id"],
            candidate_ids=candidate_ids,
            reason=ctx.gate_decision.get("reason", "operator rejected all candidates"),
        )
        raise GateRejected(ctx.gate_decision.get("reason", "all candidates rejected"))

    candidate = offer_synthesiser.select_candidate(
        ctx.session, ctx.gate_decision["candidate_id"]
    )
    ctx.context["offer_candidate_id"] = candidate.id
    return {"offer_candidate_id": candidate.id, "promise": candidate.promise}


def _start_validation(ctx: StepContext) -> dict[str, Any]:
    setup = validation_runner.start_validation(
        ctx.session,
        offer_candidate_id=ctx.context["offer_candidate_id"],
        success_threshold=ctx.context.get("success_threshold", 25),
        threshold_metric=ctx.context.get("threshold_metric", "signups"),
        variant_count=ctx.context.get("outreach_variants", 7),
        run_id=ctx.run_id,
        step_name=ctx.step_name,
    )
    ctx.context["validation_run_id"] = setup.validation_run_id
    return {
        "validation_run_id": setup.validation_run_id,
        "url": setup.url,
        "threshold": setup.threshold,
        "outreach_variants": setup.variant_count,
    }


def _evaluate_validation(ctx: StepContext) -> dict[str, Any]:
    """Stage 2's second gate: the operator confirms the test window is closed
    before the verdict is taken. Without it the run would evaluate a test that
    has been live for four seconds."""
    validation_run_id = ctx.context["validation_run_id"]

    if ctx.gate_decision is None:
        validation = ctx.session.get(ValidationRun, validation_run_id)
        assert validation is not None
        raise GateRequired(
            stage=2,
            title="Close the validation window and take the verdict",
            payload={
                "validation_run_id": validation.id,
                "headline": validation.headline,
                "threshold": validation.success_threshold,
                "metric": validation.threshold_metric,
                "signups_so_far": validation.signups,
                "views_so_far": validation.views,
                "objections": [o.text for o in validation.objections],
            },
        )

    replies = ctx.gate_decision.get("replies") or []
    if replies:
        validation_runner.capture_objections(
            ctx.session,
            validation_run_id=validation_run_id,
            replies=replies,
            run_id=ctx.run_id,
            step_name=ctx.step_name,
        )

    verdict = validation_runner.evaluate(ctx.session, validation_run_id)
    if verdict["outcome"] != "pass" and not ctx.gate_decision.get("override"):
        raise GateRejected(
            f"validation failed: {verdict['actual']} {verdict['metric']} against a "
            f"pre-registered threshold of {verdict['threshold']}"
        )
    return verdict


def _build_artifact(ctx: StepContext) -> dict[str, Any]:
    result = artifact_builder.build_product(
        ctx.session,
        offer_candidate_id=ctx.context["offer_candidate_id"],
        run_id=ctx.run_id,
        step_name=ctx.step_name,
        strict=ctx.context.get("strict_quality", True),
    )
    ctx.context["product_id"] = result.product_id
    ctx.context["artifact_version_id"] = result.artifact_version_id
    return {
        "product_id": result.product_id,
        "artifact_version_id": result.artifact_version_id,
        "quality_passed": result.quality_passed,
        "url": result.url,
    }


def _approve_packaging(ctx: StepContext) -> dict[str, Any]:
    """Stage 4 gate. Cover, positioning and price anchoring get a human look
    before anything is listed."""
    artifact_version_id = ctx.context["artifact_version_id"]

    if ctx.gate_decision is None:
        artifact = ctx.session.get(ArtifactVersion, artifact_version_id)
        assert artifact is not None
        candidate = ctx.session.get(
            OfferCandidate, ctx.context["offer_candidate_id"]
        )
        assert candidate is not None
        competitors = ctx.session.scalars(
            select(Competitor).where(Competitor.offer_candidate_id == candidate.id)
        ).all()
        raise GateRequired(
            stage=4,
            title="Approve packaging: cover, positioning, price",
            payload={
                "artifact_version_id": artifact.id,
                "kind": artifact.kind,
                "path": artifact.path,
                "cover_path": artifact.cover_path,
                "quality_checks": [
                    {"name": c.name, "passed": c.passed, "detail": c.detail}
                    for c in artifact.quality_checks
                ],
                "meta": artifact.meta,
                "proposed_price_cents": candidate.price_cents,
                "currency": candidate.currency,
                "competitors": [
                    {
                        "name": c.name,
                        "price_cents": c.price_cents,
                        "positioning": c.positioning,
                    }
                    for c in competitors
                ],
            },
        )

    if ctx.gate_decision.get("price_cents"):
        candidate = ctx.session.get(
            OfferCandidate, ctx.context["offer_candidate_id"]
        )
        assert candidate is not None
        candidate.price_cents = int(ctx.gate_decision["price_cents"])
        ctx.session.flush()
    return {"approved": True, "price_cents": ctx.gate_decision.get("price_cents")}


def _publish_listing(ctx: StepContext) -> dict[str, Any]:
    result = storefront_publisher.publish(
        ctx.session,
        artifact_version_id=ctx.context["artifact_version_id"],
        adapter_name=ctx.context.get("storefront_adapter"),
        run_id=ctx.run_id,
        step_name=ctx.step_name,
    )
    ctx.context["listing_id"] = result.listing_id
    return {
        "listing_id": result.listing_id,
        "slug": result.slug,
        "checkout_url": result.checkout_url,
        "adapter": result.adapter,
    }


def _generate_content(ctx: StepContext) -> dict[str, Any]:
    result = content_engine.generate_calendar(
        ctx.session,
        niche_id=ctx.context["niche_id"],
        product_id=ctx.context.get("product_id"),
        target_pieces=ctx.context.get("target_pieces", 30),
        pieces_per_signal=ctx.context.get("pieces_per_signal", 2),
        run_id=ctx.run_id,
        step_name=ctx.step_name,
    )
    return {
        "accepted": result.accepted,
        "rejected": result.rejected,
        "rejection_count": result.rejection_count,
    }


def _approve_content(ctx: StepContext) -> dict[str, Any]:
    """Gate 2 / stage 6. The batch is approved before anything is scheduled."""
    generated = ctx.output_of("generate_content")
    piece_ids = generated["accepted"]

    if ctx.gate_decision is None:
        pieces = [
            ctx.session.get(ContentPiece, pid) for pid in piece_ids
        ]
        raise GateRequired(
            stage=6,
            title=f"Approve content batch ({len(piece_ids)} pieces)",
            payload={
                "pieces": [
                    {
                        "id": p.id,
                        "platform": p.platform,
                        "hook": p.hook,
                        "body": p.body,
                        "cta": p.cta,
                        "format_notes": p.format_notes,
                        "pain_signal_id": p.pain_signal_id,
                        "specificity_score": p.specificity_score,
                    }
                    for p in pieces
                    if p is not None
                ],
                "rejected_by_specificity_rule": generated["rejected"],
            },
        )

    approved = content_engine.approve_batch(
        ctx.session,
        content_piece_ids=piece_ids,
        rejected_ids=ctx.gate_decision.get("rejected_ids"),
    )
    if approved == 0:
        raise GateRejected("operator approved no content pieces")
    return {"approved": approved}


def _schedule_and_publish(ctx: StepContext) -> dict[str, Any]:
    piece_ids = ctx.output_of("generate_content")["accepted"]
    scheduled = content_engine.schedule(
        ctx.session,
        content_piece_ids=piece_ids,
        per_day=ctx.context.get("posts_per_day", 3),
    )
    tally = publish_approved(ctx.session, limit=len(piece_ids) or 1)
    return {"scheduled": scheduled, "publish": tally}


def _weekly_loop(ctx: StepContext) -> dict[str, Any]:
    result = signal_loop.run_weekly(
        ctx.session,
        niche_id=ctx.context["niche_id"],
        run_id=ctx.run_id,
        step_name=ctx.step_name,
    )
    return {
        "report_id": result.report_id,
        "promoted": result.promoted,
        "demoted": result.demoted,
        "top": result.rankings[:5],
    }


def _candidate_payload(ctx: StepContext, candidate_ids: list[str]) -> list[dict]:
    payload = []
    for candidate_id in candidate_ids:
        candidate = ctx.session.get(OfferCandidate, candidate_id)
        if candidate is None:
            continue
        competitors = ctx.session.scalars(
            select(Competitor).where(Competitor.offer_candidate_id == candidate.id)
        ).all()
        payload.append(
            {
                "id": candidate.id,
                "promise": candidate.promise,
                "target_buyer": candidate.target_buyer,
                "format": candidate.format,
                "price_cents": candidate.price_cents,
                "currency": candidate.currency,
                "rationale": candidate.rationale,
                "signals": [
                    {"quote": m.pain_signal.quote, "score": m.pain_signal.score}
                    for m in candidate.cluster.members
                ],
                "competitors": [
                    {
                        "name": c.name,
                        "url": c.url,
                        "price_cents": c.price_cents,
                        "positioning": c.positioning,
                    }
                    for c in competitors
                ],
            }
        )
    return payload


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #


def _build(name: str, steps: list[tuple[str, Any, bool]]) -> Workflow:
    workflow = Workflow(name=name)
    for step_name, fn, gated in steps:
        workflow.step(step_name, gated=gated)(fn)
    return register(workflow)


#: Phase 1. Given an offer candidate that a human wrote by hand, build the
#: artifact, approve the packaging, and put it on sale. No discovery involved.
PHASE1 = _build(
    "phase1_build_and_sell",
    [
        ("build_artifact", _build_artifact, False),
        ("approve_packaging", _approve_packaging, True),
        ("publish_listing", _publish_listing, False),
    ],
)

#: Phase 2. Automate the input side, stopping at a live validation page.
DISCOVER = _build(
    "discover_demand",
    [
        ("mine_demand", _mine_demand, False),
        ("synthesise_offers", _synthesise_offers, False),
        ("select_offer", _select_offer, True),
        ("start_validation", _start_validation, False),
    ],
)

#: Everything, in order, with the three mandatory gates.
FULL_CYCLE = _build(
    "full_cycle",
    [
        ("mine_demand", _mine_demand, False),
        ("synthesise_offers", _synthesise_offers, False),
        ("select_offer", _select_offer, True),
        ("start_validation", _start_validation, False),
        ("evaluate_validation", _evaluate_validation, True),
        ("build_artifact", _build_artifact, False),
        ("approve_packaging", _approve_packaging, True),
        ("publish_listing", _publish_listing, False),
        ("generate_content", _generate_content, False),
        ("approve_content", _approve_content, True),
        ("schedule_and_publish", _schedule_and_publish, False),
    ],
)

#: Phase 4. Runs on a schedule; closes the loop back to Agent 1.
WEEKLY = _build("weekly_signal_loop", [("signal_loop", _weekly_loop, False)])


def listing_for_run(session, run_id: str) -> Listing | None:
    from ..models import RunStep

    step = session.scalar(
        select(RunStep).where(
            RunStep.run_id == run_id, RunStep.name == "publish_listing"
        )
    )
    if step is None or not step.output:
        return None
    return session.get(Listing, step.output.get("listing_id"))


def touch(run_id: str) -> None:  # pragma: no cover - convenience
    log.debug("run %s touched at %s", run_id, utcnow())
