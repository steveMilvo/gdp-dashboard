"""Clinical signal library + per-resident assessment.

Maps drift patterns (from baseline.py) to candidate conditions and "things to watch
for", and turns acute real-time events into alerts. This rule table is the core IP;
in production it is refined by the self-improving loop (outcome labels), under
clinical review. Here it is a transparent, auditable set of rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import baseline, data

TIER_RANK = {"GREEN": 0, "YELLOW": 1, "AMBER": 2, "RED": 3}
TIER_EMOJI = {"GREEN": "🟢", "YELLOW": "🟡", "AMBER": "🟠", "RED": "🔴"}


@dataclass
class Flag:
    """A longitudinal (trend-based) concern."""

    tier: str
    title: str
    action: str
    rationale: list[str] = field(default_factory=list)


@dataclass
class Alert:
    """An acute, real-time, life-safety concern."""

    tier: str
    title: str
    detail: str
    action: str
    minutes_ago: int | None = None


@dataclass
class Assessment:
    resident_id: str
    status: str
    flags: list[Flag]
    alerts: list[Alert]
    watchlist: list[dict]
    deviations: dict[str, baseline.Deviation]


def _fmt(dev: baseline.Deviation) -> str:
    meta = data.METRICS[dev.metric]
    return (f"{meta['label']} {dev.direction} "
            f"({dev.baseline:.1f}→{dev.recent:.1f} {meta['unit']}, z={dev.z:+.1f})")


def _longitudinal_flags(concerning: dict[str, baseline.Deviation]) -> list[Flag]:
    keys = set(concerning)
    flags: list[Flag] = []

    # UTI / infection: the flagship early-warning pattern.
    if {"night_bathroom_trips", "resting_hr"} <= keys and (
        {"sleep_fragmentation", "restlessness_index"} & keys
    ):
        flags.append(Flag(
            "AMBER", "Possible UTI / infection developing",
            "Request urinalysis; watch for new confusion; ensure hydration; consider GP review.",
            [_fmt(concerning[m]) for m in
             ("night_bathroom_trips", "resting_hr", "sleep_fragmentation", "restlessness_index")
             if m in concerning],
        ))

    # Mobility decline -> rising fall risk.
    if "gait_speed" in keys:
        flags.append(Flag(
            "YELLOW", "Declining mobility — rising fall risk",
            "Physiotherapy review; check footwear and environment; reassess mobility aid.",
            [_fmt(concerning["gait_speed"])],
        ))

    # Social withdrawal -> low-mood / depression risk.
    if {"daytime_activity", "social_contacts"} <= keys:
        flags.append(Flag(
            "AMBER", "Social withdrawal — low-mood / depression risk",
            "Wellbeing check; encourage social engagement; review mood and medication.",
            [_fmt(concerning[m]) for m in ("daytime_activity", "social_contacts")],
        ))

    # Standalone sleep disruption (only if not already explained by UTI pattern).
    if "sleep_fragmentation" in keys and not any(
        f.title.startswith("Possible UTI") for f in flags
    ):
        flags.append(Flag(
            "YELLOW", "Disrupted sleep",
            "Review evening routine, pain, caffeine, and bedroom environment.",
            [_fmt(concerning["sleep_fragmentation"])],
        ))

    return flags


def _acute_alerts(realtime: dict) -> list[Alert]:
    alerts: list[Alert] = []
    if realtime.get("event") == "Fall detected":
        alerts.append(Alert(
            "RED", "Fall detected",
            f"No motion since impact in {realtime['presence']}; "
            f"HR {realtime['heart_rate']} bpm, breathing {realtime['breathing_rate']}/min.",
            "Attend immediately. Assess for injury before moving. Escalate to RN.",
            realtime.get("event_minutes_ago"),
        ))
    if realtime.get("event") == "Help gesture — assistance requested":
        alerts.append(Alert(
            "RED", "Assistance requested (help gesture)",
            "Resident performed a deliberate arm-wave help gesture — an active call for "
            "assistance with no button or wearable required.",
            "Attend immediately and confirm what assistance is needed.",
            realtime.get("event_minutes_ago"),
        ))
    return alerts


def _profile_watch(resident: data.Resident) -> list[dict]:
    items = []
    if resident.profile.fall_history:
        items.append({"title": "History of falls", "tier": "YELLOW",
                      "action": "Maintain fall precautions; keep path to bathroom clear."})
    if resident.profile.dementia:
        items.append({"title": "Dementia — infection can present as confusion", "tier": "YELLOW",
                      "action": "Treat sudden confusion as possible infection/delirium, not progression."})
    return items


def assess(resident: data.Resident, history: pd.DataFrame, realtime: dict) -> Assessment:
    deviations = baseline.compute(history)
    concerning = baseline.concerning(deviations)
    flags = _longitudinal_flags(concerning)
    alerts = _acute_alerts(realtime)

    watchlist = [{"title": f.title, "tier": f.tier, "action": f.action} for f in flags]
    watchlist += _profile_watch(resident)

    tiers = ["GREEN"] + [f.tier for f in flags] + [a.tier for a in alerts]
    status = max(tiers, key=lambda t: TIER_RANK[t])
    return Assessment(resident.id, status, flags, alerts, watchlist, deviations)
