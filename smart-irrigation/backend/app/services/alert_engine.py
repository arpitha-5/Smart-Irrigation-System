"""Emergency / warning alerts for a field. Pure Python: no database, HTTP or ML imports.

Alerts are deliberately RULE-BASED and independent of the ML model, so they still work when the model, the forecast or the
weather API is unavailable. They are advisory: nothing here switches water on.

Levels: EMERGENCY > WARNING > INFO > NONE.  Moisture thresholds come from the same crop profile the recommendation engine
already reports (``critical_threshold_pct`` = stress onset, ``optimal_target_pct``). Defaults are PROPOSALS for review.
(Delivery channels such as push / SMS / email are a later milestone; this module only decides WHAT to alert.)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

LEVELS = ("NONE", "INFO", "WARNING", "EMERGENCY")


@dataclass(frozen=True)
class AlertConfig:
    # Emergency = moisture below this fraction of the crop's critical (stress-onset) threshold. 0.70 is roughly "near the
    # permanent wilting point" for the soil/crop combinations in the training simulator (wilting point / stress onset 0.5-0.7).
    emergency_fraction_of_critical: float = 0.70
    # Flowering/fruiting is yield-critical, so the emergency trigger is reached earlier.
    emergency_fraction_sensitive_stage: float = 0.85
    sensitive_stages: Sequence[str] = ("flowering", "fruiting")
    forecast_rain_relief_mm: float = 10.0     # same value as the scheduler's forecast-deferral threshold
    stale_reading_hours: float = 24.0
    overwatering_margin_pct: float = 10.0     # soil this many points above the optimal target


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _alert(code: str, level: str, title: str, message: str, action: str) -> Dict[str, str]:
    return {"code": code, "level": level, "title": title, "message": message, "recommended_action": action}


def evaluate_alerts(*, soil_moisture: Any, reading_age_hours: Any, critical_threshold_pct: Any, optimal_target_pct: Any,
                    growth_stage: Optional[str] = None, forecast_rain_mm: Any = None, schedule_action: Optional[str] = None,
                    schedule_reason_codes: Sequence[str] = (), config: Optional[AlertConfig] = None,
                    now: Optional[datetime] = None) -> Dict[str, Any]:
    """Return {level, is_emergency, alerts[...], thresholds, generated_at_utc}. Never raises for bad input."""
    cfg = config or AlertConfig()
    moisture, age = _num(soil_moisture), _num(reading_age_hours)
    crit, target = _num(critical_threshold_pct), _num(optimal_target_pct)
    rain_fc = _num(forecast_rain_mm)
    stage = growth_stage.strip().lower() if isinstance(growth_stage, str) else None
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")
    alerts: List[Dict[str, str]] = []

    frac = cfg.emergency_fraction_sensitive_stage if stage in cfg.sensitive_stages else cfg.emergency_fraction_of_critical
    emergency_below = round(crit * frac, 1) if crit is not None else None
    stale = age is not None and age > cfg.stale_reading_hours
    rain_now = "rain_in_last_hour" in schedule_reason_codes
    rain_relief = rain_now or (rain_fc is not None and rain_fc >= cfg.forecast_rain_relief_mm)

    if moisture is None:
        alerts.append(_alert("NO_SENSOR_DATA", "WARNING", "No soil-moisture reading",
                             "No valid soil-moisture reading is available, so drought and over-watering cannot be assessed.",
                             "Check the sensor and its connection, or enter a manual reading."))
    else:
        if stale:
            alerts.append(_alert("SENSOR_STALE", "WARNING", "Sensor reading is old",
                                 f"The latest reading is {age:.0f} h old (limit {cfg.stale_reading_hours:g} h); the field may have changed since.",
                                 "Check the sensor. Treat the soil values below with caution."))
        if crit is not None and moisture < crit:
            severe = moisture < crit * frac
            if severe and not stale and not rain_relief:
                alerts.append(_alert("DROUGHT_EMERGENCY", "EMERGENCY", "Emergency: crop at risk of drought damage",
                                     f"Soil moisture {moisture:g}% is below the emergency level {emergency_below:g}% "
                                     f"(critical threshold {crit:g}%{', sensitive growth stage' if stage in cfg.sensitive_stages else ''}).",
                                     "Irrigate now if it is safe to do so and verify on site; the irrigation plan (when available) shows timing."))
            else:
                why = []
                if severe and rain_now:
                    why.append("rain was observed in the last hour")
                elif severe and rain_relief:
                    why.append(f"{rain_fc:g} mm of rain is forecast within 24 h")
                if severe and stale:
                    why.append("the reading is stale")
                note = (" Severe depletion, but " + " and ".join(why) + ", so this is not raised to an emergency. "
                        "Re-check soon; irrigate if the rain does not arrive.") if why else ""
                alerts.append(_alert("DROUGHT_RISK", "WARNING", "Soil is drier than the crop's critical level",
                                     f"Soil moisture {moisture:g}% is below the critical threshold {crit:g}%.{note}",
                                     "Plan irrigation soon."))
        if target is not None and moisture >= target + cfg.overwatering_margin_pct:
            alerts.append(_alert("OVERWATERING_RISK", "WARNING", "Soil may be over-watered",
                                 f"Soil moisture {moisture:g}% is {moisture - target:.0f} points above the optimal target {target:g}%.",
                                 "Do not irrigate; check drainage to avoid waterlogging and root damage."))

    if schedule_action == "WITHHELD":
        alerts.append(_alert("SCHEDULE_WITHHELD", "INFO", "Irrigation decision withheld",
                             "The weather-aware scheduler could not make a safe recommendation (weather unusable or invalid input).",
                             "Decide manually using soil moisture and local conditions."))
    elif schedule_action == "DEFER":
        alerts.append(_alert("IRRIGATION_DEFERRED", "INFO", "Irrigation deferred for rain",
                             "Rain observed or forecast, so watering is held back for now.", "Re-check after the stated re-evaluation time."))

    level = max((a["level"] for a in alerts), key=LEVELS.index, default="NONE")
    return {"level": level, "is_emergency": level == "EMERGENCY", "alerts": alerts, "generated_at_utc": stamp,
            "thresholds": {"critical_threshold_pct": crit, "emergency_below_pct": emergency_below,
                           "optimal_target_pct": target, "forecast_rain_relief_mm": cfg.forecast_rain_relief_mm,
                           "stale_reading_hours": cfg.stale_reading_hours},
            "disclaimer": "Advisory, rule-based alerts. Verify on site before acting; nothing here controls pumps or valves."}
