# utils/event_logger.py  (новый файл)
from datetime import datetime
from flask import session
from models import db, EventLog

def log_event(level: str, component: str, msg: str, user_id: int | None = None):
    """Пишет запись в event_logs и не ломает приложение даже при ошибке."""
    try:
        uid = user_id if user_id is not None else session.get("user_id")
        db.session.add(EventLog(
            user_id=uid, level=level.upper(), component=component, message=msg,
            created_at=datetime.utcnow()))
        db.session.commit()
    except Exception:
        db.session.rollback()
