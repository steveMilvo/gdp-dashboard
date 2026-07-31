"""Course products: module map -> lesson scripts -> slide assets.

Slides are generated as a PDF deck per module rather than PPTX. A course buyer
opens the deck; they rarely edit it, and a PDF renders identically everywhere
without a template dependency.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

from ..llm import client as llm

SLIDE_SIZE = (254 * mm, 143 * mm)  # 16:9

MAP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "outcome": {
            "type": "string",
            "description": "What the student can do at the end that they could "
            "not do at the start.",
        },
        "modules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "objective": {"type": "string"},
                    "lessons": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "takeaway": {"type": "string"},
                                "answers_signal": {"type": "string"},
                            },
                            "required": ["title", "takeaway", "answers_signal"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["title", "objective", "lessons"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "outcome", "modules"],
    "additionalProperties": False,
}

LESSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "script": {
            "type": "string",
            "description": "Spoken script, first person, no stage directions.",
        },
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["headline", "bullets"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["script", "slides"],
    "additionalProperties": False,
}


@dataclass
class CourseResult:
    directory: Path
    title: str
    modules: list[dict[str, Any]]
    deck_paths: list[Path]
    script_paths: list[Path]
    full_text: str


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
    module_count: int = 4,
) -> CourseResult:
    course_dir = output_dir / slug
    (course_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (course_dir / "slides").mkdir(parents=True, exist_ok=True)

    plan = llm.complete_json(
        prompt_name="course_map",
        variables={
            "promise": promise,
            "target_buyer": target_buyer,
            "module_count": module_count,
            "signals": "\n".join(
                f"- id={s['id']} | {s['normalised']} (verbatim: \"{s['quote']}\")"
                for s in signals
            ),
        },
        schema=MAP_SCHEMA,
        agent="artifact_builder.course",
        run_id=run_id,
        step_name=step_name,
        product_id=product_id,
        session=session,
    )

    deck_paths: list[Path] = []
    script_paths: list[Path] = []
    text_parts: list[str] = [plan["title"], plan["outcome"]]
    modules: list[dict[str, Any]] = []

    for m_index, module in enumerate(plan["modules"], start=1):
        drafted_lessons = []
        for l_index, lesson in enumerate(module["lessons"], start=1):
            drafted = llm.complete_json(
                prompt_name="course_lesson",
                variables={
                    "course_title": plan["title"],
                    "module_title": module["title"],
                    "module_objective": module["objective"],
                    "lesson_title": lesson["title"],
                    "takeaway": lesson["takeaway"],
                    "target_buyer": target_buyer,
                    "signal": _signal_text(signals, lesson.get("answers_signal")),
                },
                schema=LESSON_SCHEMA,
                agent="artifact_builder.course",
                run_id=run_id,
                step_name=step_name,
                product_id=product_id,
                session=session,
            )
            drafted_lessons.append(
                {
                    "title": lesson["title"],
                    "takeaway": lesson["takeaway"],
                    "answers_signal": lesson.get("answers_signal"),
                    "script": drafted["script"],
                    "slides": drafted["slides"],
                }
            )
            script_path = (
                course_dir / "scripts" / f"m{m_index:02d}-l{l_index:02d}.md"
            )
            script_path.write_text(
                f"# {lesson['title']}\n\n_{lesson['takeaway']}_\n\n{drafted['script']}\n",
                encoding="utf-8",
            )
            script_paths.append(script_path)
            text_parts.extend([lesson["title"], drafted["script"]])

        module_record = {
            "title": module["title"],
            "objective": module["objective"],
            "lessons": drafted_lessons,
        }
        modules.append(module_record)

        deck_path = course_dir / "slides" / f"m{m_index:02d}-{_slugify(module['title'])}.pdf"
        render_deck(deck_path, plan["title"], module_record)
        deck_paths.append(deck_path)

    (course_dir / "SYLLABUS.md").write_text(
        _syllabus(plan, modules), encoding="utf-8"
    )

    return CourseResult(
        directory=course_dir,
        title=plan["title"],
        modules=modules,
        deck_paths=deck_paths,
        script_paths=script_paths,
        full_text="\n\n".join(text_parts),
    )


def render_deck(path: Path, course_title: str, module: dict[str, Any]) -> Path:
    c = pdfcanvas.Canvas(str(path), pagesize=landscape(SLIDE_SIZE))
    width, height = landscape(SLIDE_SIZE)
    bg = colors.HexColor("#12263A")
    accent = colors.HexColor("#F4D35E")

    def slide(headline: str, bullets: list[str], eyebrow: str) -> None:
        c.setFillColor(bg)
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillColor(accent)
        c.rect(0, height - 6 * mm, width, 6 * mm, fill=1, stroke=0)
        c.setFont("Helvetica", 10)
        c.drawString(18 * mm, height - 18 * mm, eyebrow.upper())
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 26)
        y = height - 36 * mm
        for line in textwrap.wrap(headline, 44)[:3]:
            c.drawString(18 * mm, y, line)
            y -= 12 * mm
        c.setFont("Helvetica", 14)
        y -= 6 * mm
        for bullet in bullets[:5]:
            for i, line in enumerate(textwrap.wrap(bullet, 78)[:2]):
                c.setFillColor(accent if i == 0 else colors.white)
                prefix = "•  " if i == 0 else "   "
                c.setFillColor(colors.white)
                c.drawString(20 * mm, y, prefix + line)
                y -= 8 * mm
            y -= 2 * mm
        c.showPage()

    slide(module["title"], [module["objective"]], course_title)
    for lesson in module["lessons"]:
        for deck_slide in lesson["slides"]:
            slide(deck_slide["headline"], deck_slide["bullets"], lesson["title"])
    c.save()
    return path


def _syllabus(plan: dict[str, Any], modules: list[dict[str, Any]]) -> str:
    lines = [f"# {plan['title']}", "", f"**Outcome:** {plan['outcome']}", ""]
    for index, module in enumerate(modules, start=1):
        lines.append(f"## Module {index}: {module['title']}")
        lines.append(f"_{module['objective']}_")
        lines.append("")
        for lesson in module["lessons"]:
            lines.append(f"- **{lesson['title']}** — {lesson['takeaway']}")
        lines.append("")
    return "\n".join(lines)


def _signal_text(signals: list[dict[str, str]], signal_id: str | None) -> str:
    for signal in signals:
        if signal["id"] == signal_id:
            return f"{signal['normalised']} — verbatim: \"{signal['quote']}\""
    return "(no specific signal assigned; teach to the overall promise)"


def _slugify(name: str) -> str:
    return "-".join(
        part
        for part in "".join(c.lower() if c.isalnum() else " " for c in name).split()
    ) or "module"
