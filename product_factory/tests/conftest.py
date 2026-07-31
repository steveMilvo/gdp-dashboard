"""Test harness.

Two pieces do the heavy lifting:

* **Source fixtures** — captured-looking rows across five source kinds, written
  to a temp directory that `PF_FIXTURES_DIR` points at. Recurrence is encoded
  in the URLs so the same problem genuinely recurs across independent kinds,
  which is what the demand miner's core rule is supposed to detect.
* **A stub LLM responder** — deterministic, schema-shaped answers keyed by
  prompt name. It lets the whole pipeline run end to end with no API key and no
  spend, which is the only way the acceptance criteria are actually checkable
  in CI rather than asserted in a README.

The stub is honest about the one thing that matters: it produces *verbatim*
quotes taken from the fixture text, so the demand miner's anti-hallucination
check is exercised rather than bypassed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# Problems that recur, with the source kinds each is seen in. Two of these
# clear the recurrence bar; two deliberately do not.
PROBLEMS = {
    "reconcile-stripe-fees": {
        "kinds": ["reddit", "forum", "review", "youtube"],
        "per_kind": 2,
        "quote": (
            "Every month I spend two whole evenings trying to work out which "
            "Stripe payout maps to which invoice, and the fees never line up "
            "with what my accountant expects."
        ),
    },
    "chase-late-invoices": {
        "kinds": ["reddit", "review", "marketplace"],
        "per_kind": 2,
        "quote": (
            "I have eleven invoices past sixty days and no system for chasing "
            "them, so I just avoid it until rent is due and then panic."
        ),
    },
    "quote-jobs-accurately": {
        "kinds": ["reddit", "forum"],
        "per_kind": 2,
        "quote": (
            "I keep underquoting fixed-price jobs because I guess the hours "
            "instead of measuring them, and I eat the difference every time."
        ),
    },
    # Recurs often, but only in one source kind — must be rejected.
    "single-source-noise": {
        "kinds": ["reddit"],
        "per_kind": 5,
        "quote": (
            "Honestly the worst part of this whole business is the software "
            "subscriptions stacking up month after month with no warning."
        ),
    },
    # Articulate, but seen once — must be rejected.
    "one-off-complaint": {
        "kinds": ["forum"],
        "per_kind": 1,
        "quote": (
            "The single most frustrating thing is that nobody explains what a "
            "reconciliation actually is before they sell you the software."
        ),
    },
}


def _fixture_payload() -> dict[str, list[dict[str, Any]]]:
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for key, spec in PROBLEMS.items():
        for kind in spec["kinds"]:
            for index in range(spec["per_kind"]):
                by_kind.setdefault(kind, []).append(
                    {
                        "url": f"https://example.test/{kind}/{key}/{index}",
                        "title": key.replace("-", " ").title(),
                        "author": f"user{index}",
                        "text": (
                            f"{spec['quote']} I have tried a few things and "
                            f"nothing has stuck ({kind} thread {index})."
                        ),
                        "meta": {"sales": 500, "rating": 3.1},
                    }
                )
    return by_kind


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory) -> Path:
    directory = tmp_path_factory.mktemp("source_fixtures")
    for kind, items in _fixture_payload().items():
        # "*" means "any query" — the miner queries per keyword and we want
        # every keyword to return the same captured corpus.
        (directory / f"{kind}.json").write_text(
            json.dumps({"*": items}), encoding="utf-8"
        )
    return directory


@pytest.fixture(autouse=True)
def factory_env(tmp_path, fixtures_dir, monkeypatch):
    """Isolate every test: its own database, artifacts dir and app dir."""
    monkeypatch.setenv("PF_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("PF_DATA_REGION", "ap-southeast-2")
    monkeypatch.setenv("PF_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("PF_APPS_DIR", str(tmp_path / "apps"))
    monkeypatch.setenv("PF_FIXTURES_DIR", str(fixtures_dir))
    monkeypatch.setenv("PF_BASE_URL", "http://testserver")
    monkeypatch.setenv("PF_OPERATOR_TOKEN", "test-operator-token")
    monkeypatch.setenv("PF_ALLOW_TEST_CHECKOUT", "1")
    monkeypatch.setenv(
        "PF_PROMPTS_DIR",
        str(Path(__file__).resolve().parent.parent / "prompts"),
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from product_factory import config, db
    from product_factory.llm import prompts

    config.reset_settings()
    db.reset_engine()
    prompts.clear_cache()
    db.init_db()
    yield
    db.reset_engine()
    config.reset_settings()


# --------------------------------------------------------------------------- #
# Stub model
# --------------------------------------------------------------------------- #

_LOREM = (
    "The first thing to fix is the part of this that runs on memory rather "
    "than on a written rule. Write the rule down, put it where you will trip "
    "over it, and stop relying on remembering. Most of the cost of this "
    "problem is not the task itself but the reconstruction you do every time "
    "you come back to it after a fortnight away. That reconstruction is what "
    "you are paying for, and it is what a written procedure removes. "
)


def _paragraphs(count: int, seed: str) -> list[str]:
    return [
        f"{seed} {_LOREM}"
        + f"This is step {i + 1} of the sequence and it is where most people stop."
        for i in range(count)
    ]


def stub_responder(prompt_name: str, variables: dict[str, Any]) -> dict[str, Any]:
    handler = _HANDLERS.get(prompt_name)
    if handler is None:
        raise AssertionError(f"stub has no handler for prompt {prompt_name!r}")
    return handler(variables)


def _extract(v: dict[str, Any]) -> dict[str, Any]:
    text: str = v["text"]
    url: str = v["url"]
    key = url.split("/")[-2]
    # Verbatim: the first sentence of the fixture text, copied exactly.
    quote = text.split(". ")[0] + "."
    return {
        "signals": [
            {
                "quote": quote,
                "normalised": f"the buyer cannot {key.replace('-', ' ')} reliably",
                "wtp_tier": "mid",
                "wtp_rationale": "already paying for adjacent software",
            }
        ]
    }


def _offers(v: dict[str, Any]) -> dict[str, Any]:
    ids = [
        line.split("id=")[1].split(" ")[0]
        for line in v["signals"].splitlines()
        if "id=" in line
    ]
    if not ids:
        return {"clusters": []}
    return {
        "clusters": [
            {
                "label": "Reconciliation and chasing",
                "summary": "Money in, money owed, and the admin between them.",
                "signal_ids": ids[:3],
                "offer": {
                    "promise": "Reconcile a month of Stripe payouts in 20 minutes",
                    "target_buyer": "Australian sole traders billing through Stripe",
                    "format": "ebook",
                    "price_cents": 4900,
                    "rationale": "Recurs monthly, costs two evenings each time.",
                    "competitors": [
                        {
                            "name": "Bookkeeping Basics",
                            "url": "https://example.test/comp/1",
                            "price_cents": 7900,
                            "positioning": "General, not Stripe-specific",
                        },
                        {
                            "name": "Payout Sorter",
                            "url": "https://example.test/comp/2",
                            "price_cents": 2900,
                            "positioning": "Tool, no method",
                        },
                        {
                            "name": "The Sole Trader Course",
                            "url": "https://example.test/comp/3",
                            "price_cents": 19900,
                            "positioning": "Broad course, thin on reconciliation",
                        },
                    ],
                },
            }
        ]
    }


def _outline(v: dict[str, Any]) -> dict[str, Any]:
    ids = [
        line.split("id=")[1].split(" ")[0]
        for line in v["signals"].splitlines()
        if "id=" in line
    ] or [""]
    minimum = int(v["min_sections"])
    return {
        "title": "The Twenty Minute Reconciliation",
        "subtitle": "A monthly procedure for Stripe payouts and invoices",
        "sections": [
            {
                "heading": f"Step {i + 1}: close the loop on payouts",
                "intent": "Match one payout to its invoices without guessing.",
                "answers_signal": ids[i % len(ids)],
            }
            for i in range(minimum)
        ],
    }


def _section(v: dict[str, Any]) -> dict[str, Any]:
    return {"heading": v["heading"], "paragraphs": _paragraphs(6, v["heading"])}


def _template_schema(v: dict[str, Any]) -> dict[str, Any]:
    count = int(v["template_count"])
    return {
        "templates": [
            {
                "name": f"Reconciliation tracker {i + 1}",
                "file_format": "csv" if i % 2 == 0 else "json",
                "description": "One row per payout, reconciled against invoices.",
                "fields": [
                    {
                        "key": "payout_date",
                        "label": "Payout date",
                        "type": "date",
                        "help": "The date Stripe paid out, e.g. 2026-03-04",
                    },
                    {
                        "key": "gross_amount",
                        "label": "Gross amount",
                        "type": "number",
                        "help": "Gross before fees, e.g. 2400",
                    },
                    {
                        "key": "fees",
                        "label": "Fees",
                        "type": "number",
                        "help": "Stripe fees deducted, e.g. 41.20",
                    },
                    {
                        "key": "invoice_ids",
                        "label": "Invoice ids",
                        "type": "string",
                        "help": "Semicolon separated, e.g. INV-104;INV-105",
                    },
                    {
                        "key": "reconciled",
                        "label": "Reconciled",
                        "type": "boolean",
                        "help": "yes once the amounts agree",
                    },
                ],
            }
            for i in range(count)
        ]
    }


def _template_example(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": [
            {
                "payout_date": f"2026-03-{i + 1:02d}",
                "gross_amount": str(1000 + i * 137),
                "fees": f"{18.4 + i:.2f}",
                "invoice_ids": f"INV-{100 + i};INV-{200 + i}",
                "reconciled": "yes",
            }
            for i in range(6)
        ]
    }


def _template_guide(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "How to run the monthly reconciliation",
        "sections": [
            {"heading": f"Week {i + 1}", "body": " ".join(_paragraphs(4, "Week"))}
            for i in range(4)
        ],
    }


def _app_spec(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "Payout Reconciler",
        "one_liner": "Work out what a Stripe payout should have been.",
        "primary_flow": "Enter gross, fee rate and invoice count; get the expected net.",
        "inputs": [
            {"key": "gross", "label": "Gross amount", "type": "number", "options": []},
            {
                "key": "fee_percent",
                "label": "Fee percent",
                "type": "number",
                "options": [],
            },
            {
                "key": "invoices",
                "label": "Invoice count",
                "type": "number",
                "options": [],
            },
        ],
        "output_description": "Expected net payout and per-invoice share.",
        "requires_auth": False,
    }


def _app_compute(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "compute_source": (
            "def compute(payload: dict) -> dict:\n"
            "    try:\n"
            "        gross = float(payload.get('gross') or 0)\n"
            "        fee_percent = float(payload.get('fee_percent') or 0)\n"
            "        invoices = int(float(payload.get('invoices') or 0))\n"
            "    except (TypeError, ValueError):\n"
            "        raise ValueError('Enter numbers for gross, fee percent and invoices.')\n"
            "    fees = round(gross * fee_percent / 100.0, 2)\n"
            "    net = round(gross - fees, 2)\n"
            "    share = round(net / invoices, 2) if invoices else 0.0\n"
            "    return {\n"
            "        'gross': gross,\n"
            "        'fees': fees,\n"
            "        'net': net,\n"
            "        'per_invoice': share,\n"
            "        'summary': 'Expected net ' + str(net) + ' after ' + str(fees) + ' in fees.',\n"
            "    }\n"
        ),
        "notes": "Pure arithmetic, no dependencies.",
    }


def _course_map(v: dict[str, Any]) -> dict[str, Any]:
    ids = [
        line.split("id=")[1].split(" ")[0]
        for line in v["signals"].splitlines()
        if "id=" in line
    ] or [""]
    count = int(v["module_count"])
    return {
        "title": "Reconciliation in practice",
        "outcome": "Close a month of payouts in one sitting.",
        "modules": [
            {
                "title": f"Module {m + 1}",
                "objective": "Move from guessing to measuring.",
                "lessons": [
                    {
                        "title": f"Lesson {m + 1}.{n + 1}",
                        "takeaway": "Match one payout end to end.",
                        "answers_signal": ids[(m + n) % len(ids)],
                    }
                    for n in range(3)
                ],
            }
            for m in range(count)
        ],
    }


def _course_lesson(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "script": " ".join(_paragraphs(4, v["lesson_title"])),
        "slides": [
            {
                "headline": f"{v['lesson_title']} — part {i + 1}",
                "bullets": ["Measure the hours", "Write the rule down", "Repeat monthly"],
            }
            for i in range(3)
        ],
    }


def _listing(v: dict[str, Any]) -> dict[str, Any]:
    objections = [
        line[2:] for line in v["objections"].splitlines() if line.startswith("- ")
    ]
    return {
        "title": "The Twenty Minute Reconciliation",
        "lede": "A monthly procedure for Stripe payouts and invoices.",
        "what_you_get": [
            "A written monthly procedure",
            "The reconciliation checklist",
            "The three failure modes and their fixes",
        ],
        "objection_answers": [
            {"objection": o, "answer": "Here is the straight answer to that."}
            for o in objections
        ]
        or [
            {
                "objection": "Can I not just ask my accountant?",
                "answer": "You can, and they will bill you for it monthly.",
            }
        ],
        "who_its_not_for": "Businesses with a bookkeeper already doing this.",
    }


def _content(v: dict[str, Any]) -> dict[str, Any]:
    count = int(v["count"])
    # Hooks reuse distinctive vocabulary from the quote, which is what the
    # deterministic half of the specificity rule checks for.
    quote_words = [w for w in v["quote"].lower().split() if len(w) > 6][:4]
    salient = " ".join(quote_words) or "reconciliation payouts"
    platforms = ["tiktok", "reddit", "linkedin", "x"]
    return {
        "pieces": [
            {
                "platform": platforms[i % len(platforms)],
                "distribution": "direct_reply" if i % 2 == 0 else "broadcast",
                "hook": f"Two evenings on {salient} is not a discipline problem",
                "body": " ".join(_paragraphs(2, "Body")),
                "cta": "What does your current month-end actually look like?",
                "format_notes": "Talking head, text on screen for the numbers.",
            }
            for i in range(count)
        ]
    }


def _judge(v: dict[str, Any]) -> dict[str, Any]:
    hooks = [line for line in v["hooks"].splitlines() if line.strip()]
    return {
        "verdicts": [
            {
                "index": i,
                # The stub marks anything containing "generic" as generic, so
                # tests can drive both branches of the rule.
                "generic": "generic" in hook.lower(),
                "score": 0.2 if "generic" in hook.lower() else 0.86,
                "reason": "names the specific situation" ,
            }
            for i, hook in enumerate(hooks)
        ]
    }


def _landing(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "headline": "Stop losing two evenings a month to Stripe payouts",
        "subhead": "A written monthly procedure, for sole traders billing through Stripe.",
        "problem_paragraphs": _paragraphs(3, "Problem"),
        "what_it_is": ["A procedure", "A checklist", "Three worked examples"],
        "cta_label": "Tell me when it's ready",
        "price_framing": "Less than one hour of your accountant",
    }


def _outreach(v: dict[str, Any]) -> dict[str, Any]:
    ids = [
        line.split("id=")[1].split(" ")[0]
        for line in v["signals"].splitlines()
        if "id=" in line
    ] or [""]
    count = int(v["count"])
    channels = ["dm", "comment_reply", "email"]
    return {
        "variants": [
            {
                "pain_signal_id": ids[i % len(ids)],
                "channel": channels[i % len(channels)],
                "body": "You mentioned the payout matching taking two evenings. "
                "Is that still how it goes, or did you find something?",
            }
            for i in range(count)
        ]
    }


def _objections(v: dict[str, Any]) -> dict[str, Any]:
    replies = [
        line[2:] for line in v["replies"].splitlines() if line.startswith("- ")
    ]
    return {
        "objections": [
            {
                "text": reply,
                "theme": "cost",
                "rebuttal": "Honest answer, including who this is not for.",
            }
            for reply in replies
        ]
    }


def _patterns(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "patterns": [
            {
                "pattern": "Hooks naming a unit of time outperformed",
                "evidence": "Both revenue-producing hooks led with 'two evenings'",
                "action": "Lead with the cost in hours, not the outcome",
            }
        ],
        "narrative": "Small sample. One pattern is defensible; the rest is noise.",
    }


_HANDLERS = {
    "demand_miner_extract": _extract,
    "offer_synthesiser": _offers,
    "document_outline": _outline,
    "document_section": _section,
    "template_schema": _template_schema,
    "template_example": _template_example,
    "template_guide": _template_guide,
    "micro_app_spec": _app_spec,
    "micro_app_compute": _app_compute,
    "course_map": _course_map,
    "course_lesson": _course_lesson,
    "listing_copy": _listing,
    "content_pieces": _content,
    "content_specificity_judge": _judge,
    "validation_landing": _landing,
    "validation_outreach": _outreach,
    "validation_objections": _objections,
    "signal_loop_patterns": _patterns,
}


@pytest.fixture(autouse=True)
def stub_llm():
    from product_factory.llm import client

    client.set_stub_responder(stub_responder)
    yield
    client.set_stub_responder(None)
