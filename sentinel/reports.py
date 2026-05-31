"""Report generator — assembles the facts for each report type and narrates them.

One engine, role-typed outputs: the same resident data is framed for carers, doctors,
management, or an incident record. See PLAN.md §5.
"""

from __future__ import annotations

import pandas as pd

from . import data, narrator, signals
from .signals import Assessment


def _facts_block(resident: data.Resident, a: Assessment) -> str:
    lines = [
        f"Resident: {resident.name}, age {resident.age}, room {resident.room}.",
        f"Profile: {resident.profile.care_level} care, mobility {resident.profile.mobility}, "
        f"{'dementia, ' if resident.profile.dementia else ''}"
        f"{'fall history, ' if resident.profile.fall_history else ''}"
        f"meds: {', '.join(resident.profile.medications) or 'none'}.",
        f"Overall status: {a.status}.",
    ]
    if a.alerts:
        lines.append("ACUTE ALERTS:")
        lines += [f"  - [{al.tier}] {al.title}: {al.detail} (action: {al.action})" for al in a.alerts]
    if a.flags:
        lines.append("TREND FLAGS (vs this resident's own baseline):")
        for f in a.flags:
            lines.append(f"  - [{f.tier}] {f.title}")
            lines += [f"      • {r}" for r in f.rationale]
            lines.append(f"      → {f.action}")
    if not a.alerts and not a.flags:
        lines.append("No acute alerts or trend flags. Within normal baseline.")
    return "\n".join(lines)


def carer_report(resident: data.Resident, a: Assessment) -> str:
    return narrator.narrate(
        "shift-handoff note", "on-shift carer / nurse", _facts_block(resident, a))


def doctor_report(resident: data.Resident, a: Assessment, history: pd.DataFrame) -> str:
    trend = history.tail(7)[list(data.METRICS)].round(2).to_string()
    facts = _facts_block(resident, a) + "\n\nLast 7 days of daily metrics:\n" + trend
    return narrator.narrate("clinical summary", "GP / treating doctor", facts)


def incident_report(resident: data.Resident, a: Assessment, realtime: dict) -> str:
    alert = next((al for al in a.alerts if al.tier == "RED"), None)
    detail = (f"Event: {alert.title} ~{alert.minutes_ago} min ago.\n{alert.detail}"
              if alert else "No acute RED event currently active.")
    facts = (f"{_facts_block(resident, a)}\n\nIncident detail:\n{detail}\n"
             f"Real-time state: presence={realtime['presence']}, motion={realtime['motion']}, "
             f"HR={realtime['heart_rate']} bpm, breathing={realtime['breathing_rate']}/min.")
    return narrator.narrate(
        "structured incident report (what happened, when, state at the time, response taken)",
        "facility records / compliance", facts)


def management_report(assessments: dict[str, Assessment]) -> str:
    counts = {"RED": 0, "AMBER": 0, "YELLOW": 0, "GREEN": 0}
    flagged = []
    for r in data.roster():
        a = assessments[r.id]
        counts[a.status] += 1
        if a.status in ("RED", "AMBER"):
            top = (a.alerts[0].title if a.alerts else a.flags[0].title)
            flagged.append(f"  - {r.name} ({r.room}): {a.status} — {top}")
    facts = (
        f"Wing A, {len(data.roster())} residents.\n"
        f"Status counts: RED {counts['RED']}, AMBER {counts['AMBER']}, "
        f"YELLOW {counts['YELLOW']}, GREEN {counts['GREEN']}.\n"
        f"Residents needing attention:\n" + ("\n".join(flagged) or "  none")
    )
    return narrator.narrate(
        "daily operational summary", "facility management / director of nursing", facts)
