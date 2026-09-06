"""Where a lawn's weather comes from, in one shape.

Two sources, one dictionary. The station in the garden is the ground truth for a lawn that
has one, but it can be sheltered, dirty or missing days; a reanalysis for the same
coordinates has none of those faults and reaches back years. Both are returned in the same
units — degrees, percent, metres a second at two metres, megajoules a square metre, and
millimetres — so nothing downstream has to know which it is looking at.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.hosekeeper.engine import et

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
DAILY = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "shortwave_radiation_sum",
    "wind_speed_10m_mean",
    "relative_humidity_2m_mean",
    "et0_fao_evapotranspiration",
)

Series = dict[str, dict[dt.date, float]]


def believable_wind(measured_ms: float | None) -> float:
    """Return the wind to compute with, distrusting an anemometer in the lee of a house."""
    if measured_ms is None or measured_ms < 0.5:
        return 2.0
    return measured_ms


def believable_sun(measured_mj: float | None, estimate_mj: float) -> float:
    """Return the radiation to compute with, distrusting a pyranometer in the shade."""
    if measured_mj is None or measured_mj < 0.7 * estimate_mj:
        return estimate_mj
    return measured_mj


def from_file(path: Path) -> Series:
    """Return the daily series saved in a file by `save`.

    The preview uses one of these rather than the network: the sample lawn should be the
    same lawn for everybody, on a train as well as at a desk.
    """
    raw = json.loads(path.read_text())
    return {
        name: {dt.date.fromisoformat(day): value for day, value in series.items()}
        for name, series in raw.items()
        if not name.startswith("_")
    }


def save(series: Series, path: Path, comment: str) -> None:
    """Write a daily series to a file, dates as text."""
    out: dict[str, object] = {"_comment": comment}
    out |= {
        name: {day.isoformat(): round(value, 2) for day, value in days.items()}
        for name, days in series.items()
    }
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")


def from_statistics(path: Path, prefix: str) -> Series:
    """Return the daily series from Home Assistant's own statistics."""
    raw = json.loads(path.read_text())

    def series(name: str, key: str) -> dict[dt.date, float]:
        return {
            dt.datetime.fromtimestamp(row["start"] / 1000).date(): row[key]
            for row in raw.get(f"{prefix}{name}", [])
            if row.get(key) is not None
        }

    cumulative = series("rain", "sum")
    rain: dict[dt.date, float] = {}
    previous: float | None = None
    for day in sorted(cumulative):
        rain[day] = max(0.0, cumulative[day] - previous) if previous is not None else 0.0
        previous = cumulative[day]
    return {
        "tmax": series("temperature", "max"),
        "tmin": series("temperature", "min"),
        "rh": series("humidity", "mean"),
        # The station reads km/h at about lawn height, which is close enough to the two
        # metres the equations want.
        "wind": {day: value / 3.6 for day, value in series("wind_speed", "mean").items()},
        # A daily mean in watts is a day's energy once it is spread over the day's seconds.
        "solar": {
            day: value * 86400 / 1e6 for day, value in series("solar_radiation", "mean").items()
        },
        "rain": rain,
    }


def from_open_meteo(latitude: float, longitude: float, start: dt.date, end: dt.date) -> Series:
    """Return the daily series for a place from the Open-Meteo archive.

    A reanalysis rather than a forecast: what the atmosphere actually did over those
    coordinates, free and without a key. It is also the only way to check whether a garden
    station is telling the truth.
    """
    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": ",".join(DAILY),
            "timezone": "auto",
        }
    )
    with urlopen(f"{ARCHIVE}?{query}", timeout=60) as response:
        payload = json.loads(response.read())
    daily = payload["daily"]
    days = [dt.date.fromisoformat(value) for value in daily["time"]]

    def series(name: str) -> dict[dt.date, float]:
        return {
            day: value for day, value in zip(days, daily[name], strict=True) if value is not None
        }

    wind_10m = series("wind_speed_10m_mean")
    return {
        "tmax": series("temperature_2m_max"),
        "tmin": series("temperature_2m_min"),
        "rh": series("relative_humidity_2m_mean"),
        "wind": {day: et.wind_10m_to_2m(value / 3.6) for day, value in wind_10m.items()},
        "solar": series("shortwave_radiation_sum"),
        "rain": series("precipitation_sum"),
        "et0_reference": series("et0_fao_evapotranspiration"),
    }
