from datetime import datetime, timedelta
import json
import requests
from sqlalchemy.sql import text

from config import Config
from models import db


def weather_forecast():
    row = db.session.execute(
        text(
            "SELECT payload, fetched_at FROM weather_cache "
            "WHERE lat=:lat AND lon=:lon LIMIT 1"
        ),
        {"lat": Config.WEATHER_LAT, "lon": Config.WEATHER_LON},
    ).first()
    if row and datetime.utcnow() - row.fetched_at < timedelta(minutes=30):
        return json.loads(row.payload)
    url = Config.WEATHER_API_URL.format(
        lat=Config.WEATHER_LAT, lon=Config.WEATHER_LON
    )
    params = {"apikey": Config.WEATHER_API_KEY} if Config.WEATHER_API_KEY else {}
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    db.session.execute(
        text(
            "INSERT INTO weather_cache (fetched_at, lat, lon, payload) "
            "VALUES (:fetched_at, :lat, :lon, :payload) "
            "ON DUPLICATE KEY UPDATE fetched_at=:fetched_at, payload=:payload"
        ),
        {
            "fetched_at": datetime.utcnow(),
            "lat": Config.WEATHER_LAT,
            "lon": Config.WEATHER_LON,
            "payload": json.dumps(data),
        },
    )
    db.session.commit()
    return data


def publish_robot(conn, command):
    conn.publish("robot:commands", command)


def chart_data():
    rows = db.session.execute(
        text(
            "SELECT recorded_at, energy_generated_kwh, energy_saved_kwh "
            "FROM energy_stats ORDER BY recorded_at"
        )
    ).all()
    labels, generated, saved = [], [], []
    for recorded_at, gen_kwh, saved_kwh in rows:
        labels.append(recorded_at.strftime("%Y-%m-%d %H:%M"))
        generated.append(float(gen_kwh))
        saved.append(float(saved_kwh))
    return {
        "labels": labels,
        "datasets": [
            {"label": "Energy Generated (kWh)", "data": generated},
            {"label": "Energy Saved (kWh)", "data": saved},
        ],
    }
