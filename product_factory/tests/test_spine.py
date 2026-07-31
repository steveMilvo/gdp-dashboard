"""The orchestration spine: resumability, gates, idempotent replay."""

from __future__ import annotations

import pytest

from product_factory.db import session_scope
from product_factory.models import Gate, Run, RunStatus, RunStep, StepStatus
from product_factory.orchestrator import spine


def _fresh_workflow(name: str) -> spine.Workflow:
    workflow = spine.Workflow(name=name)
    spine.register(workflow)
    return workflow


def test_completed_steps_are_not_re_executed_on_resume():
    """The core durability property: a resumed run replays committed outputs
    rather than redoing the work. This is what lets a 40-minute content batch
    survive a restart."""
    calls: list[str] = []
    workflow = _fresh_workflow("t_resume")

    @workflow.step("first")
    def first(ctx):
        calls.append("first")
        return {"value": 1}

    @workflow.step("second")
    def second(ctx):
        calls.append("second")
        if len([c for c in calls if c == "second"]) == 1:
            raise RuntimeError("simulated crash")
        return {"value": ctx.output_of("first")["value"] + 1}

    workflow.steps[1].max_attempts = 1

    run_id = spine.start_run("t_resume")
    assert spine.resume_run(run_id) == RunStatus.FAILED.value
    assert calls == ["first", "second"]

    # Resume: `first` is replayed from the database, not re-executed.
    assert spine.resume_run(run_id) == RunStatus.SUCCEEDED.value
    assert calls == ["first", "second", "second"]

    with session_scope() as sess:
        steps = {s.name: s for s in sess.get(Run, run_id).steps}
        assert steps["first"].status == StepStatus.SUCCEEDED.value
        assert steps["second"].output == {"value": 2}


def test_gate_parks_the_run_and_blocks_everything_downstream():
    downstream: list[str] = []
    workflow = _fresh_workflow("t_gate")

    @workflow.step("needs_approval", gated=True)
    def needs_approval(ctx):
        if ctx.gate_decision is None:
            raise spine.GateRequired(stage=4, title="Approve", payload={"a": 1})
        return {"chosen": ctx.gate_decision["choice"]}

    @workflow.step("after")
    def after(ctx):
        downstream.append("ran")
        return {}

    run_id = spine.start_run("t_gate")
    assert spine.resume_run(run_id) == RunStatus.AWAITING_GATE.value
    assert downstream == [], "downstream step must not run while a gate is open"

    gates = spine.open_gates()
    assert len(gates) == 1 and gates[0]["stage"] == 4
    assert gates[0]["payload"] == {"a": 1}

    spine.decide_gate(gates[0]["id"], approved=True, decision={"choice": "b"})
    assert spine.resume_run(run_id) == RunStatus.SUCCEEDED.value
    assert downstream == ["ran"]

    with session_scope() as sess:
        step = next(
            s for s in sess.get(Run, run_id).steps if s.name == "needs_approval"
        )
        assert step.output == {"chosen": "b"}


def test_rejected_gate_cancels_the_run():
    workflow = _fresh_workflow("t_reject")

    @workflow.step("gate_step", gated=True)
    def gate_step(ctx):
        if ctx.gate_decision is None:
            raise spine.GateRequired(stage=2, title="Pick one")
        return {}

    run_id = spine.start_run("t_reject")
    spine.resume_run(run_id)
    gate = spine.open_gates()[0]
    spine.decide_gate(gate["id"], approved=False, decision={"reason": "all weak"})

    assert spine.resume_run(run_id) == RunStatus.CANCELLED.value
    with session_scope() as sess:
        assert "all weak" in (sess.get(Run, run_id).error or "")


def test_step_retries_before_failing():
    attempts: list[int] = []
    workflow = _fresh_workflow("t_retry")

    @workflow.step("flaky")
    def flaky(ctx):
        attempts.append(ctx.attempt)
        if ctx.attempt < 3:
            raise RuntimeError("transient")
        return {"ok": True}

    workflow.steps[0].retry_backoff_seconds = 0.01
    run_id = spine.start_run("t_retry")
    assert spine.resume_run(run_id) == RunStatus.SUCCEEDED.value
    assert attempts == [1, 2, 3]


def test_context_survives_a_restart():
    workflow = _fresh_workflow("t_context")

    @workflow.step("writer")
    def writer(ctx):
        ctx.context["carried"] = "value"
        return {}

    @workflow.step("reader", gated=True)
    def reader(ctx):
        if ctx.gate_decision is None:
            raise spine.GateRequired(stage=6, title="pause here")
        return {"saw": ctx.context.get("carried")}

    run_id = spine.start_run("t_context", context={"seed": 1})
    spine.resume_run(run_id)

    # Simulate a process restart: nothing is held in memory between these calls.
    gate = spine.open_gates()[0]
    spine.decide_gate(gate["id"], approved=True, decision={})
    spine.resume_run(run_id)

    with session_scope() as sess:
        step = next(s for s in sess.get(Run, run_id).steps if s.name == "reader")
        assert step.output == {"saw": "value"}


def test_unknown_workflow_fails_fast():
    with pytest.raises(KeyError):
        spine.start_run("does_not_exist")


def test_gate_cannot_be_decided_twice():
    workflow = _fresh_workflow("t_double")

    @workflow.step("g", gated=True)
    def g(ctx):
        if ctx.gate_decision is None:
            raise spine.GateRequired(stage=2, title="once only")
        return {}

    run_id = spine.start_run("t_double")
    spine.resume_run(run_id)
    gate_id = spine.open_gates()[0]["id"]
    spine.decide_gate(gate_id, approved=True, decision={})
    with pytest.raises(ValueError):
        spine.decide_gate(gate_id, approved=True, decision={})

    with session_scope() as sess:
        assert sess.get(Gate, gate_id).status == "approved"
        assert (
            sess.query(RunStep).filter_by(run_id=run_id, name="g").one().status
            in {StepStatus.PENDING.value, StepStatus.SUCCEEDED.value}
        )
