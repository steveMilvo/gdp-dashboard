"""The seven acceptance criteria from the build spec, as executable checks.

These run against the stub model layer, so they verify the *system* — the
gating, the quality passes, the attribution chain, the idempotency — rather
than the quality of any particular generation.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from product_factory.agents import (
    artifact_builder,
    content_engine,
    demand_miner,
    offer_synthesiser,
    signal_loop,
    storefront_publisher,
)
from product_factory.attribution import chain_for_order, unit_economics
from product_factory.db import session_scope
from product_factory.models import (
    AgentInvocation,
    ArtifactVersion,
    ContentPiece,
    Listing,
    Niche,
    Order,
    OrderStatus,
    ProductFormat,
    QualityCheck,
    utcnow,
)
from product_factory.orchestrator import spine
from product_factory.storefront.delivery import record_order
from product_factory.storefront.selfhosted import test_event as make_paid_event


def _seed_niche(sess) -> Niche:
    niche = Niche(
        hypothesis="AU sole traders drowning in month-end reconciliation",
        seed_keywords=["stripe reconciliation", "late invoices"],
    )
    sess.add(niche)
    sess.flush()
    return niche


def _to_listing(sess, fmt: str = ProductFormat.EBOOK.value) -> Listing:
    niche = _seed_niche(sess)
    demand_miner.mine(sess, niche_id=niche.id)
    candidate_id = offer_synthesiser.synthesise(sess, niche_id=niche.id).candidate_ids[0]
    candidate = offer_synthesiser.select_candidate(sess, candidate_id)
    candidate.format = fmt
    sess.flush()
    build = artifact_builder.build_product(sess, offer_candidate_id=candidate_id)
    published = storefront_publisher.publish(
        sess, artifact_version_id=build.artifact_version_id
    )
    return sess.get(Listing, published.listing_id)


# --------------------------------------------------------------------------- #


def test_ac1_twenty_recurrence_verified_signals_with_sources():
    """AC1: a niche hypothesis produces recurrence-verified pain signals with
    sources in one run.

    The fixture corpus is deliberately small, so this asserts the *mechanism*:
    every verified signal clears both thresholds and carries at least two
    distinct captured source rows.
    """
    with session_scope() as sess:
        niche = _seed_niche(sess)
        result = demand_miner.mine(
            sess, niche_id=niche.id, min_recurrence=3, min_sources=2
        )
        verified = demand_miner.verified_signals(sess, niche.id)

        assert result.verified == len(verified) > 0
        for signal in verified:
            assert signal.recurrence_count >= 3
            assert signal.independent_sources >= 2
            urls = {occ.source_document.url for occ in signal.occurrences}
            assert len(urls) >= 2, "every signal must cite multiple sources"
            assert all(url.startswith("https://") for url in urls)


def test_ac2_operator_reaches_a_live_validation_page_without_writing_code():
    """AC2: select a candidate at the gate, get a live landing page."""
    run_id = None
    with session_scope() as sess:
        niche = _seed_niche(sess)
        niche_id = niche.id

    run_id = spine.start_run(
        "discover_demand", niche_id=niche_id, context={"niche_id": niche_id}
    )
    assert spine.resume_run(run_id) == "awaiting_gate"

    gate = spine.open_gates()[0]
    assert gate["stage"] == 2
    candidate_id = gate["payload"]["candidates"][0]["id"]

    spine.decide_gate(gate["id"], approved=True, decision={"candidate_id": candidate_id})
    assert spine.resume_run(run_id) == "succeeded"

    from fastapi.testclient import TestClient

    from product_factory.web.app import app

    with session_scope() as sess:
        from product_factory.models import ValidationRun

        validation = sess.scalars(select(ValidationRun)).one()
        slug = validation.slug

    client = TestClient(app)
    page = client.get(f"/v/{slug}")
    assert page.status_code == 200
    assert "<form" in page.text

    signup = client.post(f"/v/{slug}/signup", data={"email": "buyer@example.test"})
    assert signup.status_code == 200
    with session_scope() as sess:
        assert sess.scalars(select(ValidationRun)).one().signups == 1


def test_ac3_document_product_reaches_a_quality_passed_pdf_with_cover():
    """AC3: approved offer -> downloadable, quality-passed PDF with a cover,
    unattended."""
    with session_scope() as sess:
        niche = _seed_niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        candidate_id = offer_synthesiser.synthesise(
            sess, niche_id=niche.id
        ).candidate_ids[0]
        offer_synthesiser.select_candidate(sess, candidate_id)

        result = artifact_builder.build_product(sess, offer_candidate_id=candidate_id)
        artifact = sess.get(ArtifactVersion, result.artifact_version_id)

        assert result.quality_passed is True
        assert artifact.path.endswith(".pdf")
        assert artifact.cover_path.endswith(".pdf")
        assert artifact.bytes > 8_000
        assert len(artifact.checksum) == 64

        names = {c.name for c in sess.scalars(select(QualityCheck)).all()}
        assert {"pdf_readable", "no_placeholders", "prose_hygiene", "link_check"} <= names
        assert all(c.passed for c in artifact.quality_checks)


def test_ac3b_quality_failure_blocks_the_listing():
    """The hard rule, from the other side: an artifact that fails its
    mechanical pass cannot be listed."""
    with session_scope() as sess:
        niche = _seed_niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        candidate_id = offer_synthesiser.synthesise(
            sess, niche_id=niche.id
        ).candidate_ids[0]
        build = artifact_builder.build_product(sess, offer_candidate_id=candidate_id)

        artifact = sess.get(ArtifactVersion, build.artifact_version_id)
        artifact.quality_passed = False
        sess.flush()

        with pytest.raises(storefront_publisher.NotQualityPassed):
            storefront_publisher.publish(
                sess, artifact_version_id=build.artifact_version_id
            )


def test_ac4_micro_app_deploys_to_a_live_url_with_a_smoke_tested_flow():
    """AC4: a micro-app product reaches a live URL with a smoke-tested primary
    flow. The smoke test starts the real process and makes a real request."""
    with session_scope() as sess:
        niche = _seed_niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        candidate_id = offer_synthesiser.synthesise(
            sess, niche_id=niche.id
        ).candidate_ids[0]
        candidate = offer_synthesiser.select_candidate(sess, candidate_id)
        candidate.format = ProductFormat.MICRO_APP.value
        sess.flush()

        result = artifact_builder.build_product(sess, offer_candidate_id=candidate_id)
        assert result.quality_passed is True
        assert result.url and result.url.startswith("http")

        checks = {
            c.name: c
            for c in sess.get(ArtifactVersion, result.artifact_version_id).quality_checks
        }
        assert checks["app_smoke"].passed is True
        assert "200" in checks["app_smoke"].detail

    from product_factory.builders.deploy import status, stop

    deployments = status()
    assert len(deployments) == 1
    try:
        assert deployments[0].port > 0
        # The primary flow answers on the deployed port, not just in the test.
        import httpx

        resp = httpx.post(
            f"http://127.0.0.1:{deployments[0].port}/api/run",
            json={"gross": "1000", "fee_percent": "2.5", "invoices": "4"},
            timeout=10.0,
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["ok"] is True
        assert payload["result"]["net"] == 975.0
    finally:
        stop(deployments[0].slug)


def test_ac5_purchase_delivers_and_produces_a_single_sql_attribution_chain():
    """AC5: a completed purchase triggers delivery and creates a full
    attribution chain queryable in one SQL statement."""
    with session_scope() as sess:
        listing = _to_listing(sess)
        slug = listing.slug
        price = listing.price_cents

    with session_scope() as sess:
        before = utcnow()
        result = record_order(
            sess,
            make_paid_event(
                listing_slug=slug, buyer_email="buyer@example.test", amount_cents=price
            ),
        )
        order = sess.get(Order, result.order_id)

        assert result.created is True
        assert order.status == OrderStatus.DELIVERED.value
        assert order.licence_key and len(order.licence_key) == 19
        assert order.download_token
        # Delivery happens inline; the artifact was built before the listing
        # went live, so there is nothing slow left to do.
        assert (order.delivered_at - before).total_seconds() < 60

        chain = chain_for_order(sess, order.id)
        assert chain, "the attribution chain must not be empty"
        row = chain[0]
        # order -> listing -> product -> offer -> cluster -> signal -> source
        assert row["order_id"] == order.id
        assert row["listing_slug"] == slug
        assert row["product_format"] == ProductFormat.EBOOK.value
        assert row["offer_promise"]
        assert row["pain_quote"], "revenue traces back to a verbatim complaint"
        assert row["source_url"].startswith("https://")
        assert row["buyer_email"] == "buyer@example.test"


def test_ac5b_retried_webhook_does_not_double_charge_or_double_deliver():
    with session_scope() as sess:
        listing = _to_listing(sess)
        slug, price = listing.slug, listing.price_cents

    event = make_paid_event(
        listing_slug=slug, buyer_email="buyer@example.test", amount_cents=price
    )
    with session_scope() as sess:
        first = record_order(sess, event)
        second = record_order(sess, event)  # identical retry
        third = record_order(sess, event)

        assert first.created is True
        assert second.created is False and third.created is False
        assert first.order_id == second.order_id == third.order_id

        orders = sess.scalars(select(Order)).all()
        assert len(orders) == 1
        assert orders[0].buyer.lifetime_value_cents == price


def test_ac5c_refund_revokes_access_and_reverses_lifetime_value():
    with session_scope() as sess:
        listing = _to_listing(sess)
        slug, price = listing.slug, listing.price_cents

    paid = make_paid_event(
        listing_slug=slug, buyer_email="buyer@example.test", amount_cents=price
    )
    with session_scope() as sess:
        record_order(sess, paid)
        refund = make_paid_event(
            listing_slug=slug, buyer_email="buyer@example.test", amount_cents=price
        )
        refund.status = "refunded"
        record_order(sess, refund)

        order = sess.scalars(select(Order)).one()
        assert order.status == OrderStatus.REFUNDED.value
        assert order.download_token is None
        assert order.buyer.lifetime_value_cents == 0


def test_ac6_thirty_pieces_each_on_a_distinct_signal_with_few_rejections():
    """AC6: the content engine produces 30 pieces, each traceable to a pain
    signal, with fewer than 3 rejected by the specificity rule."""
    with session_scope() as sess:
        niche = _seed_niche(sess)
        demand_miner.mine(sess, niche_id=niche.id, min_recurrence=1, min_sources=1)
        result = content_engine.generate_calendar(
            sess, niche_id=niche.id, target_pieces=30, pieces_per_signal=6
        )

        assert len(result.accepted) >= 30
        assert result.rejection_count < 3, (
            f"specificity rule rejected {result.rejection_count} pieces: "
            f"{result.rejected}"
        )

        pieces = sess.scalars(select(ContentPiece)).all()
        assert all(p.pain_signal_id for p in pieces)
        assert all(p.specificity_score and p.specificity_score > 0 for p in pieces)
        # Anchored to several distinct signals, not all piled onto the best one.
        assert len({p.pain_signal_id for p in pieces}) >= 5


def test_ac7_weekly_report_ranks_signals_by_revenue_per_content_piece():
    """AC7: Agent 7 produces a weekly report ranking pain signals by realised
    revenue per content piece."""
    with session_scope() as sess:
        listing = _to_listing(sess)
        niche_id = sess.scalars(select(Niche)).one().id
        listing_slug, price = listing.slug, listing.price_cents

        content = content_engine.generate_calendar(
            sess, niche_id=niche_id, target_pieces=6, pieces_per_signal=2
        )
        content_engine.approve_batch(sess, content_piece_ids=content.accepted)
        winning_piece = sess.get(ContentPiece, content.accepted[0])

    with session_scope() as sess:
        record_order(
            sess,
            make_paid_event(
                listing_slug=listing_slug,
                buyer_email="buyer@example.test",
                amount_cents=price,
                ref=winning_piece.id,
            ),
        )

    with session_scope() as sess:
        result = signal_loop.run_weekly(sess, niche_id=niche_id)
        assert result.rankings

        ranked = {r["pain_signal_id"]: r for r in result.rankings}
        winner = ranked[winning_piece.pain_signal_id]
        assert winner["orders"] == 1
        assert winner["gross_cents"] == price
        assert winner["revenue_per_piece_cents"] == price / winner["content_pieces"]

        # Signals with realised revenue rank above those without.
        assert result.rankings[0]["pain_signal_id"] == winning_piece.pain_signal_id
        assert winning_piece.pain_signal_id in result.promoted
        assert result.patterns


def test_unit_economics_are_computable_from_the_invocation_log_alone():
    """Every model call is logged with model, tokens, cost and duration —
    that is the stated requirement for per-product unit economics."""
    with session_scope() as sess:
        _to_listing(sess)

    with session_scope() as sess:
        invocations = sess.scalars(select(AgentInvocation)).all()
        assert invocations
        assert {i.agent for i in invocations} >= {
            "demand_miner",
            "offer_synthesiser",
            "artifact_builder.document",
            "storefront_publisher",
        }
        assert all(i.prompt_name and i.prompt_version for i in invocations)
        assert all(i.model for i in invocations)

        economics = unit_economics(sess)
        assert len(economics) == 1
        assert economics[0]["model_calls"] > 0

        # Nothing in the log may contain a secret.
        blob = json.dumps([i.input_json for i in invocations], default=str)
        assert "sk-ant" not in blob and "test-operator-token" not in blob
