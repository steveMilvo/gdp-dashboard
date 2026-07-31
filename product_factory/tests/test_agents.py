"""Agent-level rules: recurrence gating, the specificity rule, idempotent
delivery, and the pre-registered validation threshold."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from product_factory.agents import (
    content_engine,
    demand_miner,
    offer_synthesiser,
    validation_runner,
)
from product_factory.db import session_scope
from product_factory.models import (
    ContentPiece,
    NegativeExample,
    Niche,
    PainSignal,
    SourceDocument,
)


def _niche(sess, hypothesis="AU sole traders drowning in month-end admin"):
    niche = Niche(hypothesis=hypothesis, seed_keywords=["reconciliation"])
    sess.add(niche)
    sess.flush()
    return niche


# --------------------------------------------------------------------------- #
# Agent 1
# --------------------------------------------------------------------------- #


def test_recurrence_rule_rejects_single_source_and_single_sighting():
    """The rule the whole system rests on: a signal must recur, and it must
    recur across independent sources. One articulate complaint is noise."""
    with session_scope() as sess:
        niche = _niche(sess)
        result = demand_miner.mine(
            sess, niche_id=niche.id, min_recurrence=3, min_sources=2
        )

        assert result.documents_captured > 0
        signals = {
            s.normalised: s
            for s in sess.scalars(
                select(PainSignal).where(PainSignal.niche_id == niche.id)
            ).all()
        }

        # Seen 8 times across 4 kinds -> verified.
        multi = signals["the buyer cannot reconcile stripe fees reliably"]
        assert multi.verified is True
        assert multi.independent_sources == 4

        # Seen 5 times but only in one source kind -> rejected.
        single_kind = signals["the buyer cannot single source noise reliably"]
        assert single_kind.recurrence_count == 5
        assert single_kind.independent_sources == 1
        assert single_kind.verified is False

        # Seen once -> rejected.
        one_off = signals["the buyer cannot one off complaint reliably"]
        assert one_off.recurrence_count == 1
        assert one_off.verified is False


def test_signals_are_scored_by_recurrence_and_source_diversity():
    with session_scope() as sess:
        niche = _niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        verified = demand_miner.verified_signals(sess, niche.id)
        assert verified, "expected at least one verified signal"
        assert verified == sorted(verified, key=lambda s: s.score, reverse=True)
        # The four-source signal must outrank the three-source one.
        assert verified[0].independent_sources >= verified[-1].independent_sources


def test_non_verbatim_quotes_are_discarded(monkeypatch):
    """A quote that isn't in the source is a compliance problem, not a style
    one — every customer-facing claim traces back to it."""
    from product_factory.llm import client

    def hallucinating(prompt_name, variables):
        if prompt_name != "demand_miner_extract":
            raise AssertionError(prompt_name)
        return {
            "signals": [
                {
                    "quote": "A sentence that appears nowhere in the source text.",
                    "normalised": "invented problem",
                    "wtp_tier": "high",
                    "wtp_rationale": "made up",
                }
            ]
        }

    client.set_stub_responder(hallucinating)
    with session_scope() as sess:
        niche = _niche(sess)
        result = demand_miner.mine(sess, niche_id=niche.id)
        assert result.candidates == 0
        assert sess.scalars(select(PainSignal)).all() == []


def test_mining_is_idempotent_across_runs():
    with session_scope() as sess:
        niche = _niche(sess)
        first = demand_miner.mine(sess, niche_id=niche.id)
        second = demand_miner.mine(sess, niche_id=niche.id)
        assert first.candidates == second.candidates
        assert len(sess.scalars(select(SourceDocument)).all()) == first.documents_captured


# --------------------------------------------------------------------------- #
# Agent 2
# --------------------------------------------------------------------------- #


def test_rejecting_all_candidates_writes_negative_examples():
    with session_scope() as sess:
        niche = _niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        result = offer_synthesiser.synthesise(sess, niche_id=niche.id)
        assert result.candidate_ids

        offer_synthesiser.reject_all(
            sess,
            niche_id=niche.id,
            candidate_ids=result.candidate_ids,
            reason="price anchor is wrong for this market",
        )
        negatives = sess.scalars(select(NegativeExample)).all()
        assert len(negatives) == len(result.candidate_ids)
        assert "price anchor" in negatives[0].reason


def test_synthesis_without_verified_signals_is_an_error():
    with session_scope() as sess:
        niche = _niche(sess)
        with pytest.raises(ValueError, match="recurrence-verified"):
            offer_synthesiser.synthesise(sess, niche_id=niche.id)


# --------------------------------------------------------------------------- #
# Agent 6
# --------------------------------------------------------------------------- #


def test_specificity_rule_kills_generic_hooks():
    with session_scope() as sess:
        niche = _niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        signal = demand_miner.verified_signals(sess, niche.id)[0]

        ok, _, _ = content_engine.local_specificity(
            "5 tips to grow your business fast", signal
        )
        assert ok is False, "a hook of pure marketing filler must be rejected"

        ok, score, _ = content_engine.local_specificity(
            "Reconciling Stripe payouts against invoices takes two evenings", signal
        )
        assert ok is True and score > 0


def test_every_content_piece_is_anchored_to_exactly_one_signal():
    with session_scope() as sess:
        niche = _niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        result = content_engine.generate_calendar(
            sess, niche_id=niche.id, target_pieces=6, pieces_per_signal=2
        )
        assert result.accepted
        pieces = sess.scalars(select(ContentPiece)).all()
        assert all(p.pain_signal_id for p in pieces)
        assert len({p.pain_signal_id for p in pieces}) > 1


def test_unjudged_hooks_fail_closed(monkeypatch):
    """If the specificity judge returns nothing for a hook, that hook is not
    approved. Failing open here would let generic content through silently."""
    from product_factory.llm import client
    from tests.conftest import stub_responder

    def no_verdicts(prompt_name, variables):
        if prompt_name == "content_specificity_judge":
            return {"verdicts": []}
        return stub_responder(prompt_name, variables)

    with session_scope() as sess:
        niche = _niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        client.set_stub_responder(no_verdicts)
        result = content_engine.generate_calendar(
            sess, niche_id=niche.id, target_pieces=4, pieces_per_signal=2
        )
        assert result.accepted == []
        assert result.rejection_count > 0


def test_schedule_only_touches_approved_pieces():
    with session_scope() as sess:
        niche = _niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        result = content_engine.generate_calendar(
            sess, niche_id=niche.id, target_pieces=4, pieces_per_signal=2
        )
        scheduled = content_engine.schedule(
            sess, content_piece_ids=result.accepted
        )
        assert scheduled == 0, "nothing is scheduled before gate 2"

        content_engine.approve_batch(sess, content_piece_ids=result.accepted[:2])
        scheduled = content_engine.schedule(sess, content_piece_ids=result.accepted)
        assert scheduled == 2


# --------------------------------------------------------------------------- #
# Agent 3
# --------------------------------------------------------------------------- #


def test_validation_threshold_is_declared_before_the_test_runs():
    with session_scope() as sess:
        niche = _niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        candidate_id = offer_synthesiser.synthesise(
            sess, niche_id=niche.id
        ).candidate_ids[0]

        with pytest.raises(ValueError, match="declare a real threshold"):
            validation_runner.start_validation(
                sess, offer_candidate_id=candidate_id, success_threshold=0
            )

        setup = validation_runner.start_validation(
            sess, offer_candidate_id=candidate_id, success_threshold=3
        )
        assert setup.variant_count > 0

        # Two signups against a threshold of three is a fail, and the verdict
        # is taken against the number set beforehand.
        for i in range(2):
            validation_runner.record_signup(
                sess, slug=setup.slug, email=f"a{i}@example.test"
            )
        assert validation_runner.evaluate(sess, setup.validation_run_id)["outcome"] == "fail"

        validation_runner.record_signup(sess, slug=setup.slug, email="c@example.test")
        verdict = validation_runner.evaluate(sess, setup.validation_run_id)
        assert verdict["outcome"] == "pass"
        assert verdict["threshold"] == 3


def test_duplicate_signups_are_not_counted_twice():
    with session_scope() as sess:
        niche = _niche(sess)
        demand_miner.mine(sess, niche_id=niche.id)
        candidate_id = offer_synthesiser.synthesise(
            sess, niche_id=niche.id
        ).candidate_ids[0]
        setup = validation_runner.start_validation(
            sess, offer_candidate_id=candidate_id, success_threshold=5
        )
        assert validation_runner.record_signup(
            sess, slug=setup.slug, email="dup@example.test"
        )
        assert not validation_runner.record_signup(
            sess, slug=setup.slug, email="dup@example.test"
        )
        assert validation_runner.evaluate(sess, setup.validation_run_id)["actual"] == 1
