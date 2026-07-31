"""Document products: outline -> section drafts -> assembled PDF with cover.

Two-pass generation on purpose. Asking for a whole ebook in one call gets you
something that drifts and repeats; asking for an outline first and then
drafting each section against that outline plus the section list keeps the
structure coherent and makes a failed section retryable on its own.

The cover is generated typographically with ReportLab rather than fetched from
an image service — no external dependency, deterministic output, and it renders
identically on the storefront thumbnail and inside the PDF.
"""

from __future__ import annotations

import hashlib
import logging
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from ..llm import client as llm

log = logging.getLogger("product_factory.builders.document")

OUTLINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "intent": {
                        "type": "string",
                        "description": "What the reader can do after this "
                        "section that they could not do before it.",
                    },
                    "answers_signal": {
                        "type": "string",
                        "description": "The pain signal id this section answers.",
                    },
                },
                "required": ["heading", "intent", "answers_signal"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "subtitle", "sections"],
    "additionalProperties": False,
}

SECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "heading": {"type": "string"},
        "paragraphs": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["heading", "paragraphs"],
    "additionalProperties": False,
}

_PALETTE = [
    (colors.HexColor("#12263A"), colors.HexColor("#F4D35E")),
    (colors.HexColor("#22333B"), colors.HexColor("#EAE0D5")),
    (colors.HexColor("#3D348B"), colors.HexColor("#F7B801")),
    (colors.HexColor("#004E64"), colors.HexColor("#00A5CF")),
    (colors.HexColor("#4A1942"), colors.HexColor("#F2C078")),
]


@dataclass
class DocumentResult:
    pdf_path: Path
    cover_path: Path
    title: str
    full_text: str
    sections: list[dict[str, Any]] = field(default_factory=list)


def build(
    *,
    output_dir: Path,
    slug: str,
    promise: str,
    target_buyer: str,
    signals: list[dict[str, str]],
    objections: list[str],
    session: Any = None,
    run_id: str | None = None,
    step_name: str | None = None,
    product_id: str | None = None,
    min_sections: int = 7,
) -> DocumentResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    outline = llm.complete_json(
        prompt_name="document_outline",
        variables={
            "promise": promise,
            "target_buyer": target_buyer,
            "min_sections": min_sections,
            "signals": _render_signals(signals),
            "objections": "\n".join(f"- {o}" for o in objections) or "(none captured)",
        },
        schema=OUTLINE_SCHEMA,
        agent="artifact_builder.document",
        run_id=run_id,
        step_name=step_name,
        product_id=product_id,
        session=session,
    )

    headings = [s["heading"] for s in outline["sections"]]
    drafted: list[dict[str, Any]] = []
    for index, section in enumerate(outline["sections"]):
        draft = llm.complete_json(
            prompt_name="document_section",
            variables={
                "title": outline["title"],
                "promise": promise,
                "target_buyer": target_buyer,
                "heading": section["heading"],
                "intent": section["intent"],
                "position": f"{index + 1} of {len(outline['sections'])}",
                "all_headings": "\n".join(f"{i+1}. {h}" for i, h in enumerate(headings)),
                "signal": _signal_text(signals, section.get("answers_signal")),
            },
            schema=SECTION_SCHEMA,
            agent="artifact_builder.document",
            run_id=run_id,
            step_name=step_name,
            product_id=product_id,
            session=session,
        )
        drafted.append(
            {
                "heading": draft["heading"],
                "paragraphs": [p for p in draft["paragraphs"] if p.strip()],
                "answers_signal": section.get("answers_signal"),
            }
        )

    cover_path = output_dir / f"{slug}-cover.pdf"
    render_cover(cover_path, outline["title"], outline["subtitle"], target_buyer)

    pdf_path = output_dir / f"{slug}.pdf"
    full_text = render_pdf(
        pdf_path,
        title=outline["title"],
        subtitle=outline["subtitle"],
        sections=drafted,
    )

    return DocumentResult(
        pdf_path=pdf_path,
        cover_path=cover_path,
        title=outline["title"],
        full_text=full_text,
        sections=drafted,
    )


def _palette_for(title: str) -> tuple[colors.Color, colors.Color]:
    idx = int(hashlib.sha256(title.encode()).hexdigest(), 16) % len(_PALETTE)
    return _PALETTE[idx]


def render_cover(path: Path, title: str, subtitle: str, audience: str) -> Path:
    """A typographic cover. Deterministic from the title so a rebuild produces
    the same asset rather than churning the storefront thumbnail."""
    bg, accent = _palette_for(title)
    width, height = A4
    c = pdfcanvas.Canvas(str(path), pagesize=A4)
    c.setFillColor(bg)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    c.setFillColor(accent)
    c.rect(0, height - 18 * mm, width, 18 * mm, fill=1, stroke=0)
    c.rect(0, 0, width, 8 * mm, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 34)
    y = height - 90 * mm
    for line in textwrap.wrap(title, 22)[:4]:
        c.drawString(22 * mm, y, line)
        y -= 15 * mm

    c.setFillColor(accent)
    c.setFont("Helvetica", 15)
    y -= 6 * mm
    for line in textwrap.wrap(subtitle, 44)[:3]:
        c.drawString(22 * mm, y, line)
        y -= 8 * mm

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Oblique", 11)
    c.drawString(22 * mm, 24 * mm, f"For {audience}")
    c.showPage()
    c.save()
    return path


def render_pdf(
    path: Path, *, title: str, subtitle: str, sections: list[dict[str, Any]]
) -> str:
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "PFBody",
        parent=styles["BodyText"],
        fontSize=11,
        leading=16.5,
        spaceAfter=8,
        alignment=TA_JUSTIFY,
    )
    h1 = ParagraphStyle(
        "PFH1", parent=styles["Heading1"], fontSize=20, spaceAfter=12, spaceBefore=4
    )
    title_style = ParagraphStyle(
        "PFTitle", parent=styles["Title"], fontSize=28, leading=34
    )

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        title=title,
        author="Product Factory",
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=24 * mm,
        bottomMargin=22 * mm,
    )

    flow: list[Any] = [
        Spacer(1, 45 * mm),
        Paragraph(_esc(title), title_style),
        Spacer(1, 6 * mm),
        Paragraph(_esc(subtitle), styles["Heading3"]),
        PageBreak(),
        Paragraph("Contents", h1),
    ]
    for index, section in enumerate(sections, start=1):
        flow.append(Paragraph(f"{index}. {_esc(section['heading'])}", body))
    flow.append(PageBreak())

    text_parts = [title, subtitle]
    for section in sections:
        flow.append(Paragraph(_esc(section["heading"]), h1))
        text_parts.append(section["heading"])
        for para in section["paragraphs"]:
            flow.append(Paragraph(_esc(para), body))
            text_parts.append(para)
        flow.append(PageBreak())

    doc.build(flow)
    return "\n\n".join(text_parts)


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _render_signals(signals: list[dict[str, str]]) -> str:
    return "\n".join(
        f"- id={s['id']} | {s['normalised']}\n  verbatim: \"{s['quote']}\""
        for s in signals
    )


def _signal_text(signals: list[dict[str, str]], signal_id: str | None) -> str:
    for signal in signals:
        if signal["id"] == signal_id:
            return f"{signal['normalised']} — verbatim: \"{signal['quote']}\""
    return "(no specific signal assigned; write to the overall promise)"
