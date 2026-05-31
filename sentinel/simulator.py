"""Simulated ambient-sensing feed.

Stands in for the RuView/ESP32 mesh: produces a 14-day daily-metric history plus a
"right now" real-time state for each resident, shaped by their scenario. Everything
is deterministic (seeded per resident) so the demo is reproducible.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import data

HISTORY_DAYS = 14
TODAY = date(2026, 5, 31)

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
    if resident.scenario == "fall":
        rt.update(
            presence="bathroom",
            motion="no motion since impact",
            heart_rate=int(rng.normal(104, 6)),
            breathing_rate=round(float(rng.normal(22, 2)), 1),
            event="Fall detected",
            event_minutes_ago=3,
        )
    return rt


def snapshot() -> dict[str, dict]:
    """Full simulated state for the whole roster: history + real-time per resident."""
    out = {}
    for r in data.roster():
        hist = _history(r)
        out[r.id] = {"history": hist, "realtime": _realtime(r, hist)}
    return out
