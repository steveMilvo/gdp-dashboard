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


def responsiveness_summary(calls: pd.DataFrame) -> dict:
    answered = calls[calls["status"] != "unanswered"]
    night_unans = calls[(calls["status"] == "unanswered") & calls["time"].map(_is_night)]
    return {
        "total": len(calls),
        "unanswered": int((calls["status"] == "unanswered").sum()),
        "slow": int((calls["status"] == "slow").sum()),
        "avg_response": round(float(answered["response_min"].mean()), 1) if len(answered) else None,
        "max_response": int(answered["response_min"].max()) if len(answered) else None,
        "night_unanswered": len(night_unans),
    }


def accountability_exceptions(calls: pd.DataFrame) -> list[dict]:
    """Exception flags to escalate to management / compliance."""
    exc = []
    night = calls[calls["time"].map(_is_night)]
    unans = night[night["status"] == "unanswered"]
    if len(unans) >= 2:
        responders = night.loc[night["responder"] != "—", "responder"]
        carer = responders.mode().iat[0] if len(responders) else "the rostered night carer"
        exc.append({
            "severity": "RED",
            "title": "Unanswered assistance calls overnight",
            "detail": (f"{len(unans)} assistance call(s) went unanswered between "
                       f"{unans['time'].min()} and {unans['time'].max()} while {carer} was the "
                       f"rostered night carer — a large gap between their logged responses spans "
                       f"the unanswered cluster (possible inactivity)."),
            "action": ("Review immediately and verify against badge trail, roster, and CCTV. "
                       "Unmet care needs may be SIRS-reportable as neglect."),
        })
    for _, c in calls[calls["status"] == "slow"].iterrows():
        exc.append({
            "severity": "AMBER",
            "title": "Response slower than SLA",
            "detail": (f"{c['room']} {c['resident']} — {c['type']} answered in "
                       f"{int(c['response_min'])} min by {c['responder']} (SLA {SLA_MIN} min)."),
            "action": "Review staffing/workload for that period.",
        })
    return exc
