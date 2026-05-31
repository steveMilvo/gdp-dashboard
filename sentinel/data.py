"""Data model and the demo resident roster.

In production these are rows in Postgres; here they are dataclasses + an in-memory
roster so the prototype runs with zero setup. History attaches to ``resident_id``,
not the room, so it follows a resident through room moves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The metrics the sentinel tracks per resident per day. Each has a human label, a
# unit, and a "direction" indicating which way is clinically concerning. These map
# to what an ambient sensing mesh (RuView/CSI) can estimate without a camera.
METRICS: dict[str, dict] = {
    "night_bathroom_trips": {"label": "Night bathroom trips", "unit": "/night", "bad": "high"},
    "resting_hr": {"label": "Resting heart rate", "unit": "bpm", "bad": "high"},
    "sleep_fragmentation": {"label": "Sleep fragmentation", "unit": "idx", "bad": "high"},
    "restlessness_index": {"label": "Restlessness", "unit": "idx", "bad": "high"},
    "gait_speed": {"label": "Gait speed", "unit": "m/s", "bad": "low"},
    "daytime_activity": {"label": "Daytime activity", "unit": "idx", "bad": "low"},
    "social_contacts": {"label": "Social contacts", "unit": "/day", "bad": "low"},
    "time_in_bed_hours": {"label": "Time in bed", "unit": "h", "bad": "high"},
}


@dataclass
class ResidentProfile:
    """Intake data captured at onboarding; seeds the baseline and tunes thresholds."""

    care_level: str
    mobility: str
    continence: str
    dementia: bool
    fall_history: bool
    medications: list[str] = field(default_factory=list)
    consent: bool = True


@dataclass
class Resident:
    id: str
    name: str
    room: str
    age: int
    profile: ResidentProfile
    # Drives the simulator's scenario for this resident in the Phase 0 demo.
    scenario: str = "normal"


# Wing A demo roster. Scenarios drive the simulated signals (see simulator.py):
#   normal       — healthy baseline, no concerns
#   uti          — 3-day UTI drift (the flagship "caught it early" story)
#   fall         — acute fall happening now (RED life-safety alert)
#   gait_decline — slow mobility decline (rising fall risk, YELLOW)
#   withdrawal   — social withdrawal / low-mood risk (AMBER)
ROSTER: list[Resident] = [
    Resident("R-101", "Margaret Whitfield", "A-101", 84,
             ResidentProfile("Medium", "Independent", "Continent", False, False,
                             ["Atorvastatin"]), "normal"),
    Resident("R-102", "Arthur Bell", "A-102", 79,
             ResidentProfile("High", "Walker", "Continent", True, True,
                             ["Donepezil", "Amlodipine"]), "uti"),
    Resident("R-103", "Dorothy Klein", "A-103", 88,
             ResidentProfile("High", "Walker", "Occasional", False, True,
                             ["Warfarin", "Furosemide"]), "fall"),
    Resident("R-104", "Henry Osei", "A-104", 73,
             ResidentProfile("Medium", "Cane", "Continent", False, False,
                             ["Metformin"]), "gait_decline"),
    Resident("R-105", "Vera Lindqvist", "A-105", 90,
             ResidentProfile("Medium", "Independent", "Continent", False, False,
                             ["Sertraline"]), "withdrawal"),
    Resident("R-106", "Stanley Adams", "A-106", 81,
             ResidentProfile("Low", "Independent", "Continent", False, False,
                             []), "normal"),
    Resident("R-107", "Joan Pearce", "A-107", 86,
             ResidentProfile("Medium", "Cane", "Continent", True, False,
                             ["Levothyroxine"]), "normal"),
]


def roster() -> list[Resident]:
    return list(ROSTER)


def get_resident(resident_id: str) -> Resident:
    for r in ROSTER:
        if r.id == resident_id:
            return r
    raise KeyError(resident_id)
