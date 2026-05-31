"""Co-presence and staff-interaction logic.

Staff carry a BLE badge read by the same room nodes, so every staff–resident
interaction is logged (who, when, duration). This:
  - resolves "who is the second person" (staff vs unknown), suppressing false falls;
  - evidences AN-ACC **care minutes** automatically (the headline compliance feature);
  - raises an alert only for an *unidentified* second person *after hours*
    (policy: log all co-presence, alert on unknown-after-hours).

Staff-tracking is industrially sensitive — deploy transparently, with consultation,
framed as care-minute evidence + lone-worker safety, not surveillance. See PLAN.md.
"""

from __future__ import annotations

import pandas as pd

from . import data

CARE_MINUTE_TARGET = 215   # AN-ACC total care minutes / resident / day
RN_MINUTE_TARGET = 44      # of which must be RN minutes
_RN_ROLES = {"RN", "EN"}


def copresence_alert(realtime: dict) -> dict | None:
    """Return an alert dict if an unidentified person is present after hours, else None."""
    occ = realtime.get("occupancy", {})
    unknown = [o for o in occ.get("others", []) if not o.get("identified")]
    if unknown and occ.get("after_hours"):
        return {
            "tier": "AMBER",
            "title": "Unidentified person in room (after hours)",
            "action": "Verify identity — check for a wandering resident or unauthorised visitor.",
        }
    return None


def occupants_label(realtime: dict) -> str | None:
    """Human-readable 'who is in the room now', or None if just the resident."""
    occ = realtime.get("occupancy", {})
    if occ.get("count", 1) <= 1:
        return None
    others = ", ".join(o["name"] for o in occ.get("others", []))
    return f"{occ['count']} people in room — resident + {others}"


def care_minutes_summary(inter: pd.DataFrame) -> pd.DataFrame:
    """Per-resident care-minute tally vs AN-ACC targets, from the interaction log."""
    rows = []
    for r in data.roster():
        sub = inter[inter["resident_id"] == r.id]
        total = int(sub["minutes"].sum())
        rn = int(sub[sub["role"].isin(_RN_ROLES)]["minutes"].sum())
        met = total >= CARE_MINUTE_TARGET and rn >= RN_MINUTE_TARGET
        rows.append({
            "Resident": r.name, "Room": r.room,
            "Care mins": total, "Target": CARE_MINUTE_TARGET,
            "RN mins": rn, "RN target": RN_MINUTE_TARGET,
            "Visits": len(sub), "Status": "✅ met" if met else "⚠️ under",
        })
    return pd.DataFrame(rows)


def staff_summary(inter: pd.DataFrame) -> pd.DataFrame:
    """Per-staff workload across the shift — the managerial view of the same log."""
    rows = []
    for (sid, name, role), sub in inter.groupby(["staff_id", "staff", "role"], sort=False):
        span = f"{sub['start'].min()}–{sub['end'].max()}"
        rows.append({
            "Staff": name, "Role": role,
            "Interactions": len(sub),
            "Active mins": int(sub["minutes"].sum()),
            "Residents seen": sub["resident_id"].nunique(),
            "Rooms": sub["room"].nunique(),
            "Shift span": span,
        })
    return pd.DataFrame(rows).sort_values("Active mins", ascending=False)


def staff_shift_log(inter: pd.DataFrame, staff_id: str) -> pd.DataFrame:
    """One staff member's chronological movement trail across the shift."""
    sub = inter[inter["staff_id"] == staff_id].copy()
    sub = sub.sort_values("start")
    return sub[["start", "end", "room", "resident", "activity", "minutes"]]

