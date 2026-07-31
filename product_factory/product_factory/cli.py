"""Command-line entrypoints.

    python -m product_factory.cli init
    python -m product_factory.cli niche "AU sole traders drowning in BAS prep" --keyword bas --keyword gst
    python -m product_factory.cli run full_cycle --niche nch_... --set success_threshold=25
    python -m product_factory.cli gates
    python -m product_factory.cli approve <gate_id> --set candidate_id=offr_...
    python -m product_factory.cli resume <run_id>
    python -m product_factory.cli report <niche_id>
    python -m product_factory.cli economics
    python -m product_factory.cli attribution [order_id]
    python -m product_factory.cli apps

argparse rather than a CLI framework: this is an operator tool with nine verbs,
and a dependency-free entrypoint is one fewer thing to break on a fresh host.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from .agents.signal_loop import funnel_summary
from .attribution import all_chains, chain_for_order, revenue_by_signal, unit_economics
from .db import init_db, session_scope
from .llm.pricing import format_microcents
from .models import Niche
from .orchestrator import spine, workflows  # noqa: F401 - registers workflows


def _kv(pairs: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for pair in pairs or []:
        key, _, raw = pair.partition("=")
        try:
            out[key] = json.loads(raw)
        except json.JSONDecodeError:
            out[key] = raw
    return out


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(prog="product_factory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the database schema")

    p_niche = sub.add_parser("niche", help="register a niche hypothesis")
    p_niche.add_argument("hypothesis")
    p_niche.add_argument("--keyword", action="append", default=[])

    p_run = sub.add_parser("run", help="start and execute a workflow")
    p_run.add_argument("workflow", choices=list(spine.registered()))
    p_run.add_argument("--niche")
    p_run.add_argument("--set", action="append", dest="context", default=[])

    sub.add_parser("gates", help="list open approval gates")

    p_approve = sub.add_parser("approve", help="approve a gate and resume the run")
    p_approve.add_argument("gate_id")
    p_approve.add_argument("--set", action="append", dest="decision", default=[])

    p_reject = sub.add_parser("reject", help="reject a gate")
    p_reject.add_argument("gate_id")
    p_reject.add_argument("--reason", default="rejected by operator")

    p_resume = sub.add_parser("resume", help="resume a parked or failed run")
    p_resume.add_argument("run_id")

    p_report = sub.add_parser("report", help="weekly signal report for a niche")
    p_report.add_argument("niche_id")

    sub.add_parser("economics", help="per-product build cost from the invocation log")

    p_attr = sub.add_parser("attribution", help="the full attribution chain")
    p_attr.add_argument("order_id", nargs="?")

    sub.add_parser("apps", help="deployed micro-app status")

    args = parser.parse_args(argv)

    if args.command == "init":
        init_db()
        print("schema created")
        return 0

    init_db()

    if args.command == "niche":
        with session_scope() as sess:
            niche = Niche(hypothesis=args.hypothesis, seed_keywords=args.keyword)
            sess.add(niche)
            sess.flush()
            print(niche.id)
        return 0

    if args.command == "run":
        context = _kv(args.context)
        if args.niche:
            context["niche_id"] = args.niche
        run_id = spine.start_run(args.workflow, niche_id=args.niche, context=context)
        status = spine.resume_run(run_id)
        _print({"run_id": run_id, "status": status})
        return 0

    if args.command == "gates":
        _print(spine.open_gates())
        return 0

    if args.command == "approve":
        run_id = spine.decide_gate(
            args.gate_id, approved=True, decision=_kv(args.decision)
        )
        _print({"run_id": run_id, "status": spine.resume_run(run_id)})
        return 0

    if args.command == "reject":
        run_id = spine.decide_gate(
            args.gate_id, approved=False, decision={"reason": args.reason}
        )
        _print({"run_id": run_id, "status": spine.resume_run(run_id)})
        return 0

    if args.command == "resume":
        _print({"run_id": args.run_id, "status": spine.resume_run(args.run_id)})
        return 0

    if args.command == "report":
        with session_scope() as sess:
            _print(
                {
                    "revenue_by_signal": revenue_by_signal(sess, args.niche_id),
                    "funnel": funnel_summary(sess, args.niche_id),
                }
            )
        return 0

    if args.command == "economics":
        with session_scope() as sess:
            rows = unit_economics(sess)
        for row in rows:
            row["build_cost"] = format_microcents(int(row["build_cost_microcents"]))
        _print(rows)
        return 0

    if args.command == "attribution":
        with session_scope() as sess:
            _print(
                chain_for_order(sess, args.order_id)
                if args.order_id
                else all_chains(sess)
            )
        return 0

    if args.command == "apps":
        from .builders.deploy import status

        _print([app.__dict__ for app in status()])
        return 0

    parser.error(f"unhandled command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
