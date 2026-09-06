"""FAO-56 worked examples, so the arithmetic is pinned to the paper and not to itself."""

from __future__ import annotations

import pytest

from custom_components.hosekeeper.engine import et


def test_extraterrestrial_radiation_example_8() -> None:
    # Example 8: 20°S on 3 September (day 246) gives Ra = 32.2 MJ m⁻² day⁻¹.
    assert et.extraterrestrial_radiation(-20.0, 246) == pytest.approx(32.2, abs=0.1)


def test_daylight_hours_example_9() -> None:
    # Example 9: same place and day, N = 11.7 hours.
    assert et.daylight_hours(-20.0, 246) == pytest.approx(11.7, abs=0.05)


def test_saturation_vapour_pressure_table() -> None:
    # Table 2.3: e°(24.5 °C) = 3.075 kPa, e°(15 °C) = 1.705 kPa.
    assert et.saturation_vapour_pressure(24.5) == pytest.approx(3.075, abs=0.005)
    assert et.saturation_vapour_pressure(15.0) == pytest.approx(1.705, abs=0.005)


def test_psychrometric_constant_example_2() -> None:
    # Example 2: 1800 m gives P = 81.8 kPa and gamma = 0.054 kPa °C⁻¹.
    assert et.atmospheric_pressure(1800) == pytest.approx(81.8, abs=0.1)
    assert et.psychrometric_constant(1800) == pytest.approx(0.054, abs=0.001)


def test_wind_profile_example_14() -> None:
    # Example 14: 3.2 m/s at 10 m is 2.4 m/s at 2 m.
    assert et.wind_10m_to_2m(3.2) == pytest.approx(2.4, abs=0.05)


def test_penman_monteith_example_18() -> None:
    # Example 18: Brussels (50°48'N, 100 m), 6 July. Tmax 21.5, Tmin 12.3, RH 84/63,
    # u2 2.78 m/s, Rs 22.07 MJ m⁻² day⁻¹ → ET₀ = 3.9 mm/day. The paper uses RHmax and
    # RHmin separately; a single mean is a few hundredths of a kPa off, hence the tolerance.
    day = et.WeatherDay(tmax=21.5, tmin=12.3, rh_mean=73.5, wind_2m_ms=2.78, rs_mj=22.07)
    et0 = et.penman_monteith_et0(day, latitude_deg=50.8, elevation_m=100, day_of_year=187)
    assert et0 == pytest.approx(3.9, abs=0.15)


def test_hargreaves_example_20() -> None:
    # Example 20: Lyon (45°43'N), July, Tmax 26.6, Tmin 14.8, Ra 40.6 → ET₀ = 5.0 mm/day.
    assert et.hargreaves_et0(26.6, 14.8, 40.6) == pytest.approx(5.0, abs=0.1)


def test_radiation_from_temperature_example_15() -> None:
    # Example 15: Lyon, July, Ra 40.6, Tmax 26.6, Tmin 14.8 → Rs = 22.3 MJ m⁻² day⁻¹.
    assert et.solar_radiation_from_temperature(26.6, 14.8, 40.6) == pytest.approx(22.3, abs=0.1)


def test_best_method_is_chosen_from_the_data() -> None:
    full = et.WeatherDay(30.0, 18.0, rh_mean=50.0, wind_2m_ms=1.5, rs_mj=25.0)
    partial = et.WeatherDay(30.0, 18.0)
    _, method = et.reference_et0(full, latitude_deg=45.0, elevation_m=250, day_of_year=200)
    assert method == "penman_monteith"
    _, method = et.reference_et0(partial, latitude_deg=45.0, elevation_m=250, day_of_year=200)
    assert method == "hargreaves"


def test_penman_monteith_refuses_missing_inputs() -> None:
    with pytest.raises(ValueError, match="humidity"):
        et.penman_monteith_et0(
            et.WeatherDay(30.0, 18.0), latitude_deg=45.0, elevation_m=250, day_of_year=200
        )


def test_hot_dry_summer_day_in_the_po_valley() -> None:
    # A sanity check on the order of magnitude: a 34/22 °C day with 40 % humidity, light
    # wind and a clear sky should evaporate 6 to 7 mm from a reference lawn.
    day = et.WeatherDay(34.0, 22.0, rh_mean=40.0, wind_2m_ms=1.0, rs_mj=26.0)
    et0 = et.penman_monteith_et0(day, latitude_deg=45.0, elevation_m=280, day_of_year=200)
    assert 5.5 < et0 < 7.5
