"""Reference evapotranspiration after FAO Irrigation and Drainage Paper 56.

Two estimators are provided. Penman-Monteith is the standard and needs radiation,
humidity and wind; Hargreaves-Samani needs only the daily temperature range and is what
a forecast alone can support. Both are checked in tests against the worked examples in
the paper (Example 18 for Penman-Monteith, Example 20 for Hargreaves).
"""

from __future__ import annotations

from dataclasses import dataclass
import math

SOLAR_CONSTANT = 0.0820  # MJ m⁻² min⁻¹
STEFAN_BOLTZMANN = 4.903e-9  # MJ K⁻⁴ m⁻² day⁻¹
ALBEDO_GRASS = 0.23


@dataclass(frozen=True, slots=True)
class WeatherDay:
    """One day of weather, as much of it as is known."""

    tmax: float
    tmin: float
    rh_mean: float | None = None
    """Mean relative humidity, percent."""
    wind_2m_ms: float | None = None
    """Mean wind speed at 2 m, metres per second."""
    rs_mj: float | None = None
    """Incoming solar radiation, MJ m⁻² day⁻¹."""

    @property
    def tmean(self) -> float:
        """Return the daily mean as FAO-56 defines it: the midpoint of the extremes."""
        return (self.tmax + self.tmin) / 2.0

    @property
    def supports_penman_monteith(self) -> bool:
        """Return whether every input the full equation needs is present."""
        return self.rh_mean is not None and self.wind_2m_ms is not None and self.rs_mj is not None


def inverse_relative_distance(day_of_year: int) -> float:
    """Return dr, eq. 23."""
    return 1 + 0.033 * math.cos(2 * math.pi / 365 * day_of_year)


def solar_declination(day_of_year: int) -> float:
    """Return δ in radians, eq. 24."""
    return 0.409 * math.sin(2 * math.pi / 365 * day_of_year - 1.39)


def sunset_hour_angle(latitude_rad: float, declination: float) -> float:
    """Return ωs in radians, eq. 25."""
    return math.acos(max(-1.0, min(1.0, -math.tan(latitude_rad) * math.tan(declination))))


def extraterrestrial_radiation(latitude_deg: float, day_of_year: int) -> float:
    """Return Ra in MJ m⁻² day⁻¹, eq. 21."""
    phi = math.radians(latitude_deg)
    dr = inverse_relative_distance(day_of_year)
    delta = solar_declination(day_of_year)
    ws = sunset_hour_angle(phi, delta)
    return (
        24
        * 60
        / math.pi
        * SOLAR_CONSTANT
        * dr
        * (ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))
    )


def daylight_hours(latitude_deg: float, day_of_year: int) -> float:
    """Return N, eq. 34."""
    ws = sunset_hour_angle(math.radians(latitude_deg), solar_declination(day_of_year))
    return 24 / math.pi * ws


def clear_sky_radiation(ra: float, elevation_m: float) -> float:
    """Return Rso in MJ m⁻² day⁻¹, eq. 37."""
    return (0.75 + 2e-5 * elevation_m) * ra


def solar_radiation_from_temperature(
    tmax: float, tmin: float, ra: float, k_rs: float = 0.16
) -> float:
    """Return Rs estimated from the temperature range, eq. 50.

    k_rs is 0.16 for interior locations and 0.19 near a coast, and interior is the default:
    most lawns are further from the sea than not.
    """
    return k_rs * math.sqrt(max(0.0, tmax - tmin)) * ra


def saturation_vapour_pressure(temperature: float) -> float:
    """Return e°(T) in kPa, eq. 11."""
    return 0.6108 * math.exp(17.27 * temperature / (temperature + 237.3))


def slope_vapour_pressure_curve(temperature: float) -> float:
    """Return Δ in kPa °C⁻¹, eq. 13."""
    return 4098 * saturation_vapour_pressure(temperature) / (temperature + 237.3) ** 2


def atmospheric_pressure(elevation_m: float) -> float:
    """Return P in kPa, eq. 7."""
    return 101.3 * ((293 - 0.0065 * elevation_m) / 293) ** 5.26


def psychrometric_constant(elevation_m: float) -> float:
    """Return gamma in kPa °C⁻¹, eq. 8."""
    return 0.000665 * atmospheric_pressure(elevation_m)


def wind_10m_to_2m(u10: float) -> float:
    """Return wind at 2 m from a 10 m measurement, eq. 47."""
    return u10 * 4.87 / math.log(67.8 * 10 - 5.42)


def hargreaves_et0(tmax: float, tmin: float, ra: float) -> float:
    """Return ET₀ in mm/day, eq. 52.

    Ra is in MJ m⁻² day⁻¹ here and converted to mm of evaporation equivalent inside.
    """
    tmean = (tmax + tmin) / 2.0
    return max(0.0, 0.0023 * (ra * 0.408) * (tmean + 17.8) * math.sqrt(max(0.0, tmax - tmin)))


def penman_monteith_et0(
    day: WeatherDay,
    *,
    latitude_deg: float,
    elevation_m: float,
    day_of_year: int,
) -> float:
    """Return ET₀ in mm/day, eq. 6, from daily means.

    Actual vapour pressure comes from mean relative humidity (eq. 19), the least
    demanding of the paper's options and the one a single humidity sensor supports.
    """
    if not day.supports_penman_monteith:
        raise ValueError("Penman-Monteith needs humidity, wind and radiation")
    assert day.rh_mean is not None and day.wind_2m_ms is not None and day.rs_mj is not None

    tmean = day.tmean
    delta = slope_vapour_pressure_curve(tmean)
    gamma = psychrometric_constant(elevation_m)
    es = (saturation_vapour_pressure(day.tmax) + saturation_vapour_pressure(day.tmin)) / 2.0
    ea = day.rh_mean / 100.0 * es
    ea = min(ea, es)

    ra = extraterrestrial_radiation(latitude_deg, day_of_year)
    rso = clear_sky_radiation(ra, elevation_m)
    rns = (1 - ALBEDO_GRASS) * day.rs_mj
    relative_shortwave = min(1.0, day.rs_mj / rso) if rso > 0 else 1.0
    rnl = (
        STEFAN_BOLTZMANN
        * (((day.tmax + 273.16) ** 4 + (day.tmin + 273.16) ** 4) / 2.0)
        * (0.34 - 0.14 * math.sqrt(ea))
        * (1.35 * relative_shortwave - 0.35)
    )
    rn = rns - rnl
    g = 0.0  # soil heat flux is negligible over a day for grass

    u2 = day.wind_2m_ms
    numerator = 0.408 * delta * (rn - g) + gamma * 900 / (tmean + 273) * u2 * (es - ea)
    denominator = delta + gamma * (1 + 0.34 * u2)
    return max(0.0, numerator / denominator)


def reference_et0(
    day: WeatherDay, *, latitude_deg: float, elevation_m: float, day_of_year: int
) -> tuple[float, str]:
    """Return (ET₀ mm/day, method) using the best estimator the data allows."""
    if day.supports_penman_monteith:
        return (
            penman_monteith_et0(
                day, latitude_deg=latitude_deg, elevation_m=elevation_m, day_of_year=day_of_year
            ),
            "penman_monteith",
        )
    ra = extraterrestrial_radiation(latitude_deg, day_of_year)
    return hargreaves_et0(day.tmax, day.tmin, ra), "hargreaves"
