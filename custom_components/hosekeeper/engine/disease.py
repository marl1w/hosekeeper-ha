"""Published turf disease models, so a warning is a number with a paper behind it.

Dollar spot: the Smith-Kerns model (Smith, Kerns et al., 2018), a logistic regression on
five-day means of relative humidity and air temperature; fungicide timing at 20 %
probability was effective in validation.

Brown patch: the Fidanza, Dernoeden and Grybauskas (1996) E2 index on mean relative
humidity and minimum air temperature; a warning at E ≥ 6 predicted outbreaks with 85 %
accuracy in field validation.
"""

from __future__ import annotations

from collections.abc import Sequence
import math

DOLLAR_SPOT_ACTION_PROBABILITY = 0.20
BROWN_PATCH_WARNING_INDEX = 6.0


def dollar_spot_probability(rh_means: Sequence[float], temp_means: Sequence[float]) -> float | None:
    """Return the Smith-Kerns probability from the last five days, or None without data."""
    rh = [v for v in list(rh_means)[-5:] if v is not None]
    temps = [v for v in list(temp_means)[-5:] if v is not None]
    if len(rh) < 3 or len(temps) < 3:
        return None
    mean_rh = sum(rh) / len(rh)
    mean_t = sum(temps) / len(temps)
    logit = -11.4041 + 0.0894 * mean_rh + 0.1932 * mean_t
    return 1.0 / (1.0 + math.exp(-logit))


def brown_patch_index(rh_mean: float | None, tmin: float | None) -> float | None:
    """Return the Fidanza E2 index for a day, or None without data."""
    if rh_mean is None or tmin is None:
        return None
    return -21.5 + 0.15 * rh_mean + 1.4 * tmin - 0.033 * tmin * tmin
