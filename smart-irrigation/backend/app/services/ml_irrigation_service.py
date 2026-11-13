"""Glue between the trained irrigation model and the live system (database rows, weather, settings).

The model and its feature rules live in ``app/ml`` and are pure; this module only:
  * loads / caches the model (``get_predictor``) and reports its status (``model_info``),
  * collects the model's inputs for a registered field from the database (``gather_runtime_context``).
Nothing here invents data: a missing planting date, crop, or soil-moisture reading means "ML unavailable", and the caller
falls back to the rule-based engine and says why.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.ml.predictor import IrrigationPredictor
from app.ml.training import ModelLoadError
from app.models import Crop, Field, SensorReading
from app.services import agro_params

log = logging.getLogger("irrigation.ml.service")

BACKEND_DIR = Path(__file__).resolve().parents[2]
_STATE: Dict[str, Any] = {"loaded": False, "predictor": None, "error": None}


# ── model loading ─────────────────────────────────────────────────────────────────────────────────

def models_dir(settings: Optional[Settings] = None) -> Path:
    s = settings or get_settings()
    return Path(s.irrigation_models_dir) if s.irrigation_models_dir else BACKEND_DIR / "models"


def reset_predictor_cache() -> None:
    _STATE.update(loaded=False, predictor=None, error=None)


def get_predictor(settings: Optional[Settings] = None) -> Optional[IrrigationPredictor]:
    """The cached predictor, or None if ML is disabled or no usable model exists (reason in ``model_info``)."""
    s = settings or get_settings()
    if not s.irrigation_ml_enabled:
        return None
    if not _STATE["loaded"]:
        try:
            _STATE["predictor"] = IrrigationPredictor.load(models_dir(s))
            _STATE["error"] = None
        except ModelLoadError as exc:
            _STATE["predictor"], _STATE["error"] = None, str(exc)
            log.warning("Irrigation ML model unavailable: %s", exc)
        except Exception as exc:  # noqa: BLE001 - serving must never crash because the model file is odd
            _STATE["predictor"], _STATE["error"] = None, f"Unexpected error loading the model ({type(exc).__name__})."
            log.error("Irrigation ML model failed to load: %s", type(exc).__name__)
        _STATE["loaded"] = True
    return _STATE["predictor"]


def model_info(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Status + evaluation summary for the model-serving endpoint. Never raises."""
    s = settings or get_settings()
    predictor = get_predictor(s)
    base: Dict[str, Any] = {"enabled": s.irrigation_ml_enabled, "loaded": predictor is not None,
                            "supported_crops": list(agro_params.SUPPORTED_CROPS), "error": _STATE["error"]}
    if predictor is None:
        base["fallback"] = "The rule-based irrigation engine is used." if s.irrigation_ml_enabled else \
            "ML is disabled (IRRIGATION_ML_ENABLED=false); the rule-based engine is used."
        return base
    m = predictor.metadata
    base.update(version=predictor.version, model_name=m.get("model_name"), kind=m.get("kind"), threshold=m.get("threshold"),
                trained_on=m.get("trained_on"), target_definition=m.get("target_definition"),
                decision_time_assumption=m.get("decision_time_assumption"), feature_columns=m.get("feature_columns"),
                feature_ranges=m.get("feature_ranges"), holdout_metrics=m.get("holdout_metrics"),
                warnings=m.get("load_warnings", []),
                limitations=["Trained on SYNTHETIC data: metrics measure agreement with a simulator, not agronomic accuracy.",
                             "Soil-moisture scale of the training data may differ from your sensors; check the range warnings.",
                             "Only the supported crops are handled; other crops use the rule-based engine.",
                             "Precision on held-out fields is moderate: some 'irrigate' calls are false alarms."])
    return base


# ── runtime feature collection ────────────────────────────────────────────────────────────────────

def pick_prior_reading(latest_ts: datetime, candidates: Iterable[Tuple[datetime, float]], *, target_hours: float = 24.0,
                       tolerance_hours: float = 3.0) -> Optional[Tuple[datetime, float]]:
    """The candidate closest to ``latest_ts - target_hours``, only if within the tolerance; else None."""
    target = latest_ts - timedelta(hours=target_hours)
    best, best_gap = None, None
    for ts, value in candidates:
        gap = abs((ts - target).total_seconds()) / 3600.0
        if gap <= tolerance_hours and (best_gap is None or gap < best_gap):
            best, best_gap = (ts, value), gap
    return best


def gather_runtime_context(db: Session, field_row: Field, *, manual_soil_moisture: Optional[float] = None,
                           now: Optional[datetime] = None) -> Dict[str, Any]:
    """Collect crop, growth-day and soil-moisture inputs for one registered field. Never invents a value."""
    now = now or datetime.now(timezone.utc)
    now_naive = now.astimezone(timezone.utc).replace(tzinfo=None)         # DB timestamps are naive UTC
    crop_row = db.scalar(select(Crop).where(Crop.field_id == field_row.field_id).order_by(Crop.created_at.desc()).limit(1))
    crop_type = (crop_row.crop_type if crop_row and crop_row.crop_type else field_row.crop_type)
    planting = crop_row.planting_date if crop_row else None
    das = (now_naive.date() - planting).days if planting else None
    stage = crop_row.growth_stage if crop_row and crop_row.growth_stage else None
    key = agro_params.normalise_crop(crop_type)
    if stage is None and key is not None and das is not None and das >= 0:
        stage = agro_params.stage_at(key, das).lower()

    ctx: Dict[str, Any] = {"crop_type": crop_type, "planting_date": planting.isoformat() if planting else None,
                           "days_after_sowing": das, "growth_stage": stage, "soil_moisture": None,
                           "soil_moisture_change_24h": None, "reading_age_hours": None, "moisture_source": None}
    if manual_soil_moisture is not None:
        ctx.update(soil_moisture=float(manual_soil_moisture), reading_age_hours=0.0, moisture_source="manual_input")
        return ctx

    latest = db.scalar(select(SensorReading).where(SensorReading.field_id == field_row.field_id,
                                                   SensorReading.soil_moisture.is_not(None))
                       .order_by(SensorReading.timestamp.desc()).limit(1))
    if latest is None:
        return ctx
    ctx.update(soil_moisture=float(latest.soil_moisture), moisture_source="sensor",
               reading_age_hours=round(max(0.0, (now_naive - latest.timestamp).total_seconds() / 3600.0), 2),
               reading_timestamp=latest.timestamp.isoformat())
    window = db.execute(select(SensorReading.timestamp, SensorReading.soil_moisture).where(
        SensorReading.field_id == field_row.field_id, SensorReading.soil_moisture.is_not(None),
        SensorReading.timestamp >= latest.timestamp - timedelta(hours=27),
        SensorReading.timestamp <= latest.timestamp - timedelta(hours=21)).limit(500)).all()
    prior = pick_prior_reading(latest.timestamp, [(ts, float(v)) for ts, v in window])
    if prior is not None:
        ctx["soil_moisture_change_24h"] = round(float(latest.soil_moisture) - prior[1], 3)
    return ctx


def ml_inputs(ctx: Dict[str, Any], forecast_rain_mm: Optional[float]) -> Dict[str, Any]:
    """The raw mapping handed to ``IrrigationPredictor.predict`` (missing values stay None)."""
    return {"crop_type": ctx.get("crop_type"), "days_after_sowing": ctx.get("days_after_sowing"),
            "soil_moisture": ctx.get("soil_moisture"), "soil_moisture_change_24h": ctx.get("soil_moisture_change_24h"),
            "rain_forecast_next24h_mm": forecast_rain_mm}


# ── Two-Stage ML Model (irrigation_model_v2.joblib) ──────────────────────────────────────────

_ML_V2_CACHE: Dict[str, Any] = {"model": None, "checked": False}


def get_ml_v2_model() -> Optional[Dict[str, Any]]:
    """Loads and caches the uploaded Two-Stage Gradient Boosting ML model."""
    if _ML_V2_CACHE["checked"]:
        return _ML_V2_CACHE["model"]
    import joblib

    candidates = [
        BACKEND_DIR / "models" / "trained" / "irrigation_model_v2.joblib",
        BACKEND_DIR.parent / "ml" / "models" / "irrigation_model_v2.joblib",
        Path.cwd() / "ml" / "models" / "irrigation_model_v2.joblib",
    ]
    for p in candidates:
        if p.is_file():
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    m = joblib.load(p)
                if isinstance(m, dict) and "classifier" in m and "regressor" in m:
                    _ML_V2_CACHE["model"] = m
                    log.info("Loaded Two-Stage ML irrigation model from %s", p)
                    break
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not load ML model from %s: %s", p, exc)
    _ML_V2_CACHE["checked"] = True
    return _ML_V2_CACHE["model"]


def predict_ml_v2(
    crop_type: Optional[str] = None,
    growth_stage: Optional[str] = None,
    soil_moisture: Optional[float] = None,
    temperature: Optional[float] = None,
    humidity: Optional[float] = None,
    recent_rainfall_mm: Optional[float] = None,
    forecast_rainfall_mm: Optional[float] = None,
    days_after_sowing: Optional[float] = None,
    soil_type: Optional[str] = "Loam",
    irrigation_type: Optional[str] = "Drip",
    soil_moisture_change_24h: Optional[float] = None,
    days_since_irrigation: Optional[float] = None,
) -> Dict[str, Any]:
    """Inference for the Two-Stage Gradient Boosting expected value model uploaded in irrigation_model_v2.joblib.

    Features: 27 columns matching training on multi-season field telemetry.
    Returns predicted water depth in mm, probability of irrigation, and model metadata.
    """
    model_data = get_ml_v2_model()
    if not model_data:
        return {"available": False, "reason": "Two-Stage ML model file (irrigation_model_v2.joblib) not found."}

    try:
        import pandas as pd

        clf = model_data["classifier"]
        reg = model_data["regressor"]
        cols = model_data["columns"]

        crop_norm = (crop_type or "Rice").strip().title()
        stage_norm = (growth_stage or "Vegetative").strip().title()
        moist_val = float(soil_moisture if soil_moisture is not None else 30.0)
        temp_val = float(temperature if temperature is not None else 28.0)
        hum_val = float(humidity if humidity is not None else 65.0)
        recent_rain = float(recent_rainfall_mm or 0.0)
        fc_rain = float(forecast_rainfall_mm or 0.0)

        # Stage to DAS mapping if not provided
        das = days_after_sowing
        if das is None:
            stage_das = {"Sowing": 10.0, "Vegetative": 35.0, "Flowering": 65.0, "Harvest": 110.0}
            das = stage_das.get(stage_norm, 40.0)

        # Soil moisture change 24h
        moist_chg = soil_moisture_change_24h
        if moist_chg is None:
            moist_chg = min(8.0, recent_rain * 0.4) if recent_rain > 0 else -1.5

        dsi = float(days_since_irrigation if days_since_irrigation is not None else (1.0 if recent_rain > 5 else 4.0))

        row = {c: 0.0 for c in cols}
        row["days_after_sowing"] = float(das)
        row["soil_moisture_0600"] = moist_val
        row["soil_moisture_change_24h"] = float(moist_chg)
        row["temperature_0600"] = temp_val
        row["humidity_0600"] = hum_val
        row["rain_prev24h_mm"] = recent_rain
        row["rain_forecast_next24h_mm"] = fc_rain
        row["irrigation_prev7d_mm"] = 0.0
        row["days_since_irrigation"] = dsi
        row["rain_3d"] = recent_rain
        row["moist_3d_mean"] = moist_val
        row["moist_trend_3d"] = float(moist_chg)

        # One-hot crop
        crop_col = f"crop_type_{crop_norm}"
        if crop_col in cols:
            row[crop_col] = 1.0
        else:
            row["crop_type_Rice"] = 1.0

        # One-hot stage
        stage_col = f"growth_stage_{stage_norm}"
        if stage_col in cols:
            row[stage_col] = 1.0
        else:
            row["growth_stage_Vegetative"] = 1.0

        # One-hot soil
        soil_norm = (soil_type or "Loam").strip().title()
        soil_col = f"soil_type_{soil_norm}"
        if soil_col in cols:
            row[soil_col] = 1.0
        else:
            row["soil_type_Loam"] = 1.0

        # One-hot irrigation
        irrig_norm = (irrigation_type or "Drip").strip().title()
        irrig_col = f"irrigation_type_{irrig_norm}"
        if irrig_col in cols:
            row[irrig_col] = 1.0
        else:
            row["irrigation_type_Drip"] = 1.0

        frame = pd.DataFrame([row], columns=cols)
        prob = float(clf.predict_proba(frame)[0, 1])
        raw_depth = max(0.0, float(reg.predict(frame)[0]))
        expected_depth = round(prob * raw_depth, 1)

        return {
            "available": True,
            "probability": round(prob, 4),
            "raw_depth_mm": round(raw_depth, 1),
            "predicted_water_mm": expected_depth,
            "model_name": "AI Two-Stage Gradient Boosting ML Model",
            "model_version": "v2 (Trained on Field Telemetry)",
            "features_used": {
                "crop": crop_norm,
                "stage": stage_norm,
                "soil_moisture": moist_val,
                "temperature": temp_val,
                "recent_rainfall_mm": recent_rain,
                "forecast_rainfall_mm": fc_rain,
                "days_after_sowing": float(das),
            },
        }
    except Exception as exc:  # noqa: BLE001
        log.error("predict_ml_v2 failed: %s", type(exc).__name__)
        return {"available": False, "reason": f"Prediction failed ({type(exc).__name__})"}

