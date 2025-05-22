from functools import wraps
from datetime import datetime
import json
import shutil, os

import redis
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
)
from models import UserSettings
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

from config import Config
from models import db, User, CleaningLog
from services import weather_forecast, publish_robot, chart_data
from stream import bp as stream_bp
import subprocess
from intelligent_planner import suggest_cleaning_time

app = Flask(__name__)
app.config.from_object(Config)
app.register_blueprint(stream_bp)

SYSTEMCTL = shutil.which("systemctl")

@app.context_processor
def inject_now():
    return {"datetime": datetime}

db.init_app(app)
redis_conn = redis.from_url(app.config["REDIS_URL"], ssl_cert_reqs=None)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return fn(*args, **kwargs)
    return wrapper

with app.app_context():
    db.create_all()

@app.route("/")
def index() -> str:
    return redirect(url_for("dashboard"))

@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        if not username or not password:
            return "Недостаточно данных", 400
        if User.query.filter_by(username=username).first():
            return "Пользователь уже существует", 409
        user = User(
            username=username, password_hash=generate_password_hash(password, "scrypt")
        )
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return "Неверные учётные данные", 401
        session["user_id"] = user.id
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout() -> str:
    session.pop("user_id", None)
    return redirect(url_for("login_page"))

@app.route("/dashboard")
@login_required
def dashboard() -> str:
    return render_template("dashboard.html")

@app.route("/api/weather")
@login_required
def api_weather():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    forecast = weather_forecast(lat, lon)
    return jsonify(forecast)

@app.route("/api/chart-data")
@login_required
def api_chart_data():
    data = chart_data()
    return jsonify(data)

@app.route("/api/robot", methods=["POST"])
@login_required
def api_robot():
    payload = request.get_json(silent=True) or {}
    command = payload.get("command")
    if not command:
        return jsonify({"error": "command required"}), 400
    publish_robot(redis_conn, command)
    log = CleaningLog(
        user_id=session["user_id"],
        command=command,
        issued_at=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"status": "ok"}), 200


@app.route("/api/settings", methods=["GET", "PUT"])
@login_required
def api_settings():
    uid = session["user_id"]

    if request.method == "GET":
        s = UserSettings.query.get(uid)
        return jsonify({"lat": s.lat if s else None,
                        "lon": s.lon if s else None})

    data = request.get_json(force=True)
    lat, lon = data.get("lat"), data.get("lon")

    s = UserSettings.query.get(uid) or UserSettings(user_id=uid)
    s.lat, s.lon = lat, lon
    db.session.add(s)
    db.session.execute(text("DELETE FROM weather_cache WHERE user_id=:uid"),
        {"uid": uid})
    db.session.commit()
    return "", 204

@app.route("/api/pipeline", methods=["POST"])
@login_required
def api_pipeline():
    action = request.json.get("action")
    uid    = session["user_id"]
    svc    = f"robot-worker@{uid}"
    if SYSTEMCTL is None:
        if action == "status":
            status = (redis_conn.get(f"user:{uid}:robot:state") or b"inactive").decode()
            return jsonify({"status": status})
        elif action in ("start", "stop"):
            redis_conn.set(f"user:{uid}:robot:state",
                           "active" if action == "start" else "inactive",
                           ex=30)
            return "", 204
        return jsonify(error="unknown action"), 400

    if action == "start":
        subprocess.run([SYSTEMCTL, "start",svc], check=True)
    elif action == "stop":
        subprocess.run([SYSTEMCTL, "stop",svc], check=True)
    elif action == "status":
        out = subprocess.check_output([SYSTEMCTL, "is-active", svc]).decode().strip()
        return jsonify({"status": out})
    else:
        return jsonify(error="unknown action"), 400
    return "", 204

@app.route("/api/telemetry")
@login_required
def api_telemetry():
    """
    Возвращает уровень заряда батареи.
    • если worker активен — берём из Redis
    • если worker неактивен или ключа нет — возвращаем 100 %
    """
    uid     = session["user_id"]
    battery = 100.0

    hash_key = f"user:{uid}:telemetry"
    try:
        value = redis_conn.hget(hash_key, "battery")
        if value is not None:
            battery = float(value)
    except Exception:
        pass

    if battery == 100.0:
        for key in (
            f"user:{uid}:robot:battery",
            f"user:{uid}:battery",
        ):
            raw = redis_conn.get(key)
            if not raw:
                continue
            try:
                if raw.startswith(b"{"):
                    battery = float(json.loads(raw).get("battery", battery))
                else:
                    battery = float(raw)
                break
            except Exception:
                continue

    return jsonify({"battery": battery})


@app.route("/api/best_cleaning_time")
@login_required
def best_cleaning_time():
    uid = session["user_id"]
    settings = UserSettings.query.get(uid)
    t = suggest_cleaning_time(settings.lat, settings.lon)
    if t is None:
        return jsonify(best_time="Немає безпечного вікна в найближчі 48 год.")
    return jsonify(best_time=t.strftime("%d %b %Y %H:%M"))

if __name__ == "__main__":
    app.secret_key = Config.SECRET_KEY
    app.run(debug=True, threaded=True)
