"""Serve the trained irrigation model. Pure (numpy/pandas/scikit-learn); no database or HTTP.

``IrrigationPredictor.predict(raw)`` never raises for bad input: it returns ``MLPrediction(available=False, reason=...)``
so the caller can fall back to the rule-based engine. Nothing is imputed: a missing REQUIRED input means no prediction.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import pandas as pd

from app.ml import features as F
from app.ml.training import ModelBundle, ModelLoadError, load_bundle


@dataclass
class MLPrediction:
    available: bool
    reason: Optional[str] = None                 # why no prediction was made
    irrigate: Optional[bool] = None
    probability: Optional[float] = None          # P(irrigate today) from the classifier
    threshold: Optional[float] = None
    depth_mm: Optional[float] = None             # recommended GROSS depth; 0.0 when irrigate is False
    unit: str = "mm"
    depth_basis: str = "gross depth applied at the field surface (1 mm over 1 ha = 10,000 L)"
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    features_used: Dict[str, Any] = field(default_factory=dict)
    missing_optional_features: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IrrigationPredictor:
    def __init__(self, bundle: ModelBundle, version: str):
        self.bundle, self.version = bundle, version

    # ── loading ───────────────────────────────────────────────────────────────────────────────────
    @classmethod
    def load(cls, models_dir: Path, version: Optional[str] = None) -> "IrrigationPredictor":
        root = Path(models_dir) / "irrigation"
        if version is None:
            pointer = root / "latest.txt"
            if not pointer.is_file():
                raise ModelLoadError(f"No trained model under {root}. Run: python scripts/train_irrigation_model.py")
            version = pointer.read_text(encoding="utf-8").strip()
        if not version or "/" in version or "\\" in version or version.startswith("."):
            raise ModelLoadError("Invalid model version label.")
        return cls(load_bundle(root / version), version)

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.bundle.metadata

    # ── prediction ────────────────────────────────────────────────────────────────────────────────
    def predict(self, raw: Mapping[str, Any]) -> MLPrediction:
        meta = self.metadata
        out = MLPrediction(available=False, model_name=meta.get("model_name"), model_version=self.version,
                           threshold=self.bundle.threshold)
        try:
            row = F.build_feature_row(raw)
        except F.FeatureError as exc:
            out.reason = str(exc)
            return out

        for col in ("soil_moisture_change_24h", "rain_forecast_next24h_mm"):
            if math.isnan(row[col]):
                out.missing_optional_features.append(col)
        if out.missing_optional_features:
            out.warnings.append("Optional inputs unavailable (" + ", ".join(out.missing_optional_features) +
                                "); the model was trained to tolerate this but is less accurate without them.")
        for col, (lo, hi) in (meta.get("feature_ranges") or {}).items():
            v = row.get(col)
            if v is not None and not math.isnan(v) and not lo <= v <= hi:
                out.warnings.append(f"{col}={v:g} is outside the range the model was trained on ({lo:g} to {hi:g}); "
                                    "the prediction is an extrapolation and may be unreliable.")
        frame = pd.DataFrame([row], columns=F.FEATURE_COLUMNS)
        prob = float(self.bundle.classifier.predict_proba(frame)[0, 1])
        depth = max(0.0, float(self.bundle.regressor.predict(frame)[0]))
        irrigate = prob >= self.bundle.threshold
        out.available = True
        out.probability = round(prob, 4)
        out.irrigate = bool(irrigate)
        out.depth_mm = round(depth, 1) if irrigate else 0.0
        out.features_used = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}
        return out
