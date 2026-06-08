"""ATO effective-life reference data for common residential plant & equipment.

These are *indicative* effective lives (in years) for frequently encountered
residential rental assets. They are used to:

  * pre-fill the Division 40 asset register in the UI, and
  * cross-check (validate) any effective life proposed by an LLM or a user.

The authoritative source is the ATO's effective-life determination:

  * Pre-2026 basis:  Taxation Ruling TR 2022/1 (withdrawn 31 Oct 2025)
  * Post-2026 basis: Income Tax (Effective Life of Depreciating Assets)
                     Determination 2025  (LI 2025/20)

The "pre_2026" and "post_2026" columns let the engine model the change of basis.
Where a value is unconfirmed against LI 2025/20 it mirrors the pre-2026 figure;
those should be verified against the current determination before production use.
This table is NOT a substitute for the determination and is not tax advice.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EffectiveLife:
    name: str
    keywords: tuple[str, ...]
    pre_2026: float
    post_2026: float


# Indicative residential effective lives (years). Keywords drive fuzzy matching.
EFFECTIVE_LIVES: tuple[EffectiveLife, ...] = (
    EffectiveLife("Carpet", ("carpet",), 8, 8),
    EffectiveLife("Floating timber/laminate flooring", ("floating floor", "laminate", "floating timber"), 15, 15),
    EffectiveLife("Vinyl flooring", ("vinyl", "linoleum"), 10, 10),
    EffectiveLife("Hot water system", ("hot water", "hws"), 12, 12),
    EffectiveLife("Solar hot water system", ("solar hot water",), 15, 15),
    EffectiveLife("Oven", ("oven",), 12, 12),
    EffectiveLife("Cooktop", ("cooktop", "stove", "hob"), 12, 12),
    EffectiveLife("Rangehood", ("rangehood", "range hood"), 12, 12),
    EffectiveLife("Dishwasher", ("dishwasher",), 10, 10),
    EffectiveLife("Refrigerator", ("fridge", "refrigerator"), 12, 12),
    EffectiveLife("Microwave", ("microwave",), 10, 10),
    EffectiveLife("Washing machine", ("washing machine", "washer"), 10, 10),
    EffectiveLife("Clothes dryer", ("dryer",), 10, 10),
    EffectiveLife("Air conditioner (split system)", ("air conditioner", "split system", "a/c", "aircon"), 10, 10),
    EffectiveLife("Ceiling fan", ("ceiling fan", "fan"), 5, 5),
    EffectiveLife("Exhaust fan", ("exhaust fan",), 10, 10),
    EffectiveLife("Blinds (internal)", ("blind",), 10, 10),
    EffectiveLife("Curtains", ("curtain", "drape"), 6, 6),
    EffectiveLife("Light shades / freestanding lamps", ("lamp", "light shade"), 5, 5),
    EffectiveLife("Smoke alarm (freestanding)", ("smoke alarm", "smoke detector"), 6, 6),
    EffectiveLife("Garbage disposal unit", ("garbage disposal", "insinkerator"), 12, 12),
    EffectiveLife("Hot water heat pump", ("heat pump",), 12, 12),
    EffectiveLife("Security system", ("security system", "alarm system"), 5, 5),
    EffectiveLife("Door closer / garage door motor", ("garage door motor", "door motor"), 7, 7),
    EffectiveLife("Swimming pool pump", ("pool pump",), 9, 9),
)

Basis = str  # "pre_2026" | "post_2026"


def lookup_effective_life(description: str, basis: Basis = "post_2026") -> EffectiveLife | None:
    """Best-effort match of a free-text asset description to a known asset.

    Returns the matched `EffectiveLife` record, or None if nothing matches.
    """
    text = description.strip().lower()
    if not text:
        return None
    # Prefer the longest keyword match (more specific wins, e.g. "solar hot
    # water" over "hot water").
    best: tuple[int, EffectiveLife] | None = None
    for record in EFFECTIVE_LIVES:
        for kw in record.keywords:
            if kw in text:
                score = len(kw)
                if best is None or score > best[0]:
                    best = (score, record)
    return best[1] if best else None


def effective_life_for(description: str, basis: Basis = "post_2026") -> float | None:
    """Return the indicative effective life (years) for a description, or None."""
    rec = lookup_effective_life(description, basis)
    if rec is None:
        return None
    return rec.post_2026 if basis == "post_2026" else rec.pre_2026
