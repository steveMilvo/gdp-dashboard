"""Template products: schema -> worked example -> blank -> usage guide.

The order matters. Defining the schema first means the worked example and the
blank are provably the same shape (see `check_schema_parity`), and the usage
guide is written against a schema that already exists rather than describing
fields the buyer won't find.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..llm import client as llm

SCHEMA_DEF: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "file_format": {"type": "string", "enum": ["csv", "json"]},
        "description": {"type": "string"},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["string", "number", "date", "boolean", "enum"],
                    },
                    "help": {"type": "string"},
                },
                "required": ["key", "label", "type", "help"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["name", "file_format", "description", "fields"],
    "additionalProperties": False,
}

TEMPLATES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "templates": {"type": "array", "items": SCHEMA_DEF},
    },
    "required": ["templates"],
    "additionalProperties": False,
}

EXAMPLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": {"type": "string"}},
        }
    },
    "required": ["rows"],
    "additionalProperties": False,
}

GUIDE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["heading", "body"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "sections"],
    "additionalProperties": False,
}


@dataclass
class TemplatePackResult:
    directory: Path
    files: list[Path]
    pairs: list[tuple[Path, Path]]  # (populated, blank)
    guide_path: Path
    guide_text: str


def build(
    *,
    output_dir: Path,
    slug: str,
    promise: str,
    target_buyer: str,
    signals: list[dict[str, str]],
    session: Any = None,
    run_id: str | None = None,
    step_name: str | None = None,
    product_id: str | None = None,
    template_count: int = 4,
) -> TemplatePackResult:
    pack_dir = output_dir / slug
    (pack_dir / "examples").mkdir(parents=True, exist_ok=True)
    (pack_dir / "blank").mkdir(parents=True, exist_ok=True)

    schemas = llm.complete_json(
        prompt_name="template_schema",
        variables={
            "promise": promise,
            "target_buyer": target_buyer,
            "template_count": template_count,
            "signals": "\n".join(
                f"- {s['normalised']} (verbatim: \"{s['quote']}\")" for s in signals
            ),
        },
        schema=TEMPLATES_SCHEMA,
        agent="artifact_builder.template",
        run_id=run_id,
        step_name=step_name,
        product_id=product_id,
        session=session,
    )["templates"][:template_count]

    files: list[Path] = []
    pairs: list[tuple[Path, Path]] = []

    for spec in schemas:
        keys = [f["key"] for f in spec["fields"]]
        stem = _slugify(spec["name"])
        fmt = spec["file_format"]

        example = llm.complete_json(
            prompt_name="template_example",
            variables={
                "template_name": spec["name"],
                "description": spec["description"],
                "target_buyer": target_buyer,
                "fields": "\n".join(
                    f"- {f['key']} ({f['type']}): {f['help']}" for f in spec["fields"]
                ),
            },
            schema=EXAMPLE_SCHEMA,
            agent="artifact_builder.template",
            run_id=run_id,
            step_name=step_name,
            product_id=product_id,
            session=session,
        )
        rows = [{k: str(row.get(k, "")) for k in keys} for row in example["rows"]]

        populated = pack_dir / "examples" / f"{stem}.{fmt}"
        blank = pack_dir / "blank" / f"{stem}.{fmt}"
        _write(populated, fmt, keys, rows)
        _write(blank, fmt, keys, [])
        files.extend([populated, blank])
        pairs.append((populated, blank))

    guide = llm.complete_json(
        prompt_name="template_guide",
        variables={
            "promise": promise,
            "target_buyer": target_buyer,
            "templates": "\n".join(
                f"- {s['name']} ({s['file_format']}): {s['description']}\n"
                + "\n".join(f"    * {f['key']}: {f['help']}" for f in s["fields"])
                for s in schemas
            ),
        },
        schema=GUIDE_SCHEMA,
        agent="artifact_builder.template",
        run_id=run_id,
        step_name=step_name,
        product_id=product_id,
        session=session,
    )
    guide_text = f"# {guide['title']}\n\n" + "\n\n".join(
        f"## {s['heading']}\n\n{s['body']}" for s in guide["sections"]
    )
    guide_path = pack_dir / "USAGE.md"
    guide_path.write_text(guide_text, encoding="utf-8")
    files.append(guide_path)

    return TemplatePackResult(
        directory=pack_dir,
        files=files,
        pairs=pairs,
        guide_path=guide_path,
        guide_text=guide_text,
    )


def _write(path: Path, fmt: str, keys: list[str], rows: list[dict[str, str]]) -> None:
    if fmt == "csv":
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
    else:
        # A blank JSON template still carries one all-empty record so the
        # buyer can see the field names — an empty array teaches nothing.
        payload = rows or [{k: "" for k in keys}]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _slugify(name: str) -> str:
    return "-".join(
        part for part in "".join(
            c.lower() if c.isalnum() else " " for c in name
        ).split()
    ) or "template"
