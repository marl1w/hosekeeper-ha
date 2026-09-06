"""Save Home Assistant's daily statistics for a weather station to a file.

    HA_URL=... HA_TOKEN=... python scripts/pull_stats.py 45 > scripts/local/stats.json

Long-term statistics survive the recorder's purge, so this reaches back months where the
history API reaches back days. `scripts/replay.py` reads what this writes.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import sys

import aiohttp

# The default names a role. Pass your own entity ids as arguments: a station's ids say where
# it stands, so none of yours belong in a file that is committed.
SENSORS = [
    "sensor.weather_station_temperature",
    "sensor.weather_station_humidity",
    "sensor.weather_station_wind_speed",
    "sensor.weather_station_solar_radiation",
    "sensor.weather_station_rain",
]


async def pull(days: int, sensors: list[str]) -> dict:
    """Return the daily statistics for `sensors` over the last `days`."""
    url = os.environ["HA_URL"].replace("http", "ws", 1) + "/api/websocket"
    async with aiohttp.ClientSession() as session, session.ws_connect(url, max_msg_size=0) as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": os.environ["HA_TOKEN"]})
        auth = await ws.receive_json()
        if auth.get("type") != "auth_ok":
            raise SystemExit(f"authentication failed: {auth}")
        await ws.send_json(
            {
                "id": 1,
                "type": "recorder/statistics_during_period",
                "start_time": (dt.datetime.now(dt.UTC) - dt.timedelta(days=days)).isoformat(),
                "statistic_ids": sensors,
                "period": "day",
                "types": ["mean", "min", "max", "sum", "state"],
            }
        )
        while True:
            message = await ws.receive_json()
            if message.get("id") == 1:
                return message.get("result", {})


def main() -> None:
    """Write the statistics to standard output as JSON."""
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 45
    sensors = sys.argv[2:] or SENSORS
    print(json.dumps(asyncio.run(pull(days, sensors))))


if __name__ == "__main__":
    main()
