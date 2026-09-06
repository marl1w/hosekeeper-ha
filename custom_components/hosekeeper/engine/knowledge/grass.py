"""What each grass type needs: crop coefficient, rooting depth, mowing heights.

Turf crop coefficients follow the Irrigation Association / ASABE practice of treating
cool-season turf around 0.8 and warm-season around 0.6 of reference ET, with a summer
lift for cool-season species that are still actively transpiring, and a winter drop for
warm-season species that go dormant. Rooting depths are effective depths for irrigation
scheduling, not maximum root length. See docs/knowledge.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GrassProfile:
    """Season-independent facts about one grass type."""

    cool_season: bool
    kc_active: float
    kc_shoulder: float
    kc_dormant: float
    root_depth_m: float
    mow_height_mm: tuple[int, int]
    """Recommended cutting height range, low to high."""


_COOL = GrassProfile(
    cool_season=True,
    kc_active=0.85,
    kc_shoulder=0.80,
    kc_dormant=0.60,
    root_depth_m=0.20,
    mow_height_mm=(50, 80),
)

PROFILES: dict[str, GrassProfile] = {
    "cool_season_mix": _COOL,
    "tall_fescue": GrassProfile(True, 0.85, 0.80, 0.60, 0.30, (60, 90)),
    "perennial_ryegrass": GrassProfile(True, 0.85, 0.80, 0.60, 0.20, (40, 70)),
    "kentucky_bluegrass": GrassProfile(True, 0.85, 0.80, 0.60, 0.20, (50, 80)),
    "fine_fescue": GrassProfile(True, 0.80, 0.75, 0.60, 0.20, (50, 90)),
    "microclover_mix": GrassProfile(True, 0.85, 0.80, 0.60, 0.20, (50, 80)),
    "bermuda": GrassProfile(False, 0.65, 0.60, 0.30, 0.30, (25, 50)),
    "zoysia": GrassProfile(False, 0.65, 0.60, 0.30, 0.30, (25, 50)),
    "st_augustine": GrassProfile(False, 0.70, 0.65, 0.35, 0.25, (60, 100)),
    "dichondra": GrassProfile(False, 0.75, 0.70, 0.50, 0.15, (20, 40)),
}


def profile(grass_type: str) -> GrassProfile:
    """Return the profile for a grass type, falling back to a cool-season mix."""
    return PROFILES.get(grass_type, _COOL)


def mowing_range(grass_type: str, deck_mm: tuple[int, int] | None) -> tuple[int, int]:
    """Return the heights to advise: what the species wants, on the mower there is.

    The species range is an agronomic ideal and the deck is the hardware. Tall fescue asks
    for 60-90 mm; a robot whose deck runs 20-60 mm cannot be set to 75, so advising it names
    a setting that is not on the dial and the advice is simply ignored. Where the two ranges
    overlap, the overlap is what to advise. Where they do not, the nearest height the machine
    can reach is — which for a tall species on a low deck means cutting at the deck's top,
    the standing recommendation whenever the grass cannot be given the height it wants.
    """
    low, high = profile(grass_type).mow_height_mm
    if not deck_mm:
        return low, high
    floor, ceiling = min(deck_mm), max(deck_mm)
    clamp = lambda mm: int(min(max(mm, floor), ceiling))  # noqa: E731
    return clamp(low), clamp(high)


# How deep the roots actually are, which is not the depth a mature lawn of that species
# reaches. Sod is laid with two or three centimetres of soil and knits downward over a
# season; seed starts shallower still. A lawn that struggled in its first summer has less
# again. Watering a young lawn against a mature root depth is how a schedule ends up
# watering deeply and rarely a lawn that cannot yet reach the water. FAO-56 chapter 8 treats
# rooting depth as growing with the crop; this is the same idea on a turf timescale.
SOD_START_DEPTH_M = 0.06
SEED_START_DEPTH_M = 0.03
SOD_MATURE_DAYS = 300
SEED_MATURE_DAYS = 400


def root_depth(grass_type: str, age_days: int | None, method: str) -> float:
    """Return the effective rooting depth of this lawn, in metres."""
    mature = profile(grass_type).root_depth_m
    if age_days is None:
        return mature
    start = SOD_START_DEPTH_M if method == "sod" else SEED_START_DEPTH_M
    span = SOD_MATURE_DAYS if method == "sod" else SEED_MATURE_DAYS
    if age_days >= span:
        return mature
    grown = start + (mature - start) * (max(0, age_days) / span)
    return round(min(mature, grown), 3)


def crop_coefficient(grass_type: str, month: int, northern_hemisphere: bool = True) -> float:
    """Return Kc for a grass type in a month.

    The calendar is folded so that "summer" is June to August north of the equator and
    December to February south of it.
    """
    grass = profile(grass_type)
    if not northern_hemisphere:
        month = (month + 5) % 12 + 1
    if grass.cool_season:
        # Cool-season turf works hardest in the shoulder months and slows in high summer
        # heat, but its ET peaks with the summer evaporative demand, so Kc stays up.
        if month in (6, 7, 8):
            return grass.kc_active
        if month in (4, 5, 9, 10):
            return grass.kc_shoulder
        return grass.kc_dormant
    if month in (6, 7, 8):
        return grass.kc_active
    if month in (5, 9, 10):
        return grass.kc_shoulder
    return grass.kc_dormant
