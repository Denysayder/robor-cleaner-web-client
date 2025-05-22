from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from services import weather_forecast


TZ = ZoneInfo("Europe/Kyiv")


def suggest_cleaning_time(lat=None, lon=None):
    data = weather_forecast(lat, lon)
    now = datetime.now(TZ)

    times = data["hourly"]["time"]
    pops = data["hourly"]["precipitation_probability"]

    for i in range(min(len(times), 48)):
        t = datetime.fromisoformat(times[i]).replace(tzinfo=TZ)
        if t < now:
            continue
        if pops[i] >= 10:
            continue
        if 6 <= t.hour < 18:
            continue
        return t

    return None

