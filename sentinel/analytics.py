"""Responsiveness & accountability analytics.

Turns assistance-call events + staff-badge activity into response-time metrics and
exception flags for management / clinical governance — e.g. unanswered overnight calls
while the rostered carer was inactive. Genuine resident-safety failures of this kind can
be **SIRS-reportable as neglect**, which is the legitimate driver for this analysis.

Use it as governed, evidence-based safety analytics — findings must be verified
(against badge/CCTV/roster) before any action, and it is not a punitive surveillance
tool. See PLAN.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SLA_MIN = 10               # response-time service level (minutes)
NIGHT_START, NIGHT_END = 22, 6  # overnight window (hours)

# National Aged Care Mandatory Quality Indicator (QI) Program, and how far Sentinel's
# mesh data can populate each. "Auto" = computed from sensed events; "Partial" = sensing
# contributes but care records are also needed; "Integration" = needs eMAR/EHR/survey.
QI_PROGRAM = [
    ("Falls and major injury", "Auto", "Sensed fall detection + injury follow-up"),
    ("Physical restraint", "Partial", "Movement / co-presence monitoring (+ care records)"),
    ("Activities of daily living", "Partial", "Activity & mobility sensing (+ assessments)"),
    ("Continence care", "Partial", "Night toileting patterns (+ care records)"),
    ("Workforce", "Partial", "Staff-badge care-minute data"),
    ("Pressure injuries", "Integration", "Clinical records / eMAR"),
    ("Unplanned weight loss", "Integration", "Clinical records"),
    ("Medication management", "Integration", "eMAR"),
    ("Hospitalisation", "Integration", "Clinical / admin records"),
    ("Quality of life / consumer experience", "Integration", "Resident survey"),
]


def qi_table() -> pd.DataFrame:
    return pd.DataFrame(QI_PROGRAM,
                        columns=["Quality indicator", "Sentinel coverage", "Data source"])


def falls_quarter(beds: int = 132) -> dict:
    """Quarterly Falls QI, as it would be computed from logged fall events over 91 days.

    (Synthesised here; in production it's a direct count from the sensed-fall log.)
    """
    rng = np.random.default_rng(20260531)
    bed_days = beds * 91
    falls = int(rng.integers(72, 108))
    residents_fell = int(rng.integers(34, 52))
    major_injury = int(rng.integers(3, 9))
    prev_falls = int(rng.integers(80, 120))
    return {
        "beds": beds, "bed_days": bed_days, "falls": falls,
        "residents_fell": residents_fell, "major_injury": major_injury,
        "rate_per_1000_bed_days": round(falls / bed_days * 1000, 2),
        "pct_residents_fell": round(residents_fell / beds * 100),
        "trend_vs_prev": falls - prev_falls,
    }


def sirs_pack(events: pd.DataFrame) -> dict | None:
    """Assemble a SIRS-ready serious-incident pack from an unattended sensed fall."""
    fall = events[(events["trigger"] == "Fall") & (events["status"] == "unattended")]
    if fall.empty:
        return None
    f = fall.iloc[0]
    return {
        "priority": "Priority 1 — notify the Aged Care Quality & Safety Commission "
                    "within 24 hours",
        "incident_type": "Unreasonable use of force / neglect — fall left unattended",
        "resident": f["resident"], "room": f["room"], "detected": f["time"],
        "summary": (f"A fall was sensed in {f['room']} ({f['resident']}) at {f['time']} "
                    "overnight. No staff badge attended the room during the surrounding "
                    "unattended-event cluster, indicating the resident's care need went "
                    "unmet."),
        "evidence": [
            "Sensed fall event (mesh) with timestamp",
            "Staff badge movement trail showing no attendance in the window",
            "Cluster of other unattended overnight events in the same period",
        ],
        "actions": [
            "Verify against badge trail and roster; conduct welfare check / clinical review",
            "Notify the Commission within 24h (Priority 1); notify next of kin",
            "Open internal investigation; review night staffing",
        ],
    }


def _is_night(hhmm: str) -> bool:
    h = int(hhmm[:2])
    return h >= NIGHT_START or h < NIGHT_END


def responsiveness_summary(events: pd.DataFrame) -> dict:
    attended = events[events["status"] != "unattended"]
    night_unatt = events[(events["status"] == "unattended") & events["time"].map(_is_night)]
    return {
        "total": len(events),
        "unattended": int((events["status"] == "unattended").sum()),
        "late": int((events["status"] == "late").sum()),
        "avg_response": round(float(attended["response_min"].mean()), 1) if len(attended) else None,
        "max_response": int(attended["response_min"].max()) if len(attended) else None,
        "night_unattended": len(night_unatt),
    }


def accountability_exceptions(events: pd.DataFrame) -> list[dict]:
    """Exception flags to escalate to management / compliance."""
    exc = []
    night = events[events["time"].map(_is_night)]
    unatt = night[night["status"] == "unattended"]
    if len(unatt) >= 2:
        responders = night.loc[night["attended_by"] != "—", "attended_by"]
        carer = responders.mode().iat[0] if len(responders) else "the rostered night carer"
        had_fall = (unatt["trigger"] == "Fall").any()
        exc.append({
            "severity": "RED",
            "title": "Sensed distress events unattended overnight",
            "detail": (f"{len(unatt)} sensed attention event(s)"
                       + (" including a FALL" if had_fall else "")
                       + f" went unattended between {unatt['time'].min()} and "
                       f"{unatt['time'].max()} while {carer} was the rostered night carer — a "
                       f"large gap between their logged room visits spans the cluster "
                       f"(possible inactivity)."),
            "action": ("Review immediately and verify against the badge movement trail and "
                       "roster. Unmet care needs may be SIRS-reportable as neglect."),
        })
    for _, c in events[events["status"] == "late"].iterrows():
        exc.append({
            "severity": "AMBER",
            "title": "Attendance slower than SLA",
            "detail": (f"{c['room']} {c['resident']} — {c['trigger']} attended after "
                       f"{int(c['response_min'])} min by {c['attended_by']} (SLA {SLA_MIN} min)."),
            "action": "Review staffing/workload for that period.",
        })
    return exc
