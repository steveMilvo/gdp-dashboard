"""The whole pipeline, through all three mandatory gates.

This is the test that proves the spec's central claim: everything except
stages 2, 4 and 6 runs unattended, and those three stop dead until a human
decides. It also proves resumability across gate boundaries — each
`resume_run` call is a fresh entry point holding no in-memory state.
"""

from __future__ import annotations

from sqlalchemy import select

from product_factory.attribution import chain_for_order
from product_factory.db import session_scope
from product_factory.models import (
    ContentPiece,
    Listing,
    Niche,
    Publication,
    Run,
    RunStatus,
    ValidationRun,
)
from product_factory.orchestrator import spine
from product_factory.storefront.delivery import record_order
from product_factory.storefront.selfhosted import test_event as make_paid_event


def _gate(expected_stage: int) -> dict:
    gates = spine.open_gates()
    assert len(gates) == 1, f"expected exactly one open gate, got {len(gates)}"
    assert gates[0]["stage"] == expected_stage, (
        f"expected a stage {expected_stage} gate, got stage {gates[0]['stage']}"
    )
    return gates[0]


def test_full_cycle_stops_at_every_mandatory_gate_and_completes():
    with session_scope() as sess:
        niche = Niche(
            hypothesis="AU sole traders drowning in month-end reconciliation",
            seed_keywords=["stripe reconciliation"],
        )
        sess.add(niche)
        sess.flush()
        niche_id = niche.id

    run_id = spine.start_run(
        "full_cycle",
        niche_id=niche_id,
        context={
            "niche_id": niche_id,
            "success_threshold": 2,
            "target_pieces": 8,
            "pieces_per_signal": 2,
        },
    )

    # --- Stage 2, gate 1: pick an offer -------------------------------------
    assert spine.resume_run(run_id) == RunStatus.AWAITING_GATE.value
    gate = _gate(2)
    assert gate["step_name"] == "select_offer"
    candidates = gate["payload"]["candidates"]
    assert candidates and candidates[0]["competitors"], (
        "the operator must see competitors and prices to make this call"
    )
    assert candidates[0]["signals"], "and the signals the offer came from"
    spine.decide_gate(
        gate["id"], approved=True, decision={"candidate_id": candidates[0]["id"]}
    )

    # --- Stage 2, gate 2: close the validation window ------------------------
    assert spine.resume_run(run_id) == RunStatus.AWAITING_GATE.value
    gate = _gate(2)
    assert gate["step_name"] == "evaluate_validation"

    # Simulate the test actually running: signups arrive, replies come back.
    with session_scope() as sess:
        from product_factory.agents import validation_runner

        slug = sess.scalars(select(ValidationRun)).one().slug
        for i in range(3):
            validation_runner.record_signup(
                sess, slug=slug, email=f"prospect{i}@example.test"
            )

    spine.decide_gate(
        gate["id"],
        approved=True,
        decision={
            "replies": [
                "I already pay for a bookkeeper, why would I need this",
                "Does this handle multi-currency payouts",
            ]
        },
    )

    # --- Stage 4: approve the packaging -------------------------------------
    assert spine.resume_run(run_id) == RunStatus.AWAITING_GATE.value
    gate = _gate(4)
    assert gate["step_name"] == "approve_packaging"
    payload = gate["payload"]
    assert payload["cover_path"], "the operator approves a cover, so show them one"
    assert payload["quality_checks"], "and the mechanical checks that passed"
    assert all(c["passed"] for c in payload["quality_checks"])
    assert payload["competitors"], "price anchoring needs the anchors"

    # The operator overrides the price — a real thing they do at this gate.
    spine.decide_gate(gate["id"], approved=True, decision={"price_cents": 5900})

    # --- Stage 6: approve the content batch ---------------------------------
    assert spine.resume_run(run_id) == RunStatus.AWAITING_GATE.value
    gate = _gate(6)
    assert gate["step_name"] == "approve_content"
    pieces = gate["payload"]["pieces"]
    assert pieces, "there must be a batch to approve"
    assert all(p["pain_signal_id"] for p in pieces)

    # Reject one piece by hand; the rest go through.
    spine.decide_gate(
        gate["id"], approved=True, decision={"rejected_ids": [pieces[0]["id"]]}
    )

    # --- Unattended to the end ----------------------------------------------
    assert spine.resume_run(run_id) == RunStatus.SUCCEEDED.value
    assert spine.open_gates() == []

    with session_scope() as sess:
        run = sess.get(Run, run_id)
        steps = {s.name: s for s in run.steps}
        assert len(steps) == 11
        assert all(s.status == "succeeded" for s in steps.values())

        # The price override at the stage-4 gate reached the listing.
        listing = sess.scalars(select(Listing)).one()
        assert listing.price_cents == 5900
        assert listing.live is True
        # And the objections captured at the validation gate reached the copy.
        assert "bookkeeper" in listing.description_html

        # The rejected piece is not approved and not published.
        approved = sess.scalars(
            select(ContentPiece).where(ContentPiece.approved.is_(True))
        ).all()
        rejected = sess.scalars(
            select(ContentPiece).where(ContentPiece.approved.is_(False))
        ).all()
        assert approved and rejected
        assert all(p.scheduled_for is not None for p in approved)
        assert all(p.scheduled_for is None for p in rejected)

        published_ids = {
            pub.content_piece_id for pub in sess.scalars(select(Publication)).all()
        }
        assert published_ids == {p.id for p in approved}

    # --- And a purchase resolves to a complaint ------------------------------
    with session_scope() as sess:
        listing = sess.scalars(select(Listing)).one()
        piece = sess.scalars(
            select(ContentPiece).where(ContentPiece.approved.is_(True))
        ).first()
        result = record_order(
            sess,
            make_paid_event(
                listing_slug=listing.slug,
                buyer_email="buyer@example.test",
                amount_cents=listing.price_cents,
                ref=piece.id,
            ),
        )
        chain = chain_for_order(sess, result.order_id)
        assert chain
        assert chain[0]["content_hook"] == piece.hook
        assert chain[0]["pain_quote"]
        assert chain[0]["source_url"].startswith("https://")


def test_resuming_a_completed_run_is_a_no_op():
    """Idempotent publishing means resume must be safe to call repeatedly —
    a supervisor that retries a finished run must not re-post or re-charge."""
    with session_scope() as sess:
        niche = Niche(hypothesis="test niche", seed_keywords=[])
        sess.add(niche)
        sess.flush()
        niche_id = niche.id

    run_id = spine.start_run(
        "discover_demand", niche_id=niche_id, context={"niche_id": niche_id}
    )
    spine.resume_run(run_id)
    gate = spine.open_gates()[0]
    spine.decide_gate(
        gate["id"],
        approved=True,
        decision={"candidate_id": gate["payload"]["candidates"][0]["id"]},
    )
    assert spine.resume_run(run_id) == RunStatus.SUCCEEDED.value

    with session_scope() as sess:
        before = len(sess.scalars(select(ValidationRun)).all())

    for _ in range(3):
        assert spine.resume_run(run_id) == RunStatus.SUCCEEDED.value

    with session_scope() as sess:
        assert len(sess.scalars(select(ValidationRun)).all()) == before
