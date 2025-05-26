from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    energy_stats  = db.relationship("EnergyStat", back_populates="user",
                                    cascade="all, delete-orphan")
    cleaning_logs = db.relationship("CleaningLog", back_populates="user",
                                    cascade="all, delete-orphan")
    settings      = db.relationship("UserSettings", uselist=False, back_populates="user",
                                    cascade="all, delete-orphan")


class UserSettings(db.Model):
    __tablename__ = "user_settings"
    user_id = db.Column(db.Integer,
                        db.ForeignKey("users.id", ondelete="CASCADE"),
                        primary_key=True)
    lat     = db.Column(db.Numeric(8, 5))
    lon     = db.Column(db.Numeric(8, 5))
    user    = db.relationship("User", back_populates="settings")


class EnergyStat(db.Model):
    __tablename__ = "energy_stats"
    id                   = db.Column(db.BigInteger, primary_key=True)
    user_id              = db.Column(db.Integer,
                                     db.ForeignKey("users.id", ondelete="CASCADE"),
                                     nullable=False, index=True)
    recorded_at          = db.Column(db.DateTime, nullable=False)
    energy_generated_kwh = db.Column(db.Numeric(12, 6), default=0)
    energy_saved_kwh     = db.Column(db.Numeric(12, 6), default=0)
    user                 = db.relationship("User", back_populates="energy_stats")


class CleaningLog(db.Model):
    __tablename__ = "cleaning_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    command = db.Column(db.String(64), nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="cleaning_logs")

# models.py  (добавьте после CleaningLog)
class EventLog(db.Model):
    __tablename__ = "event_logs"

    id         = db.Column(db.BigInteger, primary_key=True)
    user_id    = db.Column(db.Integer,
                           db.ForeignKey("users.id", ondelete="SET NULL"),
                           nullable=True, index=True)
    level      = db.Column(db.String(5),  nullable=False)   # INFO/WARN/ERROR
    component  = db.Column(db.String(32), nullable=False)
    message    = db.Column(db.Text,       nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
