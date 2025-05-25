from datetime import datetime, timedelta
import json
import requests
from sqlalchemy.sql import text
import math
from config import Config
from models import db
from models import UserSettings
from flask import session
from datetime import datetime, timedelta


def weather_forecast(lat=None, lon=None):
    uid = session["user_id"]
    settings = UserSettings.query.get(uid)

    lat = lat or settings.lat or Config.WEATHER_LAT
    lon = lon or settings.lon or Config.WEATHER_LON

    row = db.session.execute(
        text("""SELECT payload, fetched_at
                FROM weather_cache
                WHERE user_id = :uid AND lat = :lat AND lon = :lon"""),
        {"uid": uid, "lat": lat, "lon": lon},
    ).first()

    if row and datetime.utcnow() - row.fetched_at < timedelta(minutes=30):
        return json.loads(row.payload)

    url = Config.WEATHER_API_URL.format(lat=lat, lon=lon)
    params = {"apikey": Config.WEATHER_API_KEY} if Config.WEATHER_API_KEY else {}
    data = requests.get(url, params=params, timeout=5).json()

    db.session.execute(
        text("""INSERT INTO weather_cache (user_id, lat, lon, fetched_at, payload)
                VALUES (:uid, :lat, :lon, :ts, :payload)
                ON DUPLICATE KEY UPDATE fetched_at = :ts, payload = :payload"""),
        {"uid": uid, "lat": lat, "lon": lon,
         "ts": datetime.utcnow(), "payload": json.dumps(data)},
    )
    db.session.commit()
    return data



def publish_robot(conn, command):
    uid = session["user_id"]
    conn.publish(f"user:{uid}:robot:commands", command)


def chart_data():
    uid = session["user_id"]

    rows = db.session.execute(
        text("""SELECT recorded_at,
                       energy_generated_kwh,
                       energy_saved_kwh
                FROM energy_stats
                WHERE user_id = :uid
                ORDER BY recorded_at"""),
        {"uid": uid},
    ).all()

    # ── если данных нет, соберём простой «заглушочный» ряд ─────────────
    if not rows:
        now       = datetime.utcnow()
        labels    = []
        generated = []
        saved     = []
        for h in range(24):                      # последние 24 ч
            ts = now - timedelta(hours=23 - h)   # в порядке возрастания
            labels.append(ts.strftime("%H:%M"))
            g = round(max(0.0, 0.4 * math.sin((h - 6) * math.pi / 24)), 3)
            s = round(g * 0.15, 3)               # «сэкономлено» 15 %
            generated.append(g)
            saved.append(s)
        return {
            "labels": labels,
            "datasets": [
                {"label": "Energy Generated (kWh)", "data": generated},
                {"label": "Energy Saved (kWh)",     "data": saved},
            ],
        }

    # ── обычный путь, если реальные записи есть ───────────────────────
    labels, generated, saved = [], [], []
    for recorded_at, gen_kwh, saved_kwh in rows:
        labels.append(recorded_at.strftime("%Y-%m-%d %H:%M"))
        generated.append(float(gen_kwh))
        saved.append(float(saved_kwh))

    return {
        "labels": labels,
        "datasets": [
            {"label": "Energy Generated (kWh)", "data": generated},
            {"label": "Energy Saved (kWh)",     "data": saved},
        ],
    }