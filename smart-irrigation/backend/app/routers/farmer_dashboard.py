"""Farmer-specific dashboard endpoints.

Provides aggregated statistics, water usage analytics, and alert center for the authenticated farmer.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import Farmer, Field, Sensor, SensorReading, IrrigationSchedule, WeatherData
from app.schemas.farmer_dashboard import (
    FarmerDashboardResponse,
    WaterAnalytics,
    BaselineComparison,
    FieldWaterUsage,
    FieldCondition,
    AlertItem,
)
from app.routers.auth import get_current_user, get_farmer_profiles_for_user
from app.models.user import User
from app.services.irrigation_service import recommend_irrigation, CROP_MOISTURE_PROFILES

router = APIRouter(prefix="/farmers/me", tags=["farmer_dashboard"])


def _latest_soil_moisture_reading(db: Session, field_id: str, include_simulated: bool = False):
    query = db.query(SensorReading).filter(
        SensorReading.field_id == field_id,
        (SensorReading.measurement_type == "soil_moisture") | SensorReading.soil_moisture.is_not(None),
    )
    if not include_simulated:
        query = query.filter(SensorReading.is_simulated.is_(False))
    return query.order_by(SensorReading.timestamp.desc()).first()


def _schedule_identity(schedule: IrrigationSchedule):
    recommended_date = schedule.recommended_date.isoformat() if schedule.recommended_date else None
    return (
        schedule.field_id,
        recommended_date,
        schedule.recommended_time,
        schedule.duration_minutes,
        schedule.water_quantity_liters,
        (schedule.reason or "").strip().casefold(),
    )


def _deduplicate_schedules(schedules: List[IrrigationSchedule]) -> List[IrrigationSchedule]:
    status_priority = {"completed": 3, "pending": 2, "skipped": 1, "cancelled": 1}
    unique = {}
    for schedule in schedules:
        identity = _schedule_identity(schedule)
        current = unique.get(identity)
        schedule_status = getattr(schedule.status, "value", schedule.status)
        current_status = getattr(current.status, "value", current.status) if current else None
        if current is None or status_priority.get(schedule_status, 0) > status_priority.get(current_status, 0):
            unique[identity] = schedule
    return list(unique.values())


def _resolve_farmer(db: Session, user_id: int) -> tuple[User, List[Farmer]]:
    user_record = db.query(User).filter(User.id == user_id).first()
    if not user_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_record, get_farmer_profiles_for_user(db, user_record)


@router.get("/dashboard", response_model=FarmerDashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    farmer_id: int = Depends(get_current_user),
):
    user_record, farmer_profiles = _resolve_farmer(db, farmer_id)
    farmer = farmer_profiles[0]
    farmer_ids = [profile.farmer_id for profile in farmer_profiles]

    # 1. Total fields
    farmer_fields = db.query(Field).filter(Field.farmer_id.in_(farmer_ids)).all()
    total_fields = len(farmer_fields)

    # 2. Fields needing irrigation
    fields_needing = 0
    field_conditions = []
    for field in farmer_fields:
        latest_reading = _latest_soil_moisture_reading(db, field.field_id)
        if latest_reading is None:
            latest_reading = _latest_soil_moisture_reading(db, field.field_id, include_simulated=True)
        reading_moisture = None
        if latest_reading is not None:
            reading_moisture = latest_reading.soil_moisture
            if reading_moisture is None and latest_reading.measurement_type == "soil_moisture":
                reading_moisture = latest_reading.value
        if reading_moisture is None:
            field_conditions.append(
                FieldCondition(
                    field_id=field.field_id,
                    action="NO_SENSOR_DATA",
                    urgency="NONE",
                    reason="No soil-moisture sensor reading is available for this field.",
                )
            )
            continue
        rec = recommend_irrigation(
            db=db,
            field_id=field.field_id,
            soil_moisture=reading_moisture,
        )
        if not latest_reading.is_simulated and rec.get("action") in {
            "IRRIGATE_IMMEDIATELY",
            "IRRIGATE_LIGHT",
        }:
            fields_needing += 1
        field_conditions.append(
            FieldCondition(
                field_id=field.field_id,
                action=rec["action"],
                urgency=rec["urgency"],
                reason=rec["reason"],
                soil_moisture=reading_moisture,
                sensor_timestamp=latest_reading.timestamp,
                is_simulated=latest_reading.is_simulated,
            )
        )

    # 3. Average soil moisture across recent sensor readings
    moisture_vals = []
    for field in farmer_fields:
        reading = _latest_soil_moisture_reading(db, field.field_id)
        if reading:
            moisture = reading.soil_moisture
            if moisture is None and reading.measurement_type == "soil_moisture":
                moisture = reading.value
            if moisture is not None:
                moisture_vals.append(moisture)
    avg_moisture = (sum(moisture_vals) / len(moisture_vals)) if moisture_vals else None

    # Completed schedule volumes are estimates; no flow-meter total is stored by this schema.
    all_schedules = (
        db.query(IrrigationSchedule)
        .join(Field, Field.field_id == IrrigationSchedule.field_id)
        .filter(Field.farmer_id.in_(farmer_ids))
        .all()
    )
    analytics_schedules = _deduplicate_schedules(all_schedules)
    completed_schedules = [s for s in analytics_schedules if s.status == "completed"]
    completed_schedule_volume = (
        sum(s.water_quantity_liters for s in completed_schedules) if completed_schedules else None
    )

    # Period totals use the schedule status-update time as the completion time.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    daily_records = [s for s in completed_schedules if (s.updated_at or s.recommended_date) >= today_start]
    weekly_records = [s for s in completed_schedules if (s.updated_at or s.recommended_date) >= seven_days_ago]
    monthly_records = [s for s in completed_schedules if (s.updated_at or s.recommended_date) >= thirty_days_ago]
    daily_liters = sum(s.water_quantity_liters for s in daily_records) if daily_records else None
    weekly_liters = sum(s.water_quantity_liters for s in weekly_records) if weekly_records else None
    monthly_liters = sum(s.water_quantity_liters for s in monthly_records) if monthly_records else None

    # Field breakdown
    field_breakdown = []
    for field in farmer_fields:
        completed_for_field = sum(
            s.water_quantity_liters
            for s in analytics_schedules
            if s.field_id == field.field_id and s.status == "completed"
        )
        planned_for_field = sum(
            s.water_quantity_liters
            for s in analytics_schedules
            if s.field_id == field.field_id and s.status == "pending"
        )
        field_breakdown.append(
            FieldWaterUsage(
                field_id=field.field_id,
                field_name=field.name,
                completed_schedule_volume_estimate_liters=round(completed_for_field, 1) if completed_for_field else None,
                planned_liters=round(planned_for_field, 1),
            )
        )

    # Water-saving comparison using a documented baseline:
    # Baseline: Traditional flood irrigation applies ~50mm depth per irrigation cycle.
    # 50 mm = 500,000 L / hectare.
    fields_by_id = {field.field_id: field for field in farmer_fields}
    baseline_available = bool(completed_schedules) and all(
        fields_by_id[s.field_id].area_hectares is not None
        and fields_by_id[s.field_id].area_hectares > 0
        for s in completed_schedules
    )
    traditional_flood_liters = (
        round(
            sum(fields_by_id[s.field_id].area_hectares * 500_000 for s in completed_schedules),
            1,
        )
        if baseline_available
        else None
    )
    water_saved_liters = (
        round(max(0.0, traditional_flood_liters - completed_schedule_volume), 1)
        if traditional_flood_liters is not None and completed_schedule_volume is not None
        else None
    )
    water_saved_pct = (
        round(water_saved_liters / traditional_flood_liters * 100.0, 1)
        if water_saved_liters is not None and traditional_flood_liters
        else None
    )

    water_analytics = WaterAnalytics(
        daily_schedule_volume_estimate_liters=round(daily_liters, 1) if daily_liters is not None else None,
        weekly_schedule_volume_estimate_liters=round(weekly_liters, 1) if weekly_liters is not None else None,
        monthly_schedule_volume_estimate_liters=round(monthly_liters, 1) if monthly_liters is not None else None,
        volume_basis="completed_schedule_estimates" if completed_schedule_volume is not None else "unavailable",
        efficiency_score=None,
        field_breakdown=field_breakdown,
        baseline_comparison=BaselineComparison(
            traditional_flood_liters=traditional_flood_liters,
            completed_schedule_volume_estimate_liters=(
                round(completed_schedule_volume, 1) if completed_schedule_volume is not None else None
            ),
            water_saved_liters=water_saved_liters,
            water_saved_percent=water_saved_pct,
            is_estimated=True,
            baseline_description="Estimated comparison of completed schedule volumes with a traditional flood-irrigation baseline of 50mm per cycle; no flow-meter measurements are available.",
        ),
    )

    # 6. Latest weather summary
    latest_weather = (
        db.query(WeatherData)
        .join(Field, Field.field_id == WeatherData.field_id)
        .filter(Field.farmer_id.in_(farmer_ids))
        .order_by(WeatherData.timestamp.desc())
        .first()
    )
    weather_summary = None
    if latest_weather:
        weather_summary = {
            "temperature": latest_weather.temperature,
            "humidity": latest_weather.humidity,
            "rainfall": latest_weather.rainfall,
            "wind_speed": latest_weather.wind_speed,
            "condition": latest_weather.condition,
            "source": latest_weather.source,
            "is_mock": latest_weather.is_mock,
            "timestamp": latest_weather.timestamp,
        }

    return FarmerDashboardResponse(
        farmer_name=farmer.name or user_record.full_name,
        farmer_email=farmer.email or user_record.email,
        total_fields=total_fields,
        fields_needing_irrigation=fields_needing,
        field_conditions=field_conditions,
        average_soil_moisture=round(avg_moisture, 1) if avg_moisture is not None else None,
        total_water_used_liters=None,
        completed_schedule_volume_estimate_liters=(
            round(completed_schedule_volume, 1) if completed_schedule_volume is not None else None
        ),
        weather_summary=weather_summary,
        water_analytics=water_analytics,
    )


@router.get("/alerts", response_model=List[AlertItem])
def get_alerts(
    db: Session = Depends(get_db),
    farmer_id: int = Depends(get_current_user),
):
    """Dynamically evaluate field sensor conditions, weather forecasts, and schedule reminders."""
    _, farmer_profiles = _resolve_farmer(db, farmer_id)
    farmer_ids = [profile.farmer_id for profile in farmer_profiles]
    farmer_fields = db.query(Field).filter(Field.farmer_id.in_(farmer_ids)).all()

    alerts: List[AlertItem] = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for field in farmer_fields:
        crop_name = (field.crop_type or "default").lower().strip()
        min_moisture, max_moisture = CROP_MOISTURE_PROFILES.get(crop_name, CROP_MOISTURE_PROFILES["default"])

        # Latest sensor reading
        latest_reading = _latest_soil_moisture_reading(db, field.field_id)

        if latest_reading and latest_reading.soil_moisture is not None:
            moisture = latest_reading.soil_moisture
            # 1. Critical Low Moisture Alert
            if moisture < (min_moisture - 5.0):
                alerts.append(
                    AlertItem(
                        id=f"alt_dry_{field.field_id}_{int(latest_reading.timestamp.timestamp())}",
                        type="low_moisture",
                        severity="critical",
                        title=f"Critical Soil Moisture Deficit – {field.name}",
                        message=f"Current soil moisture ({moisture:.1f}%) is below critical threshold ({min_moisture}%). Root zone water stress active.",
                        field_id=field.field_id,
                        field_name=field.name,
                        recommended_action=f"Execute scheduled irrigation immediately (~{round(min_moisture - moisture + 8)}mm) to protect crop yield.",
                        timestamp=latest_reading.timestamp,
                    )
                )
            # 2. Excess Moisture / Waterlogging Alert
            elif moisture > (max_moisture + 8.0):
                alerts.append(
                    AlertItem(
                        id=f"alt_wet_{field.field_id}_{int(latest_reading.timestamp.timestamp())}",
                        type="excess_moisture",
                        severity="warning",
                        title=f"Excess Soil Moisture / Drainage Alert – {field.name}",
                        message=f"Current soil moisture ({moisture:.1f}%) exceeds safety ceiling ({max_moisture}%). Risk of root hypoxia.",
                        field_id=field.field_id,
                        field_name=field.name,
                        recommended_action="Pause scheduled irrigation and inspect field drainage outlets.",
                        timestamp=latest_reading.timestamp,
                    )
                )

            # 3. Sensor Stale / Offline Alert (>24h old)
            age_hours = (now - latest_reading.timestamp).total_seconds() / 3600.0
            if age_hours > 24.0:
                alerts.append(
                    AlertItem(
                        id=f"alt_stale_{field.field_id}",
                        type="sensor_offline",
                        severity="warning",
                        title=f"Sensor Telemetry Stale – {field.name}",
                        message=f"Last telemetry was recorded {age_hours:.1f} hours ago. Sensor node may be offline or low on battery.",
                        field_id=field.field_id,
                        field_name=field.name,
                        recommended_action="Inspect physical IoT sensor battery, gateway connectivity, and signal RSSI.",
                        timestamp=latest_reading.timestamp,
                    )
                )
        else:
            # Field has no telemetry yet
            alerts.append(
                AlertItem(
                    id=f"alt_node_{field.field_id}",
                    type="sensor_offline",
                    severity="info",
                    title=f"Telemetry Awaiting Node Link – {field.name}",
                    message="Field is registered but no sensor telemetry has been ingested yet.",
                    field_id=field.field_id,
                    field_name=field.name,
                    recommended_action="Associate a LoRaWAN/Cellular soil moisture sensor in Sensors Management.",
                    timestamp=now,
                )
            )

        # 4. Weather / Rain Forecast Alert
        latest_weather = (
            db.query(WeatherData)
            .filter(WeatherData.field_id == field.field_id)
            .order_by(WeatherData.timestamp.desc())
            .first()
        )
        if latest_weather and latest_weather.rainfall and latest_weather.rainfall >= 10.0:
            alerts.append(
                AlertItem(
                    id=f"alt_rain_{field.field_id}",
                    type="heavy_rainfall",
                    severity="warning",
                    title=f"Heavy Rainfall Recorded – {field.name}",
                    message=f"Precipitation of {latest_weather.rainfall:.1f}mm recorded recently. Evapotranspiration demand is reduced.",
                    field_id=field.field_id,
                    field_name=field.name,
                    recommended_action="Defer upcoming irrigation runs by 24 to 48 hours to prevent over-saturation.",
                    timestamp=latest_weather.timestamp,
                )
            )

    # 5. Pending schedule reminders due today
    today_str = now.strftime("%Y-%m-%d")
    pending_today = (
        db.query(IrrigationSchedule)
        .join(Field, Field.field_id == IrrigationSchedule.field_id)
        .filter(Field.farmer_id.in_(farmer_ids))
        .filter(IrrigationSchedule.status == "pending")
        .all()
    )
    for sched in pending_today:
        sched_date_str = sched.recommended_date.strftime("%Y-%m-%d") if sched.recommended_date else ""
        if sched_date_str == today_str:
            target_field = db.get(Field, sched.field_id)
            alerts.append(
                AlertItem(
                    id=f"alt_sched_{sched.schedule_id}",
                    type="schedule_reminder",
                    severity="info",
                    title=f"Irrigation Run Scheduled Today – {target_field.name if target_field else sched.field_id}",
                    message=f"{sched.water_quantity_liters:.0f}L planned at {sched.recommended_time} hrs ({sched.duration_minutes:.0f} mins run).",
                    field_id=sched.field_id,
                    field_name=target_field.name if target_field else sched.field_id,
                    recommended_action="Verify pump availability and execute schedule from the Schedules panel.",
                    timestamp=sched.recommended_date or now,
                )
            )

    # Sort alerts by severity (critical first, then warning, then info)
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: (severity_order.get(a.severity, 3), -a.timestamp.timestamp()))
    return alerts
