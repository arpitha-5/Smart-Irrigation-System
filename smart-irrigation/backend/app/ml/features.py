"""Feature engineering for the irrigation model. Pure numpy/pandas; shared by training and serving.

Design rule: every feature must be obtainable in the RUNNING system (sensor readings, field/crop records, the weather
adapter's forecast). That is why soil type, irrigation method and irrigation history from the synthetic dataset are NOT
used (the Field model does not store them; the ablation in docs/ml_irrigation_model.md shows they are not required).

Raw inputs (one row = one field, one decision time):
    crop_type                     one of agro_params.SUPPORTED_CROPS
    days_after_sowing             from the Crop record's planting date
    soil_moisture                 latest valid sensor reading, volumetric %
    soil_moisture_change_24h      latest reading minus the reading ~24 h earlier (percentage points); may be missing
    rain_forecast_next24h_mm      forecast rain sum for the next 24 h; may be missing

Engineered features: ``kc`` (crop coefficient at that growth day, a water-demand proxy), ``stage_idx`` and one-hot crop.
Missing values are kept as NaN (never imputed with made-up numbers); the tree models are trained to tolerate them.
"""
from __future__ import annotations

import math
from typing import Any, List, Mapping

import numpy as np
import pandas as pd

from app.services import agro_params

RAW_COLUMNS: List[str] = ["crop_type", "days_after_sowing", "soil_moisture", "soil_moisture_change_24h",
                          "rain_forecast_next24h_mm"]
CROP_COLUMNS: List[str] = [f"crop_{c}" for c in agro_params.SUPPORTED_CROPS]
NUMERIC_COLUMNS: List[str] = ["days_after_sowing", "kc", "stage_idx", "soil_moisture", "soil_moisture_change_24h",
                              "rain_forecast_next24h_mm"]
FEATURE_COLUMNS: List[str] = NUMERIC_COLUMNS + CROP_COLUMNS

# plausible physical ranges used to reject garbage before it reaches the model
RANGES = {"days_after_sowing": (0, 400), "soil_moisture": (0, 100), "soil_moisture_change_24h": (-100, 100),
          "rain_forecast_next24h_mm": (0, 500)}


class FeatureError(ValueError):
    """Raised when a required input is missing or invalid (the caller must fall back, not guess)."""


def _num(value: Any):
    if isinstance(value, bool) or value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def build_feature_row(raw: Mapping[str, Any]) -> dict:
    """Validate one raw input mapping and return the engineered feature dict (NaN for optional missing values).

    Required: supported crop_type, days_after_sowing, soil_moisture. Optional (NaN if absent or invalid):
    soil_moisture_change_24h, rain_forecast_next24h_mm. Raises FeatureError for a required problem.
    """
    crop = agro_params.normalise_crop(raw.get("crop_type"))
    if crop is None:
        raise FeatureError(f"crop_type {raw.get('crop_type')!r} is not supported by the model "
                           f"(supported: {', '.join(agro_params.SUPPORTED_CROPS)}).")
    out: dict = {}
    for name in ("days_after_sowing", "soil_moisture"):
        v = _num(raw.get(name))
        lo, hi = RANGES[name]
        if v is None or not lo <= v <= hi:
            raise FeatureError(f"{name} is required and must be a number in [{lo}, {hi}], got {raw.get(name)!r}.")
        out[name] = v
    for name in ("soil_moisture_change_24h", "rain_forecast_next24h_mm"):
        v = _num(raw.get(name))
        lo, hi = RANGES[name]
        out[name] = v if v is not None and lo <= v <= hi else float("nan")
    out["kc"] = agro_params.kc_at(crop, out["days_after_sowing"])
    out["stage_idx"] = float(agro_params.STAGES.index(agro_params.stage_at(crop, out["days_after_sowing"])))
    for c in agro_params.SUPPORTED_CROPS:
        out[f"crop_{c}"] = 1.0 if c == crop else 0.0
    return {k: out[k] for k in FEATURE_COLUMNS}


def frame_from_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorised engineering for the training CSV (columns of ``scripts/generate_dataset.py``).

    Rows whose soil moisture is missing (sensor outage in the data) are dropped: the live system never predicts
    from a missing moisture reading. The returned frame also carries ``field_id`` and the targets.
    """
    d = df.copy()
    d = d[d["soil_moisture_0600"].notna()].reset_index(drop=True)
    crops = d["crop_type"].map(agro_params.normalise_crop)
    if crops.isna().any():
        raise FeatureError(f"dataset has unsupported crops: {sorted(d.loc[crops.isna(), 'crop_type'].unique())}")
    out = pd.DataFrame({
        "field_id": d["field_id"],
        "days_after_sowing": d["days_after_sowing"].astype(float),
        "soil_moisture": d["soil_moisture_0600"].astype(float),
        "soil_moisture_change_24h": d["soil_moisture_change_24h"].astype(float),
        "rain_forecast_next24h_mm": d["rain_forecast_next24h_mm"].astype(float),
    })
    out["kc"] = [agro_params.kc_at(c, t) for c, t in zip(crops, out["days_after_sowing"])]
    out["stage_idx"] = [float(agro_params.STAGES.index(agro_params.stage_at(c, t)))
                        for c, t in zip(crops, out["days_after_sowing"])]
    for c in agro_params.SUPPORTED_CROPS:
        out[f"crop_{c}"] = (crops == c).astype(float).values
    out["irrigate_today"] = d["irrigate_today"].astype(int).values
    out["irrigation_mm"] = d["irrigation_mm"].astype(float).values
    out["crop_type"] = crops.values
    return out[["field_id", "crop_type"] + FEATURE_COLUMNS + ["irrigate_today", "irrigation_mm"]]


def mask_forecast(frame: pd.DataFrame, fraction: float, rng: np.random.Generator) -> pd.DataFrame:
    """Copy of ``frame`` with the forecast feature removed for a random fraction of rows (API-downtime augmentation)."""
    out = frame.copy()
    idx = rng.random(len(out)) < fraction
    out.loc[idx, "rain_forecast_next24h_mm"] = np.nan
    return out
