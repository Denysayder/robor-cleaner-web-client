import time
import base64
import redis
from flask import Blueprint, Response
from config import Config

bp = Blueprint("stream", __name__, url_prefix="")

redis_conn = redis.from_url(Config.REDIS_URL, ssl_cert_reqs=None)

_BOUNDARY = b"--frame\r\n"
_HEADERS  = b"Content-Type: image/jpeg\r\n\r\n"
_KEYS     = ("robot:frame", "video")


def _decode(payload: bytes) -> bytes | None:
    if not payload:
        return None
    if payload[:2] == b"\xff\xd8":
        return payload
    try:
        txt = payload.decode()
    except UnicodeDecodeError:
        return None
    parts = txt.split("_")
    if parts and parts[-1] == "endframe":
        b64 = parts[1] if len(parts) >= 3 else ""
    else:
        b64 = txt
    try:
        return base64.b64decode(b64)
    except base64.binascii.Error:
        return None


def _gen():
    while True:
        frame = None
        for key in _KEYS:
            data = redis_conn.get(key)
            if data:
                frame = _decode(data)
                if frame:
                    break
        if frame:
            yield _BOUNDARY + _HEADERS + frame + b"\r\n"
        time.sleep(0.05)


@bp.route("/video_feed")
def video_feed():
    return Response(_gen(), mimetype="multipart/x-mixed-replace; boundary=frame")
