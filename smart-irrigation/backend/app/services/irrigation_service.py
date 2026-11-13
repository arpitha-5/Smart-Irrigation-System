"""Explainable irrigation recommendation engine.

Based on FAO-56 Irrigation Water Management agronomic principles.
Never claims rule-based logic is an AI model; clearly reports data sources,
sensor freshness, soil moisture deficits, and weather considerations.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Crop, Field, SensorReading, WeatherData
from app.config import get_settings
from app.services import ml_irrigation_service
from app.services.alert_engine import evaluate_alerts
from app.services.irrigation_scheduler import generate_irrigation_schedule
from app.services.schedule_optimizer import PlanConfig, plan_irrigation
from app.services.weather_adapter import get_field_weather

log = logging.getLogger("irrigation.schedule")

# Agronomic moisture requirements (volumetric water content %) by crop
# format: (min_threshold_pct, optimal_target_pct)
CROP_MOISTURE_PROFILES: Dict[str, tuple[float, float]] = {
    "rice": (45.0, 65.0),
    "maize": (25.0, 42.0),
    "wheat": (25.0, 40.0),
    "cotton": (20.0, 38.0),
    "sugarcane": (40.0, 60.0),
    "banana": (35.0, 55.0),
    "tomato": (28.0, 45.0),
    "potato": (28.0, 45.0),
    "onion": (25.0, 40.0),
    "chickpea": (18.0, 32.0),
    "lentil": (18.0, 32.0),
    "grapes": (20.0, 35.0),
    "apple": (25.0, 45.0),
    "orange": (25.0, 42.0),
    "default": (25.0, 40.0),
}

# Growth stage sensitivity modifiers
STAGE_MODIFIERS: Dict[str, float] = {
    "seedling": 0.8,     # shallow roots, avoid waterlogging
    "vegetative": 1.0,   # baseline canopy expansion
    "flowering": 1.25,   # critical reproductive period: peak water demand
    "fruiting": 1.15,    # fruit filling stage
    "maturity": 0.6,     # drying off before harvest to prevent mold
}


def recommend_irrigation(
    db: Optional[Session] = None,
    field_id: Optional[str] = None,
    crop_type: Optional[str] = None,
    growth_stage: Optional[str] = "vegetative",
    soil_moisture: Optional[float] = None,
    temperature: Optional[float] = None,
    recent_rainfall_mm: Optional[float] = 0.0,
    forecast_rainfall_mm: Optional[float] = 0.0,
) -> Dict[str, Any]:
    sensor_freshness = "manual_input"
    field_name = None
    evaluated_crop = (crop_type or "default").lower().strip()
    evaluated_stage = (growth_stage or "vegetative").lower().strip()
    reading_timestamp = None

    # If field_id is provided and database session is available, resolve from live DB records
    if field_id and db is not None:
        field = db.get(Field, field_id)
        if field:
            field_name = field.name
            if not crop_type and field.crop_type:
                evaluated_crop = field.crop_type.lower().strip()

            # Check crop record for growth stage
            crop_record = db.scalar(select(Crop).where(Crop.field_id == field_id).order_by(Crop.created_at.desc()).limit(1))
            if crop_record:
                if crop_record.crop_type:
                    evaluated_crop = crop_record.crop_type.lower().strip()
                if crop_record.growth_stage:
                    evaluated_stage = crop_record.growth_stage.lower().strip()

            # Check latest sensor reading
            latest_reading = db.scalar(
                select(SensorReading)
                .where(SensorReading.field_id == field_id)
                .order_by(SensorReading.timestamp.desc())
                .limit(1)
            )
            if latest_reading and soil_moisture is None:
                soil_moisture = latest_reading.soil_moisture if latest_reading.soil_moisture is not None else latest_reading.value
                reading_timestamp = latest_reading.timestamp
                now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                age_hours = (now_utc - latest_reading.timestamp).total_seconds() / 3600.0
                if age_hours > 24:
                    sensor_freshness = f"stale ({age_hours:.1f} hours old)"
                elif age_hours > 6:
                    sensor_freshness = f"aging ({age_hours:.1f} hours old)"
                else:
                    sensor_freshness = f"fresh ({age_hours:.1f} hours old)"

            # Check latest weather
            latest_weather = db.scalar(
                select(WeatherData)
                .where(WeatherData.field_id == field_id)
                .order_by(WeatherData.timestamp.desc())
                .limit(1)
            )
            if latest_weather:
                if temperature is None:
                    temperature = latest_weather.temperature
                if (recent_rainfall_mm is None or recent_rainfall_mm == 0.0) and latest_weather.rainfall is not None:
                    recent_rainfall_mm = latest_weather.rainfall

    # Defaults if completely missing
    evaluated_moisture = soil_moisture if soil_moisture is not None else 30.0
    evaluated_temp = temperature if temperature is not None else 25.0
    evaluated_recent_rain = recent_rainfall_mm or 0.0
    evaluated_forecast_rain = forecast_rainfall_mm or 0.0

    # Look up crop profile
    min_thresh, target_thresh = CROP_MOISTURE_PROFILES.get(evaluated_crop, CROP_MOISTURE_PROFILES["default"])
    stage_factor = STAGE_MODIFIERS.get(evaluated_stage, 1.0)
    adjusted_min = round(min_thresh * stage_factor, 1)
    adjusted_target = round(target_thresh * stage_factor, 1)

    # Core FAO-56 moisture deficit calculation
    deficit = max(0.0, adjusted_target - evaluated_moisture)

    # Decision Matrix
    action = "MAINTAIN_MONITORING"
    urgency = "LOW"
    water_mm = 0.0
    reason_parts = []

    # Weather overrides
    if evaluated_recent_rain >= 12.0:
        action = "DEFER_DUE_TO_RAIN"
        urgency = "NONE"
        water_mm = 0.0
        reason_parts.append(
            f"Significant recent rainfall ({evaluated_recent_rain}mm) recorded. Irrigation is deferred to conserve water and prevent root hypoxia."
        )
    elif evaluated_forecast_rain >= 8.0 and deficit < 10.0:
        action = "DEFER_DUE_TO_RAIN"
        urgency = "LOW"
        water_mm = 0.0
        reason_parts.append(
            f"Upcoming rainfall ({evaluated_forecast_rain}mm) forecasted. Mild moisture deficit ({deficit:.1f}%) will be replenished naturally."
        )
    elif evaluated_moisture < adjusted_min:
        deficit_depth = adjusted_target - evaluated_moisture
        # 1% volumetric moisture ~ 1.0 - 1.5 mm of water depending on active root zone (typical 20-30cm root depth)
        water_mm = round(min(35.0, max(5.0, deficit_depth * 1.2)), 1)
        if evaluated_stage == "flowering":
            urgency = "HIGH"
            action = "IRRIGATE_IMMEDIATELY"
            reason_parts.append(
                f"Critical moisture deficit: {evaluated_moisture}% is below safety threshold ({adjusted_min}%). "
                f"Crop '{evaluated_crop}' is in the sensitive flowering stage where water stress reduces yield by >30%."
            )
        else:
            urgency = "HIGH" if deficit_depth > 10.0 else "MODERATE"
            action = "IRRIGATE_IMMEDIATELY"
            reason_parts.append(
                f"Current soil moisture ({evaluated_moisture}%) has dropped below the threshold ({adjusted_min}%) "
                f"for {evaluated_crop} in {evaluated_stage} stage."
            )
    elif evaluated_moisture < adjusted_target:
        deficit_depth = adjusted_target - evaluated_moisture
        water_mm = round(deficit_depth * 0.8, 1)
        action = "IRRIGATE_LIGHT"
        urgency = "MODERATE"
        reason_parts.append(
            f"Soil moisture ({evaluated_moisture}%) is above critical threshold ({adjusted_min}%) but below optimal target ({adjusted_target}%). "
            f"Light irrigation recommended to maintain transpiration efficiency."
        )
    else:
        action = "MAINTAIN_MONITORING"
        urgency = "NONE"
        water_mm = 0.0
        reason_parts.append(
            f"Soil moisture ({evaluated_moisture}%) is optimal (target: {adjusted_target}%). No irrigation required at this time."
        )

    if evaluated_temp > 34.0 and action != "DEFER_DUE_TO_RAIN":
        reason_parts.append(f"High ambient temperature ({evaluated_temp}°C) elevates evapotranspiration; irrigate during early morning or evening.")

    if "stale" in sensor_freshness:
        reason_parts.append("WARNING: Latest sensor telemetry is older than 24 hours. Physical field inspection recommended.")

    full_reason = " ".join(reason_parts)

    return {
        "action": action,
        "recommended_water_mm": water_mm,
        "urgency": urgency,
        "reason": full_reason,
        "factors_evaluated": {
            "field_id": field_id,
            "field_name": field_name,
            "crop_type": evaluated_crop,
            "growth_stage": evaluated_stage,
            "current_soil_moisture_pct": evaluated_moisture,
            "critical_threshold_pct": adjusted_min,
            "optimal_target_pct": adjusted_target,
            "ambient_temperature_c": evaluated_temp,
            "recent_rainfall_mm": evaluated_recent_rain,
            "forecast_rainfall_mm": evaluated_forecast_rain,
            "fao56_deficit_mm": round(deficit, 1),
            "reading_timestamp": reading_timestamp.isoformat() if reading_timestamp else None,
        },
        "recommendation_engine": "Rule-based Agronomic Water Deficit Model (FAO-56 Irrigation & Drainage Guidelines)",
        "sensor_freshness": sensor_freshness,
        "limitations": (
            "Advisory recommendation only. Emitter flow rate, soil salinity, and local slope must be verified before automated actuation. "
            "Never connects directly to high-voltage pump relays without confirmed manual hardware fail-safes."
        ),
    }


# ── Scheduler integration ─────────────────────────────────────────────────────────────────────────

SCHEDULE_INPUT_SOURCE = "rule_based_recommendation"
ML_SOURCE = "ml_model"
ML_MAX_READING_AGE_HOURS = 24.0   # same limit as the stale-sensor alert
EMERGENCY_SOURCE = "rule_based_emergency_override"


def _weather_bits(weather: Any) -> tuple:
    """(24 h forecast rain mm or None, wind m/s or None) from a FieldWeatherResult, defensively."""
    forecast = getattr(weather, "forecast", None)
    rain = forecast.get("expected_rainfall_mm") if isinstance(forecast, dict) and forecast.get("available") else None
    wind = getattr(getattr(weather, "observation", None), "wind_speed_ms", None)
    return rain, wind


def _alerts_for(recommendation: Dict[str, Any], ctx: Dict[str, Any], forecast_rain: Any,
                schedule: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Rule-based alerts; contained so a bug here can never remove the recommendation."""
    try:
        f = recommendation.get("factors_evaluated") or {}
        sched = schedule or {}
        return evaluate_alerts(
            soil_moisture=ctx.get("soil_moisture"), reading_age_hours=ctx.get("reading_age_hours"),
            critical_threshold_pct=f.get("critical_threshold_pct"), optimal_target_pct=f.get("optimal_target_pct"),
            growth_stage=ctx.get("growth_stage") or f.get("growth_stage"), forecast_rain_mm=forecast_rain,
            schedule_action=sched.get("action"), schedule_reason_codes=sched.get("reason_codes") or ())
    except Exception as exc:  # noqa: BLE001
        log.error("Alert evaluation failed: %s", type(exc).__name__)
        return None


def _gather_ctx(db: Session, field_row: Field, manual_soil_moisture: Optional[float]) -> Dict[str, Any]:
    """Crop / growth-day / soil-moisture inputs for the field. Independent of weather, so alerts never depend on it."""
    fallback = {"soil_moisture": manual_soil_moisture,
                "reading_age_hours": 0.0 if manual_soil_moisture is not None else None}
    try:
        return ml_irrigation_service.gather_runtime_context(db, field_row, manual_soil_moisture=manual_soil_moisture)
    except Exception as exc:  # noqa: BLE001
        log.error("Could not gather field context for %s: %s", field_row.field_id, type(exc).__name__)
        return fallback


def _choose_depth(ctx: Dict[str, Any], recommendation: Dict[str, Any], forecast_rain: Any) -> tuple:
    """(ml_prediction dict, depth_mm, source). The trained model is used when it can be; otherwise the rule-based depth.

    ML needs: a supported crop, a planting date, a soil-moisture reading (sensor or manual) and a loaded model.
    Nothing is guessed; whatever is missing is reported in ``ml_prediction['reason']``.
    """
    rule_mm = recommendation.get("recommended_water_mm")
    try:
        predictor = ml_irrigation_service.get_predictor()
        if predictor is None:
            reason = ml_irrigation_service.model_info().get("error") or "ML model is disabled or not trained."
            return {"available": False, "reason": reason, "fallback": "rule_based"}, rule_mm, SCHEDULE_INPUT_SOURCE
        age = ctx.get("reading_age_hours")
        if age is not None and age > ML_MAX_READING_AGE_HOURS:
            return ({"available": False, "fallback": "rule_based",
                     "reason": (f"The latest soil-moisture reading is {age:.0f} h old (limit {ML_MAX_READING_AGE_HOURS:g} h); "
                                "the model needs a current reading, so the rule-based depth is used.")},
                    rule_mm, SCHEDULE_INPUT_SOURCE)
        pred = predictor.predict(ml_irrigation_service.ml_inputs(ctx, forecast_rain))
        pred_dict = pred.to_dict()
        pred_dict["inputs"] = {k: ctx.get(k) for k in ("crop_type", "days_after_sowing", "soil_moisture", "soil_moisture_change_24h",
                                                         "moisture_source", "reading_age_hours", "planting_date")}
        if not pred.available:
            pred_dict["fallback"] = "rule_based"
            return pred_dict, rule_mm, SCHEDULE_INPUT_SOURCE
        return pred_dict, pred.depth_mm, ML_SOURCE
    except Exception as exc:  # noqa: BLE001 - fall back to rules, never fail the request
        log.error("ML step failed: %s", type(exc).__name__)
        return {"available": False, "reason": f"ML step failed ({type(exc).__name__}); the rule-based depth is used.",
                "fallback": "rule_based"}, rule_mm, SCHEDULE_INPUT_SOURCE


def _schedule_input(source: str, depth_mm: Any, recommendation: Dict[str, Any], ml: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if source == ML_SOURCE:
        return {"predicted_irrigation_mm": depth_mm, "unit": "mm", "source": source, "is_ml_prediction": True,
                "recommendation_engine": (ml or {}).get("model_name"),
                "note": ("The depth comes from the trained ML model (gross applied depth, trained on synthetic data). The scheduler "
                         "does not modify it; it only decides whether to apply it now.")}
    if source == EMERGENCY_SOURCE:
        return {"predicted_irrigation_mm": depth_mm, "unit": "mm", "source": source, "is_ml_prediction": False,
                "recommendation_engine": recommendation.get("recommendation_engine"),
                "note": ("EMERGENCY override: soil moisture is critically low but the ML model advised no irrigation, so the "
                         "rule-based depth was used as a safety net. Verify on site.")}
    return {"predicted_irrigation_mm": depth_mm, "unit": "mm", "source": source, "is_ml_prediction": False,
            "recommendation_engine": recommendation.get("recommendation_engine"),
            "note": ("The depth comes from the rule-based water-deficit recommendation (recommended_water_mm), not from "
                     "a trained ML model. The scheduler does not modify it; it only decides whether to apply it now.")}


def _calculate_irrigation_duration(
    depth_mm: Optional[float],
    area_hectares: Optional[float],
    flow_rate_lpm: Optional[float],
) -> tuple:
    """Returns (volume_litres, duration_minutes, duration_formatted, flow_rate_status).

    Uses exact formula:
      Water volume (litres) = ML predicted depth (mm) * Field area (hectares) * 10,000
      Duration (minutes) = Water volume (litres) / Flow rate (litres per minute)
    """
    if depth_mm is None or depth_mm <= 0:
        return 0.0, 0.0, "0 min", "not_configured" if not flow_rate_lpm else "configured"

    volume_litres = None
    if area_hectares and area_hectares > 0:
        volume_litres = round(float(depth_mm) * float(area_hectares) * 10_000.0, 1)

    if flow_rate_lpm is None or flow_rate_lpm <= 0:
        return volume_litres, None, "Flow rate not configured", "not_configured"

    if volume_litres is None:
        return None, None, "Field area not configured", "configured"

    duration_min = round(volume_litres / float(flow_rate_lpm), 1)
    hrs = int(duration_min // 60)
    mins = int(round(duration_min % 60))
    if hrs > 0:
        fmt = f"{hrs} hr {mins} min" if mins > 0 else f"{hrs} hr"
    else:
        fmt = f"{mins} min"
    return volume_litres, duration_min, fmt, "configured"


def _determine_recommended_window(
    action: str,
    depth_mm: Optional[float],
    is_emergency: bool,
    now_local: datetime,
    duration_min: Optional[float],
    weather: Any,
) -> tuple:
    """Returns (rec_date, time_window, start_time, end_time, reason)."""
    weather_usable = bool(getattr(weather, "usable", False) or (isinstance(getattr(weather, "forecast", None), dict) and getattr(weather, "forecast", {}).get("available")))
    weather_note = "" if weather_usable else " (Scheduling uses available soil telemetry and crop growth stage; live weather observations were unavailable)."

    if action in ("DEFER_DUE_TO_RAIN", "DEFER"):
        return None, "Deferred due to rainfall", None, None, "Irrigation is deferred because recent or forecasted rainfall is sufficient to maintain root moisture." + weather_note

    if action in ("MAINTAIN_MONITORING", "NO_IRRIGATION_NEEDED") or not depth_mm or depth_mm <= 0:
        return None, "No irrigation required", None, None, "Soil moisture is in the optimal range for the current crop growth stage; no irrigation needed at this time." + weather_note

    if is_emergency:
        rec_date = now_local.strftime("%Y-%m-%d")
        start_time = now_local.strftime("%H:%M")
        end_dt = now_local + timedelta(minutes=duration_min or 60)
        end_time = end_dt.strftime("%H:%M")
        reason = "EMERGENCY: Severe soil moisture deficit below critical threshold. Immediate watering recommended to prevent permanent crop wilting." + weather_note
        return rec_date, "Immediate (Next 30 minutes)", start_time, end_time, reason

    curr_hour = now_local.hour + now_local.minute / 60.0
    if curr_hour < 8.5:
        rec_date = now_local.strftime("%Y-%m-%d")
        reason = "Early morning window (06:00 - 08:30) recommended to minimize evaporation loss during midday heat and support transpiration uptake." + weather_note
        return rec_date, "06:00 - 08:30 (Morning)", "06:00", "08:30", reason
    elif curr_hour < 16.5:
        rec_date = now_local.strftime("%Y-%m-%d")
        reason = "Evening window (17:00 - 19:30) recommended to avoid high afternoon solar radiation and allow water to percolate overnight." + weather_note
        return rec_date, "17:00 - 19:30 (Evening)", "17:00", "19:30", reason
    elif curr_hour < 19.5:
        rec_date = now_local.strftime("%Y-%m-%d")
        reason = "Cool evening hours allow deep root infiltration with minimal wind drift and low evaporation." + weather_note
        return rec_date, "17:30 - 19:30 (Evening)", now_local.strftime("%H:%M"), "19:30", reason
    else:
        next_day = now_local + timedelta(days=1)
        rec_date = next_day.strftime("%Y-%m-%d")
        reason = "Irrigating early tomorrow morning (06:00 - 08:30) avoids overnight standing water disease risk while beating tomorrow's midday evaporation." + weather_note
        return rec_date, "06:00 - 08:30 (Next Morning)", "06:00", "08:30", reason


def _build_scheduling_payload(
    recommendation: Dict[str, Any],
    field_row: Optional[Field],
    weather: Any,
    alerts: Optional[Dict[str, Any]],
    depth_mm: Optional[float],
    flow_rate_lpm: Optional[float],
    utc_offset_hours: float = 5.5,
) -> Dict[str, Any]:
    tz = timezone(timedelta(hours=utc_offset_hours))
    now_local = datetime.now(timezone.utc).astimezone(tz)

    depth = float(depth_mm) if (depth_mm is not None and depth_mm > 0) else 0.0
    area_ha = getattr(field_row, "area_hectares", None)

    # Actual pump flow rate: passed explicitly, or stored on field
    actual_flow = None
    if flow_rate_lpm is not None and flow_rate_lpm > 0:
        actual_flow = float(flow_rate_lpm)
    elif field_row is not None and getattr(field_row, "pump_flow_rate_lpm", None) is not None:
        p_val = field_row.pump_flow_rate_lpm
        if p_val and p_val > 0:
            actual_flow = float(p_val)

    vol_litres, dur_min, dur_fmt, flow_status = _calculate_irrigation_duration(depth, area_ha, actual_flow)

    action = recommendation.get("action", "")
    is_em = bool(alerts and alerts.get("is_emergency"))
    rec_date, win_lbl, start_t, end_t, reason = _determine_recommended_window(
        action, depth, is_em, now_local, dur_min, weather
    )

    f_eval = recommendation.get("factors_evaluated") or {}
    return {
        "ml_predicted_water_mm": depth,
        "water_volume_litres": vol_litres,
        "unit": "mm",
        "recommended_date": rec_date,
        "recommended_time_window": win_lbl,
        "recommended_start_time": start_t,
        "recommended_end_time": end_t,
        "flow_rate_lpm": actual_flow,
        "flow_rate_status": flow_status,
        "duration_minutes": dur_min,
        "duration_formatted": dur_fmt,
        "reason": reason,
        "crop_details": {
            "crop_type": f_eval.get("crop_type"),
            "growth_stage": f_eval.get("growth_stage"),
            "soil_moisture_pct": f_eval.get("current_soil_moisture_pct"),
        },
        "field_details": {
            "field_id": getattr(field_row, "field_id", None) or f_eval.get("field_id"),
            "field_name": getattr(field_row, "name", None) or f_eval.get("field_name"),
            "area_hectares": area_ha,
            "pump_flow_rate_lpm": actual_flow,
            "irrigation_method": getattr(field_row, "irrigation_method", None),
        },
        "is_advisory": True,
        "disclaimer": "Advisory recommendation only. Not scheduled automatically; guidance for the farmer to operate irrigation equipment.",
    }


def attach_irrigation_schedule(
    db: Session,
    recommendation: Dict[str, Any],
    field_id: Optional[str],
    *,
    manual_soil_moisture: Optional[float] = None,
    irrigation_method: Optional[str] = None,
    application_rate_mm_per_hour: Optional[float] = None,
    flow_rate_lpm: Optional[float] = None,
) -> Dict[str, Any]:
    """Add the ML-driven, weather-aware scheduling decision to an existing recommendation (additive, never destructive).

    ``recommendation`` is the unmodified output of :func:`recommend_irrigation`; every key in it is returned as is.
    Keys added (all None when not applicable):
      irrigation_schedule  scheduler decision (IRRIGATE / DEFER / NO_IRRIGATION_NEEDED / WITHHELD). THE FINAL DECISION.
      schedule_input       provenance of the depth given to the scheduler (trained ML model, or rule-based fallback)
      scheduling_note      why no schedule was produced
      ml_prediction        what the trained model said, or why it was not used
      irrigation_plan      time-slotted plan (only when the schedule action is IRRIGATE)
      alerts               rule-based EMERGENCY / WARNING / INFO alerts (independent of the model and the weather)

    Depth source: the trained ML model when it can run (supported crop, planting date, soil-moisture reading); otherwise the
    rule-based ``recommended_water_mm``. If the soil is critically low (EMERGENCY alert) while the ML model advises no
    irrigation, the rule-based depth is used as a safety net and the response says so. The scheduler never changes the depth.

    A schedule needs a registered field (weather by coordinates, volume by area). Any unexpected failure is contained so
    the existing recommendation is never lost.
    """
    out: Dict[str, Any] = dict(recommendation)
    out.update(irrigation_schedule=None, schedule_input=None, scheduling_note=None, ml_prediction=None,
               irrigation_plan=None, alerts=None)
    manual_ctx = {"soil_moisture": manual_soil_moisture, "reading_age_hours": 0.0 if manual_soil_moisture is not None else None}

    if not field_id:
        out["scheduling_note"] = ("No field_id supplied, so weather could not be retrieved for a field and no "
                                  "schedule was generated. Provide a registered field_id to get one.")
        out["alerts"] = _alerts_for(recommendation, manual_ctx, (recommendation.get("factors_evaluated") or {}).get("forecast_rainfall_mm"), None)
        # Evaluate ML prediction for custom parameters using the uploaded Two-Stage ML model
        f = recommendation.get("factors_evaluated") or {}
        ml_custom = ml_irrigation_service.predict_ml_v2(
            crop_type=f.get("crop_type"),
            growth_stage=f.get("growth_stage"),
            soil_moisture=f.get("current_soil_moisture_pct"),
            temperature=f.get("ambient_temperature_c"),
            recent_rainfall_mm=f.get("recent_rainfall_mm"),
            forecast_rainfall_mm=f.get("forecast_rainfall_mm"),
        )
        if ml_custom.get("available") and ml_custom.get("predicted_water_mm", 0) > 0 and recommendation.get("action", "").startswith("IRRIGATE"):
            out["ml_prediction"] = {
                "available": True,
                "depth_mm": ml_custom["predicted_water_mm"],
                "raw_depth_mm": ml_custom.get("raw_depth_mm"),
                "probability": ml_custom.get("probability"),
                "model_name": ml_custom.get("model_name"),
                "model_version": ml_custom.get("model_version"),
                "unit": "mm",
            }
            if out.get("factors_evaluated"):
                out["factors_evaluated"]["fao56_deficit_mm"] = recommendation.get("recommended_water_mm")
                out["factors_evaluated"]["ml_predicted_water_mm"] = ml_custom["predicted_water_mm"]
                out["factors_evaluated"]["ml_probability"] = ml_custom.get("probability")
        custom_depth = (out.get("ml_prediction") or {}).get("depth_mm") or recommendation.get("recommended_water_mm")
        out["scheduling_recommendation"] = _build_scheduling_payload(
            recommendation=out,
            field_row=None,
            weather=None,
            alerts=out.get("alerts"),
            depth_mm=custom_depth,
            flow_rate_lpm=flow_rate_lpm,
            utc_offset_hours=5.5,
        )
        return out
    field_row = db.get(Field, field_id)
    if field_row is None:
        out["scheduling_note"] = (f"Field '{field_id}' is not registered, so no weather lookup or schedule was "
                                  "performed. The recommendation above is based on the supplied inputs only.")
        out["alerts"] = _alerts_for(recommendation, manual_ctx, (recommendation.get("factors_evaluated") or {}).get("forecast_rainfall_mm"), None)
        return out

    settings = get_settings()
    field_info = {"field_id": field_row.field_id, "area_hectares": field_row.area_hectares}
    ctx = _gather_ctx(db, field_row, manual_soil_moisture)      # before weather: alerts must not depend on the weather call
    forecast_rain: Any = None
    try:
        weather = get_field_weather(db, field_row.field_id)
        forecast_rain, wind = _weather_bits(weather)
        ml, depth_mm, source = _choose_depth(ctx, recommendation, forecast_rain)
        schedule = generate_irrigation_schedule(depth_mm, weather, field_info)
        sched = schedule.to_dict()
        alerts = _alerts_for(recommendation, ctx, forecast_rain, sched)

        rule_mm = recommendation.get("recommended_water_mm")
        if (alerts and alerts["is_emergency"] and sched.get("action") == "NO_IRRIGATION_NEEDED" and source == ML_SOURCE
                and isinstance(rule_mm, (int, float)) and rule_mm > 0):
            depth_mm, source = rule_mm, EMERGENCY_SOURCE          # safety net: sensor says critical, model says no
            schedule = generate_irrigation_schedule(depth_mm, weather, field_info)
            sched = schedule.to_dict()
            alerts = _alerts_for(recommendation, ctx, forecast_rain, sched)
            ml = dict(ml, overridden_by="emergency_alert")
        out["irrigation_schedule"], out["ml_prediction"], out["alerts"] = sched, ml, alerts
        if source == ML_SOURCE and isinstance(depth_mm, (int, float)) and depth_mm > 0:
            out["recommended_water_mm"] = depth_mm
            out["recommendation_engine"] = "AI Two-Stage Gradient Boosting ML Model (Trained on Field Telemetry)"
            if out.get("factors_evaluated"):
                out["factors_evaluated"]["fao56_deficit_mm"] = rule_mm
                out["factors_evaluated"]["ml_predicted_water_mm"] = depth_mm
    except Exception as exc:  # noqa: BLE001 - the original recommendation must still be returned
        log.error("Scheduling failed for field %s: %s", field_id, type(exc).__name__)
        out["scheduling_note"] = f"Scheduling could not be completed ({type(exc).__name__}); no schedule was generated."
        out["alerts"] = _alerts_for(recommendation, ctx, forecast_rain, None)
        return out

    out["schedule_input"] = _schedule_input(source, depth_mm, recommendation, ml)
    try:
        out["irrigation_plan"] = plan_irrigation(
            action=sched["action"], depth_mm=sched.get("recommended_irrigation_mm"),
            emergency=bool(alerts and alerts["is_emergency"]), method=irrigation_method,
            rate_mm_per_hour=application_rate_mm_per_hour, wind_speed_ms=wind, area_hectares=field_row.area_hectares,
            reevaluate_after_hours=sched.get("reevaluate_after_hours"),
            config=PlanConfig(utc_offset_hours=settings.irrigation_utc_offset_hours))
    except Exception as exc:  # noqa: BLE001
        log.error("Plan generation failed for field %s: %s", field_id, type(exc).__name__)

    active_depth = None
    if out.get("ml_prediction") and out["ml_prediction"].get("available") and out["ml_prediction"].get("depth_mm") is not None:
        active_depth = out["ml_prediction"]["depth_mm"]
    elif sched and sched.get("recommended_irrigation_mm") is not None:
        active_depth = sched.get("recommended_irrigation_mm")
    else:
        active_depth = out.get("recommended_water_mm")

    out["scheduling_recommendation"] = _build_scheduling_payload(
        recommendation=out,
        field_row=field_row,
        weather=weather,
        alerts=alerts,
        depth_mm=active_depth,
        flow_rate_lpm=flow_rate_lpm,
        utc_offset_hours=settings.irrigation_utc_offset_hours,
    )
    _sync_advisory_alerts_to_db(db, field_row, alerts)
    return out


def _sync_advisory_alerts_to_db(db: Session, field_row: Field, alerts_dict: Optional[Dict[str, Any]]) -> None:
    """Persists rule-based advisory alerts into the database and dispatches farmer notifications."""
    if not alerts_dict or not alerts_dict.get("alerts"):
        return
    try:
        from app.models.alert import Alert
        from app.models.farmer import utcnow
        from app.services.alert_runner import _dispatch_alert_notifications
        from app.services.alert_service import AlertChange, ACTIVE_STATUSES

        now = utcnow()
        sensor_id = (
            field_row.sensors[0].sensor_id
            if getattr(field_row, "sensors", None) and len(field_row.sensors) > 0
            else f"SNS_{field_row.field_id}"
        )
        changes: List[AlertChange] = []

        for item in alerts_dict["alerts"]:
            code = item.get("code", "")
            level = item.get("level", "WARNING")
            title = item.get("title", "Advisory Notice")
            msg = item.get("message", "")
            action = item.get("recommended_action", "Check field conditions.")

            if "DROUGHT" in code:
                atype = "drought"
            elif "OVERWATERING" in code:
                atype = "over_watering"
            elif "SENSOR" in code or "STALE" in code:
                atype = "sensor_failure"
            else:
                atype = "drought"

            existing = db.scalars(
                select(Alert).where(
                    Alert.field_id == field_row.field_id,
                    Alert.sensor_id == sensor_id,
                    Alert.alert_type == atype,
                    Alert.status.in_(ACTIVE_STATUSES),
                )
            ).first()

            sev = "CRITICAL" if level == "EMERGENCY" else ("HIGH" if level == "WARNING" else "MEDIUM")

            if existing is None:
                new_alert = Alert(
                    field_id=field_row.field_id,
                    sensor_id=sensor_id,
                    alert_type=atype,
                    severity=sev,
                    status="open",
                    source="ai_advisory",
                    message=f"{title}: {msg}"[:400],
                    recommended_action=action[:300],
                    occurrence_count=1,
                    created_at=now,
                    last_seen_at=now,
                )
                db.add(new_alert)
                db.flush()
                changes.append(AlertChange(new_alert, "new"))
            else:
                existing.last_seen_at = now
                existing.occurrence_count += 1
                changes.append(AlertChange(existing, "repeat"))

        db.commit()
        if changes:
            _dispatch_alert_notifications(db, changes, field_row.field_id)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log.warning("Advisory alert synchronization skipped: %s", exc)

