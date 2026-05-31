"""Simulated ambient-sensing feed.

Stands in for the RuView/ESP32 mesh: produces a 14-day daily-metric history plus a
"right now" real-time state for each resident, shaped by their scenario. Everything
is deterministic (seeded per resident) so the demo is reproducible.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from . import data

HISTORY_DAYS = 14
TODAY = date(2026, 5, 31)
SHIFT_START = datetime(2026, 5, 31, 7, 0)  # for today's staff-interaction log

# Care activity types inferred from location/duration/staff role (logged per interaction).
ACTIVITIES = [
    "Personal care / bathing", "Medication round", "Meal assistance", "Toileting assist",
    "Mobility / transfer", "Welfare check", "Wound care", "Social / wellbeing",
]

# Staff who carry a BLE badge (read by the same nodes). RN/EN count as RN minutes.
STAFF = [
    ("S-1", "Jane Okafor", "RN"),
    ("S-2", "Tom Reilly", "EN"),
    ("S-3", "Mai Tran", "Carer"),
    ("S-4", "Carlos Diaz", "Carer"),
    ("S-5", "Priya Shah", "Allied"),
]

# Population-level "normal" daily values: (mean, day-to-day noise std).
_NORMAL = {
    "night_bathroom_trips": (1.5, 0.6),
    "resting_hr": (68.0, 2.5),
    "sleep_fragmentation": (0.25, 0.04),
    "restlessness_index": (0.20, 0.04),
    "gait_speed": (0.92, 0.04),
    "daytime_activity": (0.55, 0.06),
    "social_contacts": (3.0, 1.0),
    "time_in_bed_hours": (8.5, 0.5),
}


def _seed(resident_id: str) -> np.random.Generator:
    # hashlib (not builtin hash(), which is randomized per process) → reproducible runs.
    digest = hashlib.md5(resident_id.encode()).hexdigest()
    return np.random.default_rng(int(digest, 16) % (2**32))


def _ramp(n_days: int, total_len: int, peak: float) -> np.ndarray:
    """A 0->peak ramp over the final ``n_days`` of a ``total_len`` series."""
    out = np.zeros(total_len)
    if n_days > 0:
        out[-n_days:] = np.linspace(peak / n_days, peak, n_days)
    return out


def _history(resident: data.Resident) -> pd.DataFrame:
    rng = _seed(resident.id)
    days = [TODAY - timedelta(days=d) for d in range(HISTORY_DAYS - 1, -1, -1)]
    cols = {}
    # Per-resident bias so each person's baseline is genuinely their own.
    for metric, (mean, noise) in _NORMAL.items():
        bias = rng.normal(0, noise * 0.5)
        cols[metric] = mean + bias + rng.normal(0, noise, HISTORY_DAYS)

    # Apply scenario drift over the recent window.
    s = resident.scenario
    if s == "uti":
        cols["night_bathroom_trips"] += _ramp(3, HISTORY_DAYS, 4.0)
        cols["resting_hr"] += _ramp(3, HISTORY_DAYS, 11.0)
        cols["sleep_fragmentation"] += _ramp(3, HISTORY_DAYS, 0.26)
        cols["restlessness_index"] += _ramp(3, HISTORY_DAYS, 0.22)
    elif s == "gait_decline":
        cols["gait_speed"] -= _ramp(8, HISTORY_DAYS, 0.22)
    elif s == "withdrawal":
        cols["daytime_activity"] -= _ramp(6, HISTORY_DAYS, 0.27)
        cols["social_contacts"] -= _ramp(6, HISTORY_DAYS, 2.6)

    df = pd.DataFrame(cols)
    df.insert(0, "date", pd.to_datetime(days))
    df["social_contacts"] = df["social_contacts"].clip(lower=0).round()
    df["night_bathroom_trips"] = df["night_bathroom_trips"].clip(lower=0).round()
    for c in ("sleep_fragmentation", "restlessness_index", "daytime_activity"):
        df[c] = df[c].clip(0, 1)
    return df


def _realtime(resident: data.Resident, history: pd.DataFrame) -> dict:
    rng = _seed(resident.id + "rt")
    last = history.iloc[-1]
    rt = {
        "presence": "in_room",
        "motion": "moving" if rng.random() > 0.5 else "still",
        "breathing_rate": round(float(rng.normal(15, 1.5)), 1),
        "heart_rate": int(last["resting_hr"] + rng.normal(4, 3)),
        "event": None,
        "event_minutes_ago": None,
    }
    # Co-presence ("who else is in the room now"), resolved via staff badges.
    rt["occupancy"] = {"count": 1, "others": [], "after_hours": False}
    if resident.scenario == "fall":
        rt.update(
            presence="bathroom",
            motion="no motion since impact",
            heart_rate=int(rng.normal(104, 6)),
            breathing_rate=round(float(rng.normal(22, 2)), 1),
            event="Fall detected",
            event_minutes_ago=3,
        )
        rt["occupancy"] = {"count": 2, "after_hours": False,
                           "others": [{"name": "Jane Okafor (RN)", "identified": True}]}
    if resident.id == "R-107":  # demo: unidentified person after hours -> alert
        rt["occupancy"] = {"count": 2, "after_hours": True,
                           "others": [{"name": "Unidentified person", "identified": False}]}
    return rt


def interactions() -> pd.DataFrame:
    """Today's staff–resident interactions, auto-logged from staff badges.

    Each row is one badge-detected visit (who, when, how long). Durations sum into
    AN-ACC care minutes. Deterministic per resident.
    """
    rows = []
    for r in data.roster():
        rng = _seed(r.id + "visits")
        t = SHIFT_START
        for _ in range(int(rng.integers(8, 16))):
            t = t + timedelta(minutes=int(rng.integers(10, 60)))  # gap until next visit
            start_dt = t
            mins = int(rng.integers(6, 30))
            end_dt = start_dt + timedelta(minutes=mins)
            staff = STAFF[int(rng.integers(0, len(STAFF)))]
            rows.append({
                "resident_id": r.id, "resident": r.name, "room": r.room,
                "staff_id": staff[0], "staff": staff[1], "role": staff[2],
                "activity": ACTIVITIES[int(rng.integers(0, len(ACTIVITIES)))],
                "start": start_dt.strftime("%H:%M"), "end": end_dt.strftime("%H:%M"),
                "minutes": mins,
            })
            t = end_dt  # next gap starts after this visit ends (no overlaps)
    return pd.DataFrame(rows)


def vitals_trace(resident_id: str, now: float, hr: float, br: float,
                 window: float = 8.0, fs: int = 20) -> pd.DataFrame:
    """A short rolling chest-displacement waveform ending at ``now`` (wall-clock).

    Respiration sine at ``br`` breaths/min with a faint heartbeat ripple at ``hr`` bpm.
    Because the window slides with ``now``, re-rendering each second makes it scroll —
    the visual proof that sensing is live. Fresh noise each call adds realistic jitter.
    """
    n = int(window * fs)
    t = np.linspace(now - window, now, n)
    rng = np.random.default_rng()
    chest = (np.sin(2 * np.pi * (br / 60.0) * t)
             + 0.18 * np.sin(2 * np.pi * (hr / 60.0) * t)
             + rng.normal(0, 0.03, n))
    return pd.DataFrame({"seconds_ago": t - now, "chest displacement": chest})


def node_health() -> pd.DataFrame:
    """Simulated per-room mesh telemetry — the real-world 'is it alive' proof.

    Two nodes per room (the cheap install design). Fresh jitter each call so packet
    ages and RSSI tick on refresh. One node is held offline to show fault visibility.
    """
    rng = np.random.default_rng()
    rows = []
    for r in data.roster():
        for k in range(2):
            offline = (r.room == "A-106" and k == 1)
            rows.append({
                "room": r.room,
                "node": f"{r.room}-N{k}",
                "status": "🔴 offline" if offline else "🟢 online",
                "last packet (s)": 47 if offline else int(rng.integers(0, 3)),
                "RSSI (dBm)": None if offline else int(rng.integers(-68, -42)),
            })
    return pd.DataFrame(rows)


def snapshot() -> dict[str, dict]:
    """Full simulated state for the whole roster: history + real-time per resident."""
    out = {}
    for r in data.roster():
        hist = _history(r)
        out[r.id] = {"history": hist, "realtime": _realtime(r, hist)}
    return out
