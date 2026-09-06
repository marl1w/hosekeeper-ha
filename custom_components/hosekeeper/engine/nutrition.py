"""Which fertilizer, not only whether: the N-P-K class the moment calls for.

The programme says how much nitrogen a window wants. This module decides the shape of it —
the ratio between nitrogen, phosphorus and potassium, how much of the nitrogen should be
slow release, whether to split the dose — from the lawn's age and condition, the soil, the
season and what the weather is doing and about to do. It then finds the closest preset and
the dose that delivers the nitrogen, so the advice can name a bag and a number.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .knowledge import fertilizers, programme

if TYPE_CHECKING:
    from .rules import Context

# The class each role stands for, as the smallest whole-number ratio.
RATIOS: dict[str, tuple[int, int, int]] = {
    "starter": (1, 2, 1),  # phosphorus for roots: Pro Start 13-24-10
    "greening": (1, 0, 0),  # nitrogen with iron and magnesium: Dark Green 11-0-0 +3MgO +4.5Fe
    "growth": (4, 1, 2),  # nitrogen-led balanced feed: Slow Green 22-5-10
    "stress": (2, 1, 3),  # potassium-led, moderate nitrogen: Slow K 13-5-20
    "autumn": (1, 0, 1),  # nitrogen and potassium for winter hardiness: Autumn K 21-0-25
}

MAX_N_PER_APPLICATION = 5.0
MIN_N_PER_APPLICATION = 1.5

# How long a lawn counts as establishing, for the sake of choosing a fertilizer.
ESTABLISHING_DAYS = 60
SOWN_RECENTLY_DAYS = 30


@dataclass(frozen=True, slots=True)
class FeedPlan:
    """What to put down."""

    role: str
    ratio: tuple[int, int, int]
    n_g_m2: float
    slow_fraction_min: float
    split: bool
    preset: str | None
    dose_g_m2: float | None
    reasons: tuple[str, ...]

    def as_params(self) -> dict[str, object]:
        """Return the plan as advice parameters."""
        return {
            "role": self.role,
            "npk_class": "-".join(str(v) for v in self.ratio),
            "n_g_m2": self.n_g_m2,
            "slow_release_min_pct": round(self.slow_fraction_min * 100),
            "split": self.split,
            "preset": self.preset,
            "dose_g_m2": self.dose_g_m2,
        }


def plan(ctx: Context, window: programme.FeedWindow) -> FeedPlan:
    """Return the feed for a programme window, shaped by the lawn and the weather."""
    role = window.role
    reasons: list[str] = [f"window_{window.code}"]
    n = window.n_g_m2 / ctx.feed_factor
    slow_min = 0.3
    split = False

    # A lawn still establishing wants phosphorus for roots — but only while it is
    # establishing. Two months from laying, or a month from sowing, is the window; a lawn
    # four months old is a lawn, and by then the calendar knows better than the birth
    # certificate. The autumn feed is never displaced: potassium before winter is what the
    # plant is short of, whatever its age.
    young = (
        ctx.establishment_age_days is not None and ctx.establishment_age_days < ESTABLISHING_DAYS
    )
    sown = ctx.days_since_sowing is not None and ctx.days_since_sowing < SOWN_RECENTLY_DAYS
    if (young or sown) and role != "autumn":
        role = "starter"
        reasons.append("young_lawn_needs_phosphorus" if young else "recent_sowing_needs_phosphorus")

    # Heat on the way, or a stressed lawn: potassium up, nitrogen down and slow.
    hot_ahead = ctx.forecast_tmax_3d is not None and ctx.forecast_tmax_3d >= 27
    if role in ("growth", "greening") and (
        ctx.phenology.heat_stress or hot_ahead or ctx.phase == "summer_stress"
    ):
        role = "stress"
        n = min(n, 2.5)
        slow_min = max(slow_min, 0.5)
        reasons.append("heat_ahead_potassium_slow_nitrogen")

    # Disease: less nitrogen, none of it quick.
    if {"fungus", "brown_patches"} & ctx.issues_30d or (
        ctx.brown_patch_index is not None and ctx.brown_patch_index >= 6
    ):
        n *= 0.7
        slow_min = max(slow_min, 0.5)
        reasons.append("disease_less_nitrogen")
    elif ctx.dollar_spot_probability is not None and ctx.dollar_spot_probability >= 0.2:
        # Dollar spot is a disease of hungry turf: keep the nitrogen, but steady.
        slow_min = max(slow_min, 0.4)
        reasons.append("dollar_spot_steady_nitrogen")

    # A declining lawn in the growing season can take a little more, and some of it quick.
    if (
        ctx.status_score is not None
        and ctx.status_score < 2.5
        and ctx.growing
        and role in ("growth", "greening")
    ):
        n *= 1.2
        reasons.append("lawn_declining_more_nitrogen")

    # Sandy soil leaches: slow release and two half doses.
    if ctx.soil_type in ("sandy", "sandy_loam"):
        slow_min = max(slow_min, 0.5)
        split = True
        reasons.append("sandy_soil_split_slow")

    # Rain in the next days waters the granules in; a lot of it would wash them out.
    if 3 <= ctx.expected_rain_72h < 15:
        reasons.append("rain_will_water_in")

    # Late autumn: quick potassium is taken up before the cold; nitrogen stays moderate.
    if role == "autumn":
        slow_min = min(slow_min, 0.3)
        reasons.append("autumn_potassium_hardiness")

    n = round(max(MIN_N_PER_APPLICATION, min(MAX_N_PER_APPLICATION, n)), 1)
    preset, dose = _match_preset(role, n, slow_min)
    return FeedPlan(
        role=role,
        ratio=RATIOS[role],
        n_g_m2=n,
        slow_fraction_min=slow_min,
        split=split,
        preset=preset,
        dose_g_m2=dose,
        reasons=tuple(reasons),
    )


def _match_preset(role: str, n_g_m2: float, slow_min: float) -> tuple[str | None, float | None]:
    """Return the preset for the role and the dose that delivers the nitrogen, within label."""
    candidates = [
        f for f in fertilizers.PRESETS.values() if f.role == role and f.slow_fraction >= slow_min
    ] or [f for f in fertilizers.PRESETS.values() if f.role == role]
    if not candidates:
        return None, None
    product = candidates[0]
    if product.n <= 0:
        return product.id, product.default_dose_g_m2
    dose = n_g_m2 * 100.0 / product.n
    low, high = product.dose_g_m2
    return product.id, round(max(low, min(high, dose)))
