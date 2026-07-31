"""Durable, resumable run execution.

The contract is small enough to hold in your head:

* A workflow is an ordered list of named steps.
* Every step's return value is committed to `run_step.output` before the next
  step starts. Re-running a run replays committed steps from the database and
  only executes what's missing.
* A step may raise `GateRequired`. That parks the run in `awaiting_gate`; the
  operator's decision is recorded on the `gate` row and the step re-executes
  with the decision available. Nothing downstream runs in the meantime.
* No agent holds state privately — `StepContext.record` is the only way out.

Deliberately not Temporal. The durability requirement here is "survive a
process restart mid-batch", which a committed checkpoint table satisfies
without adding a cluster to operate.
"""

from __future__ import annotations

import logging
import time
import traceback
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import (
    Gate,
    GateStatus,
    Run,
    RunStatus,
    RunStep,
    StepStatus,
    utcnow,
)

log = logging.getLogger("product_factory.spine")


class GateRequired(Exception):
    """Raised by a step that needs a human decision before it can finish."""

    def __init__(
        self, *, stage: int, title: str, payload: dict[str, Any] | None = None
    ) -> None:
        super().__init__(title)
        self.stage = stage
        self.title = title
        self.payload = payload or {}


class GateRejected(Exception):
    """The operator said no. Terminal for this run, not an error condition."""


class StepFailed(Exception):
    pass


@dataclass
class StepContext:
    """What a step sees. `session` is live inside the step's transaction;
    everything a step wants to survive must be returned or written through it."""

    run_id: str
    step_name: str
    session: Session
    context: dict[str, Any]
    outputs: dict[str, dict[str, Any]]
    gate_decision: dict[str, Any] | None = None
    attempt: int = 1

    def output_of(self, step_name: str) -> dict[str, Any]:
        try:
            return self.outputs[step_name]
        except KeyError as exc:
            raise StepFailed(
                f"step {self.step_name!r} needs output of {step_name!r}, "
                "which has not run"
            ) from exc


StepFn = Callable[[StepContext], dict[str, Any] | None]


@dataclass
class Step:
    name: str
    fn: StepFn
    #  Stages 2, 4 and 6 in the build spec. A gated step is expected to raise
    #  GateRequired on its first pass and consume ctx.gate_decision on the next.
    gated: bool = False
    max_attempts: int = 3
    retry_backoff_seconds: float = 2.0


@dataclass
class Workflow:
    name: str
    steps: list[Step] = field(default_factory=list)

    def step(
        self, name: str, *, gated: bool = False, max_attempts: int = 3
    ) -> Callable[[StepFn], StepFn]:
        def decorator(fn: StepFn) -> StepFn:
            self.steps.append(
                Step(name=name, fn=fn, gated=gated, max_attempts=max_attempts)
            )
            return fn

        return decorator

    def find(self, name: str) -> Step | None:
        return next((s for s in self.steps if s.name == name), None)


_REGISTRY: dict[str, Workflow] = {}


def register(workflow: Workflow) -> Workflow:
    _REGISTRY[workflow.name] = workflow
    return workflow


def get_workflow(name: str) -> Workflow:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(
            f"unknown workflow {name!r}; registered: {sorted(_REGISTRY)}"
        ) from exc


def registered() -> Iterable[str]:
    return sorted(_REGISTRY)


# --------------------------------------------------------------------------- #


def start_run(
    workflow_name: str,
    *,
    niche_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    get_workflow(workflow_name)  # fail fast on a typo
    with session_scope() as sess:
        run = Run(
            workflow=workflow_name,
            niche_id=niche_id,
            context=context or {},
            status=RunStatus.PENDING.value,
        )
        sess.add(run)
        sess.flush()
        return run.id


def _load_outputs(sess: Session, run_id: str) -> dict[str, dict[str, Any]]:
    rows = sess.scalars(
        select(RunStep)
        .where(RunStep.run_id == run_id, RunStep.status == StepStatus.SUCCEEDED.value)
        .order_by(RunStep.sequence)
    ).all()
    return {row.name: (row.output or {}) for row in rows}


def _upsert_step(sess: Session, run_id: str, name: str, sequence: int) -> RunStep:
    row = sess.scalar(
        select(RunStep).where(RunStep.run_id == run_id, RunStep.name == name)
    )
    if row is None:
        row = RunStep(run_id=run_id, name=name, sequence=sequence)
        sess.add(row)
        sess.flush()
    return row


def resume_run(run_id: str) -> str:
    """Execute a run from wherever it stopped. Safe to call repeatedly — that
    is the whole design. Returns the run's terminal-or-parked status."""

    with session_scope() as sess:
        run = sess.get(Run, run_id)
        if run is None:
            raise KeyError(f"no such run {run_id!r}")
        workflow = get_workflow(run.workflow)
        if run.status in {RunStatus.SUCCEEDED.value, RunStatus.CANCELLED.value}:
            return run.status
        run.status = RunStatus.RUNNING.value
        run.started_at = run.started_at or utcnow()
        run.error = None
        context = dict(run.context or {})

    for sequence, step in enumerate(workflow.steps):
        status = _execute_step(run_id, workflow, step, sequence, context)
        if status is not StepStatus.SUCCEEDED:
            with session_scope() as sess:
                run = sess.get(Run, run_id)
                assert run is not None
                return run.status

    with session_scope() as sess:
        run = sess.get(Run, run_id)
        assert run is not None
        run.status = RunStatus.SUCCEEDED.value
        run.finished_at = utcnow()
        return run.status


def _execute_step(
    run_id: str,
    workflow: Workflow,
    step: Step,
    sequence: int,
    context: dict[str, Any],
) -> StepStatus:
    with session_scope() as sess:
        row = _upsert_step(sess, run_id, step.name, sequence)
        if row.status == StepStatus.SUCCEEDED.value:
            return StepStatus.SUCCEEDED
        if row.status == StepStatus.SKIPPED.value:
            return StepStatus.SUCCEEDED

    attempt = 0
    while True:
        attempt += 1
        try:
            with session_scope() as sess:
                row = _upsert_step(sess, run_id, step.name, sequence)
                row.status = StepStatus.RUNNING.value
                row.attempt = attempt
                row.started_at = row.started_at or utcnow()

                gate_decision = None
                if step.gated:
                    gate = sess.scalar(
                        select(Gate).where(
                            Gate.run_id == run_id, Gate.step_name == step.name
                        )
                    )
                    if gate is not None:
                        if gate.status == GateStatus.OPEN.value:
                            _park(sess, run_id, step.name)
                            return StepStatus.PENDING
                        if gate.status == GateStatus.REJECTED.value:
                            raise GateRejected(gate.decision.get("reason", "rejected"))
                        gate_decision = dict(gate.decision or {})

                ctx = StepContext(
                    run_id=run_id,
                    step_name=step.name,
                    session=sess,
                    context=context,
                    outputs=_load_outputs(sess, run_id),
                    gate_decision=gate_decision,
                    attempt=attempt,
                )
                started = time.monotonic()
                output = step.fn(ctx) or {}
                row = _upsert_step(sess, run_id, step.name, sequence)
                row.output = output
                row.status = StepStatus.SUCCEEDED.value
                row.finished_at = utcnow()
                run = sess.get(Run, run_id)
                assert run is not None
                # Steps may enrich the shared context; persist it so a resume
                # after a crash sees the same view.
                run.context = dict(ctx.context)
                log.info(
                    "step %s/%s ok in %.1fs",
                    run_id,
                    step.name,
                    time.monotonic() - started,
                )
            return StepStatus.SUCCEEDED

        except GateRequired as gate_req:
            with session_scope() as sess:
                existing = sess.scalar(
                    select(Gate).where(
                        Gate.run_id == run_id, Gate.step_name == step.name
                    )
                )
                if existing is None:
                    sess.add(
                        Gate(
                            run_id=run_id,
                            step_name=step.name,
                            stage=gate_req.stage,
                            title=gate_req.title,
                            payload=gate_req.payload,
                        )
                    )
                _park(sess, run_id, step.name)
            log.info("run %s parked at gate %s", run_id, step.name)
            return StepStatus.PENDING

        except GateRejected as rej:
            with session_scope() as sess:
                row = _upsert_step(sess, run_id, step.name, sequence)
                row.status = StepStatus.SKIPPED.value
                row.error = str(rej)
                row.finished_at = utcnow()
                run = sess.get(Run, run_id)
                assert run is not None
                run.status = RunStatus.CANCELLED.value
                run.error = f"gate {step.name} rejected: {rej}"
                run.finished_at = utcnow()
            return StepStatus.SKIPPED

        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised or retried
            detail = traceback.format_exc(limit=8)
            log.warning("step %s/%s attempt %s failed: %s", run_id, step.name, attempt, exc)
            with session_scope() as sess:
                row = _upsert_step(sess, run_id, step.name, sequence)
                row.error = detail
                if attempt >= step.max_attempts:
                    row.status = StepStatus.FAILED.value
                    row.finished_at = utcnow()
                    run = sess.get(Run, run_id)
                    assert run is not None
                    run.status = RunStatus.FAILED.value
                    run.error = f"{step.name}: {exc}"
                    run.finished_at = utcnow()
                else:
                    row.status = StepStatus.PENDING.value
            if attempt >= step.max_attempts:
                return StepStatus.FAILED
            time.sleep(step.retry_backoff_seconds * (2 ** (attempt - 1)))


def _park(sess: Session, run_id: str, step_name: str) -> None:
    run = sess.get(Run, run_id)
    assert run is not None
    run.status = RunStatus.AWAITING_GATE.value
    row = sess.scalar(
        select(RunStep).where(RunStep.run_id == run_id, RunStep.name == step_name)
    )
    if row is not None:
        row.status = StepStatus.PENDING.value


# --------------------------------------------------------------------------- #
# Gate decisions
# --------------------------------------------------------------------------- #


def decide_gate(
    gate_id: str,
    *,
    approved: bool,
    decision: dict[str, Any] | None = None,
    operator: str = "operator",
) -> str:
    """Record an operator decision and return the run id, ready to resume."""
    with session_scope() as sess:
        gate = sess.get(Gate, gate_id)
        if gate is None:
            raise KeyError(f"no such gate {gate_id!r}")
        if gate.status != GateStatus.OPEN.value:
            raise ValueError(f"gate {gate_id} already {gate.status}")
        gate.status = (
            GateStatus.APPROVED.value if approved else GateStatus.REJECTED.value
        )
        gate.decision = decision or {}
        gate.decided_by = operator
        gate.decided_at = utcnow()
        return gate.run_id


def open_gates() -> list[dict[str, Any]]:
    with session_scope() as sess:
        rows = sess.scalars(
            select(Gate)
            .where(Gate.status == GateStatus.OPEN.value)
            .order_by(Gate.created_at)
        ).all()
        return [
            {
                "id": g.id,
                "run_id": g.run_id,
                "stage": g.stage,
                "step_name": g.step_name,
                "title": g.title,
                "payload": g.payload,
                "created_at": g.created_at.isoformat(),
            }
            for g in rows
        ]
