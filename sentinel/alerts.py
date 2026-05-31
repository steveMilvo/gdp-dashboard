"""Alert tiering and escalation policy.

The tiers come from signals.py; this module defines what each tier *does* — who is
paged and how it escalates if unacknowledged. Tuned so RED is rare and trusted, which
is the main defence against alarm fatigue (the #1 reason facility alerting gets
switched off). See PLAN.md §5.
"""

from __future__ import annotations

# Escalation policy per tier: channel, acknowledgement requirement, and escalation.
ESCALATION = {
    "RED": {
        "channel": "Page on-shift carer immediately + audible alert",
        "ack_required": True,
        "ack_timeout_sec": 60,
        "escalates_to": "Charge nurse → site manager if unacknowledged",
    },
    "AMBER": {
        "channel": "Nurse triage queue (review this shift)",
        "ack_required": True,
        "ack_timeout_sec": 8 * 3600,
        "escalates_to": "Clinical lead if not actioned within the shift",
    },
    "YELLOW": {
        "channel": "Added to care-plan notes (no page)",
        "ack_required": False,
        "ack_timeout_sec": None,
        "escalates_to": "—",
    },
    "GREEN": {
        "channel": "No action",
        "ack_required": False,
        "ack_timeout_sec": None,
        "escalates_to": "—",
    },
}


def policy(tier: str) -> dict:
    return ESCALATION.get(tier, ESCALATION["GREEN"])
