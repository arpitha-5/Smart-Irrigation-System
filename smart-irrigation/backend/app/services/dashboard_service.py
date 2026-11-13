from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.timescale import hypertable_status
from app.models import Crop, Farmer, Field, Sensor, SensorReading, WeatherData
from app.services import quality_service, sensor_service, weather_service


def summary(db: Session) -> dict:
    farmers = db.scalar(select(func.count()).select_from(Farmer)) or 0
    fields = db.scalar(select(func.count()).select_from(Field)) or 0
    crops = db.scalar(select(func.count()).select_from(Crop)) or 0
    sensors = db.scalar(select(func.count()).select_from(Sensor)) or 0
    active = db.scalar(select(func.count()).select_from(Sensor).where(Sensor.status == "active")) or 0
    latest_readings = sensor_service.list_readings(db, None, None, None, None, 8)
    latest_weather = list(db.scalars(select(WeatherData).order_by(WeatherData.timestamp.desc()).limit(1)))
    dq = quality_service.stats(db)

    # Detect TimescaleDB active hypertables
    ts_info = hypertable_status(db.get_bind())  # the engine this session is bound to
    timescale_active = bool(ts_info.get("available") and len(ts_info.get("hypertables", [])) > 0)

    # Active risk alerts
    from app.models.alert import Alert
    active_alerts_count = db.scalar(
        select(func.count(Alert.alert_id)).where(Alert.status.in_(("open", "acknowledged")))
    ) or 0
    recent_alerts = list(
        db.scalars(
            select(Alert)
            .where(Alert.status.in_(("open", "acknowledged")))
            .order_by(Alert.created_at.desc())
            .limit(5)
        )
    )

    return {
        "farmers": farmers,
        "fields": fields,
        "crops": crops,
        "sensors": sensors,
        "active_sensors": active,
        "active_alerts_count": active_alerts_count,
        "recent_alerts": [
            {
                "alert_id": a.alert_id,
                "field_id": a.field_id,
                "sensor_id": a.sensor_id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "status": a.status,
                "message": a.message,
                "recommended_action": a.recommended_action,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in recent_alerts
        ],
        "readings_stored": dq["readings_stored"],
        "valid_readings": dq["valid_readings"],
        "simulated_readings": dq["simulated_readings"],
        "ingestion_failures": dq["ingestion_failures"],
        "weather_observations": dq["weather_observations"],
        "timescale_active": timescale_active,
        "timescale_version": ts_info.get("version"),
        "hypertables": [h["name"] for h in ts_info.get("hypertables", [])],
        "latest_readings": latest_readings,
        "latest_weather": latest_weather[0] if latest_weather else None,
        "data_quality": {
            "readings_stored": dq["readings_stored"],
            "ingestion_failures": dq["ingestion_failures"],
            "duplicate_count": dq["duplicate_count"],
            "out_of_range_count": dq["out_of_range_count"],
            "missing_value_count": dq["missing_value_count"],
        },
    }