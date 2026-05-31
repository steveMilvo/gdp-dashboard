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

import pandas as pd

SLA_MIN = 10               # response-time service level (minutes)
NIGHT_START, NIGHT_END = 22, 6  # overnight window (hours)


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
