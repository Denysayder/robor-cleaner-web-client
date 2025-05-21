from datetime import datetime, timedelta
import json
import requests
from sqlalchemy.sql import text

from config import Config
from models import db
from models import UserSettings
from flask import session


def weather_forecast(lat=None, lon=None):
    uid = session["user_id"]
    settings = UserSettings.query.get(uid)
    lat = lat or settings.lat or Config.WEATHER_LAT
    lon = lon or settings.lon or Config.WEATHER_LON

    row = db.session.execute(
        text("SELECT payload, fetched_at FROM weather_cache WHERE user_id=:uid"),
        {"uid": uid},
    ).first()
    if row and datetime.utcnow() - row.fetched_at < timedelta(minutes=30):
        return json.loads(row.payload)
    url = Config.WEATHER_API_URL.format(
        lat=lat, lon=lon
    )
    params = {"apikey": Config.WEATHER_API_KEY} if Config.WEATHER_API_KEY else {}
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    db.session.execute(
        text(
            "INSERT INTO weather_cache (user_id, fetched_at, payload) "
            "VALUES (:uid, :fetched_at, :payload) "
            "ON DUPLICATE KEY UPDATE fetched_at=:fetched_at, payload=:payload"
        ),
        {"uid": uid, "fetched_at": datetime.utcnow(), "payload": json.dumps(data)},
    )
    db.session.commit()
    return data


def publish_robot(conn, command):
    uid = session["user_id"]
    conn.publish(f"user:{uid}:robot:commands", command)


def chart_data():
    uid = session["user_id"]
    rows = db.session.execute(
        text(
            "SELECT recorded_at, energy_generated_kwh, energy_saved_kwh "
            "FROM energy_stats WHERE user_id=:uid ORDER BY recorded_at"
        ),
        {"uid": uid},
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
