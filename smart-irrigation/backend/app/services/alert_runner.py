"""Runs the alert rules when a reading arrives and when a sensor goes quiet.

It stores alerts through alert_service and returns what changed.
Outbound notifications are dynamically dispatched to the specific farmer
who owns the field where the alert occurred.
"""
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.farmer import utcnow
from app.models.sensor import Sensor
from app.models.sensor_reading import SensorReading
from app.services import alert_service
from app.services.alert_service import AlertChange
from app.services.rule_engine import AlertType, check_sensor_silence, evaluate_reading

log = logging.getLogger("irrigation.alerts")

# A soil-moisture reading can raise or clear all three alert types.
_MOISTURE_CHECK = {AlertType.DROUGHT, AlertType.OVER_WATERING, AlertType.SENSOR_FAILURE}
# Any other reading (temperature, humidity, ...) only proves the sensor is alive.
_ALIVE_ONLY = {AlertType.SENSOR_FAILURE}


def process_reading(db: Session, reading: SensorReading, now: Optional[datetime] = None) -> List[AlertChange]:
    """Evaluate one stored reading and update the field's alerts."""
    now = now or utcnow()
    if reading.quality_flags and "out_of_order" in reading.quality_flags:
        return []   # an old reading says nothing about the current state of the field

    thresholds = alert_service.get_thresholds(db, reading.field_id)
    is_moisture = (reading.measurement_type or "soil_moisture") == "soil_moisture" \
        and reading.soil_moisture is not None
    moisture = reading.soil_moisture if is_moisture else None

    # The data has just arrived, so the sensor is not silent right now.
    found = evaluate_reading(moisture, now, now, thresholds)
    managed = _MOISTURE_CHECK if is_moisture else _ALIVE_ONLY
    changes = alert_service.sync_alerts(db, reading.field_id, reading.sensor_id, found, now, managed)
    _log_changes(reading.sensor_id, changes)
    _dispatch_alert_notifications(db, changes, reading.field_id)
    return changes


def check_silent_sensors(db: Session, now: Optional[datetime] = None) -> List[AlertChange]:
    """Find active sensors that have stopped sending data. Run this on a schedule."""
    now = now or utcnow()
    changes: List[AlertChange] = []
    sensors = db.scalars(select(Sensor).where(Sensor.status == "active")).all()
    for sensor in sensors:
        thresholds = alert_service.get_thresholds(db, sensor.field_id)
        if sensor.last_seen_at is None:
            created = sensor.created_at or now
            if (now - created).total_seconds() / 60 < thresholds.sensor_silent_minutes:
                continue   # brand-new sensor: give it time to send its first reading
        found = check_sensor_silence(sensor.last_seen_at, now, thresholds)
        sensor_changes = alert_service.sync_alerts(
            db, sensor.field_id, sensor.sensor_id, [found] if found else [], now, {AlertType.SENSOR_FAILURE},
        )
        _log_changes(sensor.sensor_id, sensor_changes)
        _dispatch_alert_notifications(db, sensor_changes, sensor.field_id)
        changes.extend(sensor_changes)
    return changes


def _log_changes(sensor_id: str, changes: List[AlertChange]) -> None:
    for change in changes:
        if change.kind in ("new", "escalated", "resolved"):
            log.info("Alert %s: sensor=%s type=%s severity=%s",
                     change.kind, sensor_id, change.alert.alert_type, change.alert.severity)


def _dispatch_alert_notifications(db: Session, changes: List[AlertChange], field_id: str) -> None:
    """Dispatches notifications dynamically to the specific farmer or user owning this field."""
    active_changes = [c for c in changes if c.kind in ("new", "escalated")]
    if not active_changes:
        return

    try:
        from app.models.field import Field
        from app.models.user import User
        from app.services.notification_worker import NotificationWorker

        field = db.get(Field, field_id)
        recipient_phone = None
        recipient_email = None

        if field and field.farmer:
            recipient_phone = field.farmer.phone
            recipient_email = field.farmer.email

        # If farmer has no phone, try finding matching registered User by email
        if not recipient_phone and recipient_email:
            user = db.query(User).filter(User.email == recipient_email).first()
            if user and user.phone:
                recipient_phone = user.phone

        if not recipient_phone and not recipient_email:
            return

        worker = NotificationWorker()
        crop_name = getattr(field, "crop_type", "Crop") if field else "Crop"
        field_name = field.name if field else field_id

        for change in active_changes:
            alert = change.alert
            message = (
                f"🚨 AgriPulse Alert [{alert.severity}]: {field_name} ({crop_name}) - "
                f"{alert.message} Recommended: {alert.recommended_action or 'Check root zone.'}"
            )
            if recipient_phone:
                try:
                    worker._send_whatsapp(recipient_phone, message)
                except Exception as e:
                    log.warning("WhatsApp dispatch error: %s", e)
                try:
                    worker._send_sms(recipient_phone, message[:160])
                except Exception as e:
                    log.warning("SMS dispatch error: %s", e)
            if recipient_email:
                try:
                    worker._send_email(
                        recipient_email,
                        f"Smart Irrigation Alert: {alert.severity} on {field_name}",
                        message,
                    )
                except Exception as e:
                    log.warning("Email dispatch error: %s", e)
    except Exception as exc:
        log.warning("Automated alert dispatch failed: %s", exc)
