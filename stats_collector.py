from datetime import datetime, timezone
import time
import redis
from sqlalchemy import create_engine, text
from config import Config

redis_conn = redis.from_url(Config.REDIS_URL, ssl_cert_reqs=None, decode_responses=True)
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True, future=True)

def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0

ROUND   = 6
INTERVAL = 10           # секунд

while True:
    t = redis_conn.hgetall("telemetry")
    if t:
        p_watt = f(t.get("sensor1"))
        print(p_watt)
        gen = round(p_watt / 1000 * INTERVAL / 3600, ROUND)
        print(gen)
        if gen:
            sav = round(gen * 0.15, ROUND)
            ts = datetime.now(timezone.utc).replace(microsecond=0)
            with engine.begin() as c:
                c.execute(
                    text(
                        "INSERT INTO energy_stats "
                        "(recorded_at, energy_generated_kwh, energy_saved_kwh) "
                        "VALUES (:ts, :g, :s) "
                        "ON DUPLICATE KEY UPDATE "
                        "energy_generated_kwh = energy_generated_kwh + :g, "
                        "energy_saved_kwh     = energy_saved_kwh     + :s"
                    ),
                    {"ts": ts, "g": gen, "s": sav},
                )
    time.sleep(INTERVAL)
