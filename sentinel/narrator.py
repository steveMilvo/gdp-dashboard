"""LLM narrator — turns a resident's signals into plain-language, role-specific reports.

Uses the Anthropic SDK (Claude) when ``ANTHROPIC_API_KEY`` is set, with a prompt-cache
breakpoint on the stable system instructions. Falls back to a deterministic template
when no key is available, so the prototype always runs.
"""

from __future__ import annotations

import os

# Default to the most capable model; override with SENTINEL_MODEL if desired.
# For high-volume facility report generation, claude-sonnet-4-6 is a cost-effective
# choice at near-identical quality for this rewriting task:
#   export SENTINEL_MODEL=claude-sonnet-4-6
MODEL = os.getenv("SENTINEL_MODEL", "claude-opus-4-8")

# Stable, reusable system instructions. Kept in its own block with a cache breakpoint
# so repeated report generation reuses the prefix (see shared/prompt-caching.md).
SYSTEM = """You are the report-writer for an aged-care monitoring platform called \
Sentinel. You translate ambient-sensing signals (movement, presence, sleep, and \
estimated vital signs — no cameras) into clear, plain-language reports for care staff, \
clinicians, families, and management.

Rules you must always follow:
- This is a wellness / early-warning aid, NOT a medical or emergency device. Never \
diagnose; say "possible" / "consistent with" / "worth checking". Recommend clinical \
review for anything concerning.
- Ground every statement in the data provided. Cite the specific change (e.g. "night \
bathroom trips rose from 1.5 to 5"). Never invent readings.
- Write for the named audience: carers want concrete actions; doctors want clinical \
trends; management wants operational facts; families want reassurance in warm, \
non-alarming language.
- Be concise and skimmable. Lead with what matters. No preamble.
- Frame deviations as relative to the resident's OWN baseline, not population norms.
- Output only the finished report — no notes about your process or reasoning."""


def _client():
    import anthropic  # imported lazily so the app runs without the package installed

    return anthropic.Anthropic()


def narrate(report_type: str, audience: str, facts: str) -> str:
    """Generate a report. Returns LLM prose, or a templated fallback."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _fallback(report_type, audience, facts)
    try:
        client = _client()
        # Report-writing is rewriting structured facts, not complex reasoning, so
        # thinking is disabled (faster/cheaper and no risk of it eating the token
        # budget). The system block carries a cache breakpoint for prefix reuse.
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            thinking={"type": "disabled"},
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{
                "role": "user",
                "content": f"Write a {report_type} for this audience: {audience}.\n\n"
                           f"DATA:\n{facts}",
            }],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return text or _fallback(report_type, audience, facts)
    except Exception as exc:  # network/auth/SDK issues shouldn't break the demo
        return f"_(LLM unavailable — showing templated report. {type(exc).__name__})_\n\n" \
               + _fallback(report_type, audience, facts)


def _fallback(report_type: str, audience: str, facts: str) -> str:
    """Deterministic report when the LLM isn't available — keeps the demo working."""
    return (
        f"**{report_type.title()}** _(for {audience})_\n\n"
        f"{facts}\n\n"
        "_Set ANTHROPIC_API_KEY to have Claude write this as a polished narrative._"
    )
