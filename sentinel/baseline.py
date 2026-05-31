"""Per-resident baseline ("digital twin") and drift detection.

The baseline is each resident's *own* normal, learned over a rolling window. Drift is
the standardised deviation (z-score) of their recent days versus that baseline — which
is exactly how clinicians describe early decline: "an abrupt change from the person's
own baseline", not a fixed population threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import data

BASELINE_DAYS = 10   # learning window (older days)
RECENT_DAYS = 3      # what we compare against the baseline
Z_THRESHOLD = 1.5    # |z| above this counts as a meaningful deviation


@dataclass
class Deviation:
    metric: str
    direction: str   # "elevated" or "reduced"
    z: float
    baseline: float
    recent: float
    concerning: bool  # is this direction the clinically bad one for this metric?


def compute(history: pd.DataFrame) -> dict[str, Deviation]:
    """Return the deviations (drift) for every tracked metric in ``history``."""
    baseline_window = history.iloc[:BASELINE_DAYS]
    recent_window = history.iloc[-RECENT_DAYS:]
    out: dict[str, Deviation] = {}
    for metric, meta in data.METRICS.items():
        base_mean = float(baseline_window[metric].mean())
        base_std = float(baseline_window[metric].std(ddof=0)) or 1e-6
        recent_mean = float(recent_window[metric].mean())
        z = (recent_mean - base_mean) / base_std
        direction = "elevated" if z >= 0 else "reduced"
        concerning = (
            abs(z) >= Z_THRESHOLD
            and ((meta["bad"] == "high" and direction == "elevated")
                 or (meta["bad"] == "low" and direction == "reduced"))
        )
        out[metric] = Deviation(metric, direction, z, base_mean, recent_mean, concerning)
    return out


def concerning(deviations: dict[str, Deviation]) -> dict[str, Deviation]:
    return {m: d for m, d in deviations.items() if d.concerning}
