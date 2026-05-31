"""Node registry & commissioning.

Turns a box of identical ESP32 boards into a bound room mesh. A node is identified by
its burned-in MAC; commissioning records which room + corner it serves and authorises it.

Lifecycle:  discovered → bound → online   (+ offline / retired)

In production this is rows in a database fed by nodes announcing themselves on first
boot. Here it's seeded in-memory so the commissioning workflow can be demonstrated.
"""

from __future__ import annotations

import random

ROOM_POSITIONS = ["NW corner", "NE corner", "SW corner", "SE corner", "Mid-wall", "Ceiling"]
MIN_NODES_PER_ROOM = 3  # below this, a room can't self-survey / localise


def _mac() -> str:
    return ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))


def seed_registry() -> list[dict]:
    """A few already-commissioned nodes (so the registry isn't empty on first view)."""
    rng = random.Random(42)
    rows = []
    for room, n in [("A-101", 4), ("A-102", 4), ("A-103", 3)]:
        for i in range(n):
            rows.append({
                "mac": ":".join(f"{rng.randint(0, 255):02X}" for _ in range(6)),
                "room": room, "position": ROOM_POSITIONS[i],
                "status": "online", "rssi": rng.randint(-68, -44),
                "firmware": "v0.6.5", "last_seen_s": rng.randint(0, 3),
            })
    return rows


def seed_discovered() -> list[dict]:
    """Unregistered nodes broadcasting 'I'm new' — waiting to be claimed."""
    rng = random.Random(7)
    return [{"mac": ":".join(f"{rng.randint(0, 255):02X}" for _ in range(6)),
             "rssi": rng.randint(-72, -50)} for _ in range(3)]


def room_counts(registry: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for n in registry:
        if n["status"] in ("bound", "online"):
            counts[n["room"]] = counts.get(n["room"], 0) + 1
    return counts


def room_ready(registry: list[dict], room: str) -> bool:
    """A room can localise once it has enough bound nodes to self-survey."""
    return room_counts(registry).get(room, 0) >= MIN_NODES_PER_ROOM
