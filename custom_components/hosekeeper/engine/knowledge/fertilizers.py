"""Fertilizers as compositions, so what went on the lawn can be counted as nitrogen.

A handful of presets cover one widely sold Italian range (Bottos) and the generic
types anyone might; anything else is entered as its own N-P-K. What the engine cares about
is grams of nitrogen per square metre and how fast they arrive, not the brand.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Fertilizer:
    """One product or product type."""

    id: str
    name: str
    n: float
    """Nitrogen, percent by weight."""
    p: float
    """Phosphorus as P₂O₅, percent."""
    k: float
    """Potassium as K₂O, percent."""
    slow_fraction: float
    """Share of the nitrogen that is slow or controlled release, 0 to 1."""
    release_days: int
    """Roughly how long the slow fraction keeps feeding."""
    dose_g_m2: tuple[int, int]
    """Label rate, low to high, grams per square metre."""
    role: str
    """starter | greening | growth | stress | autumn | generic — what the programme uses it for."""

    def nitrogen_g_m2(self, dose_g_m2: float) -> float:
        """Return grams of N per m² at a dose."""
        return dose_g_m2 * self.n / 100.0

    @property
    def default_dose_g_m2(self) -> float:
        """Return the middle of the label range."""
        return sum(self.dose_g_m2) / 2.0


PRESETS: dict[str, Fertilizer] = {
    # Bottos, from the manufacturer's data sheets as resold in Italy (see docs/knowledge.md).
    "bottos_pro_start": Fertilizer(
        "bottos_pro_start", "Bottos Pro Start 13-24-10", 13, 24, 10, 0.25, 45, (30, 35), "starter"
    ),
    "bottos_dark_green": Fertilizer(
        "bottos_dark_green",
        "Bottos Dark Green 11-0-0 +3MgO +4.5Fe",
        11,
        0,
        0,
        0.2,
        30,
        (25, 35),
        "greening",
    ),
    "bottos_summer_k": Fertilizer(
        "bottos_summer_k", "Bottos Summer K 10-0-30", 10, 0, 30, 1.0, 90, (30, 40), "stress"
    ),
    "bottos_slow_green": Fertilizer(
        "bottos_slow_green",
        "Bottos Slow Green 22-5-10 +2MgO",
        22,
        5,
        10,
        0.35,
        60,
        (25, 30),
        "growth",
    ),
    "bottos_slow_k": Fertilizer(
        "bottos_slow_k", "Bottos Slow K 13-5-20 +2MgO", 13, 5, 20, 0.43, 60, (30, 35), "stress"
    ),
    "bottos_autumn_k": Fertilizer(
        "bottos_autumn_k", "Bottos Autumn K 21-0-25", 21, 0, 25, 0.40, 60, (25, 30), "autumn"
    ),
    # Generic types.
    "quick_release": Fertilizer(
        "quick_release", "Quick-release mineral", 20, 5, 10, 0.0, 21, (20, 30), "generic"
    ),
    "slow_release": Fertilizer(
        "slow_release", "Slow-release granular", 20, 5, 10, 0.5, 75, (25, 35), "generic"
    ),
    "organic": Fertilizer("organic", "Organic pellets", 6, 3, 4, 0.9, 90, (60, 100), "generic"),
    "liquid": Fertilizer("liquid", "Liquid feed", 10, 2, 5, 0.0, 14, (5, 10), "generic"),
    "iron": Fertilizer("iron", "Iron / moss control", 0, 0, 0, 0.0, 0, (10, 20), "generic"),
}


def custom(n: float, p: float, k: float, slow_fraction: float = 0.3) -> Fertilizer:
    """Return a one-off composition typed in by the user."""
    return Fertilizer(
        "custom", f"Custom {n:g}-{p:g}-{k:g}", n, p, k, slow_fraction, 45, (20, 35), "generic"
    )


def resolve(product: str | None, n: float | None, p: float | None, k: float | None) -> Fertilizer:
    """Return the preset named, or a custom composition, or a generic slow release."""
    if product and product in PRESETS:
        return PRESETS[product]
    if n is not None:
        return custom(n, p or 0.0, k or 0.0)
    return PRESETS["slow_release"]
