"""Per-model token pricing, in microcents per token.

Stored in microcents (1/1_000_000 of a cent) because a single Haiku call can
cost a fraction of a cent and integer arithmetic beats float drift when you are
summing tens of thousands of invocations into a unit-economics figure.

USD. Convert at report time if the operator wants AUD — we do not bake an FX
rate into stored history.
"""

from __future__ import annotations

from dataclasses import dataclass

_MICROCENTS_PER_DOLLAR = 100 * 1_000_000


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok_usd: float
    output_per_mtok_usd: float
    cache_write_multiplier: float = 1.25
    cache_read_multiplier: float = 0.1


PRICES: dict[str, ModelPrice] = {
    "claude-opus-5": ModelPrice(5.00, 25.00),
    "claude-opus-4-8": ModelPrice(5.00, 25.00),
    "claude-opus-4-7": ModelPrice(5.00, 25.00),
    "claude-sonnet-5": ModelPrice(3.00, 15.00),
    "claude-sonnet-4-6": ModelPrice(3.00, 15.00),
    "claude-haiku-4-5": ModelPrice(1.00, 5.00),
    "claude-fable-5": ModelPrice(10.00, 50.00),
}

_FALLBACK = ModelPrice(5.00, 25.00)


def price_for(model: str) -> ModelPrice:
    if model in PRICES:
        return PRICES[model]
    # Model IDs are stable strings without date suffixes, but be forgiving of
    # a pinned snapshot rather than mispricing at zero.
    for known, price in PRICES.items():
        if model.startswith(known):
            return price
    return _FALLBACK


def cost_microcents(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> int:
    p = price_for(model)
    per_input = p.input_per_mtok_usd * _MICROCENTS_PER_DOLLAR / 1_000_000
    per_output = p.output_per_mtok_usd * _MICROCENTS_PER_DOLLAR / 1_000_000
    total = (
        input_tokens * per_input
        + output_tokens * per_output
        + cache_read_tokens * per_input * p.cache_read_multiplier
        + cache_write_tokens * per_input * p.cache_write_multiplier
    )
    return int(round(total))


def format_microcents(value: int) -> str:
    return f"${value / (100 * 1_000_000):,.4f}"
