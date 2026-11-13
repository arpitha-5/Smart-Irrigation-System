"""Train, compare and evaluate the irrigation models (Random Forest vs Gradient Boosting, plus naive baselines).

Pure numpy / pandas / scikit-learn. No database, no HTTP.

Model structure ("hurdle"): the target is zero on most days (the farmer did not irrigate), so one regressor is a poor fit.
  * classifier  -> P(irrigate today)           (class-weighted; the decision threshold is chosen by grouped CV)
  * regressor   -> gross applied depth in mm   (trained ONLY on days with irrigation)
  recommended depth = regressor(x) if P >= threshold else 0.0

Validation protocol (avoids optimistic numbers from consecutive days of the same field leaking across a random split):
  1. ~20 % of FIELDS are held out and never used for fitting, model choice or the threshold.
  2. On the remaining fields, GroupKFold (grouped by field) compares the models and picks the threshold.
  3. The chosen model is refit on the training fields and scored once on the held-out fields (reported).
  4. The shipped artifact is refit on all fields (the held-out numbers describe the same recipe, not that exact file).

Targets: ``irrigation_mm`` is the GROSS depth applied that day (net crop need / system efficiency), as produced by the
synthetic generator. All data is synthetic: the metrics measure how well the model learned the simulator's behaviour,
NOT agronomic correctness on real farms.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.metrics import (average_precision_score, f1_score, mean_absolute_error, precision_score, r2_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import GroupKFold

from app.ml import features as F

log = logging.getLogger("irrigation.ml.training")

MODEL_FILE = "model.joblib"
METADATA_FILE = "metadata.json"
TARGET_DEFINITION = ("irrigation_mm = gross water depth applied on the day (mm of water over the field surface; "
                     "net crop need divided by system efficiency). 1 mm over 1 ha = 10,000 L.")
FORECAST_DROPOUT = 0.15      # share of training rows whose forecast is hidden, so the model copes with API downtime
MODEL_KINDS = ("random_forest", "gradient_boosting")


class ModelLoadError(RuntimeError):
    pass


@dataclass
class ModelBundle:
    classifier: Any
    regressor: Any
    threshold: float
    kind: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── fitting ───────────────────────────────────────────────────────────────────────────────────────

def _make(kind: str, seed: int):
    if kind == "random_forest":
        clf = RandomForestClassifier(n_estimators=200, min_samples_leaf=3, class_weight="balanced_subsample",
                                     random_state=seed, n_jobs=-1)
        reg = RandomForestRegressor(n_estimators=200, min_samples_leaf=2, random_state=seed, n_jobs=-1)
    elif kind == "gradient_boosting":
        clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.06, class_weight="balanced", random_state=seed)
        reg = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06, random_state=seed)
    else:
        raise ValueError(f"unknown model kind {kind!r}; choose from {MODEL_KINDS}")
    return clf, reg


def fit_models(kind: str, frame: pd.DataFrame, seed: int, dropout: float = FORECAST_DROPOUT) -> Tuple[Any, Any]:
    """Fit classifier (all rows) and regressor (irrigation days only) on a feature frame."""
    rng = np.random.default_rng(seed)
    train = F.mask_forecast(frame, dropout, rng) if dropout > 0 else frame
    clf, reg = _make(kind, seed)
    clf.fit(train[F.FEATURE_COLUMNS], train["irrigate_today"])
    pos = train[train["irrigation_mm"] > 0]
    reg.fit(pos[F.FEATURE_COLUMNS], pos["irrigation_mm"])
    return clf, reg


def predict_frame(clf, reg, frame: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    X = frame[F.FEATURE_COLUMNS]
    return clf.predict_proba(X)[:, 1], np.clip(reg.predict(X), 0.0, None)


# ── metrics ───────────────────────────────────────────────────────────────────────────────────────

def pick_threshold(y: np.ndarray, prob: np.ndarray) -> float:
    grid = np.round(np.arange(0.10, 0.91, 0.05), 2)
    scores = [f1_score(y, prob >= t, zero_division=0) for t in grid]
    return float(grid[int(np.argmax(scores))])


def decision_metrics(frame: pd.DataFrame, prob: np.ndarray, depth: np.ndarray, threshold: float) -> Dict[str, float]:
    y = frame["irrigate_today"].values
    mm = frame["irrigation_mm"].values
    pred = prob >= threshold
    pos = y == 1
    out = {
        "n_rows": int(len(y)), "n_irrigation_days": int(pos.sum()), "irrigation_day_rate": round(float(y.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y, prob)), 4) if 0 < y.sum() < len(y) else float("nan"),
        "average_precision": round(float(average_precision_score(y, prob)), 4),
        "threshold": threshold,
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 4),
        "depth_mae_mm_on_irrigation_days": round(float(mean_absolute_error(mm[pos], depth[pos])), 3),
        "depth_rmse_mm_on_irrigation_days": round(float(np.sqrt(np.mean((mm[pos] - depth[pos]) ** 2))), 3),
        "depth_r2_on_irrigation_days": round(float(r2_score(mm[pos], depth[pos])), 4),
    }
    # depth error on days where the model both fires and the farmer irrigated (what the farmer would actually see)
    both = pred & pos
    out["depth_mae_mm_when_both_irrigate"] = round(float(mean_absolute_error(mm[both], depth[both])), 3) if both.any() else float("nan")
    return out


def baseline_metrics(train: pd.DataFrame, test: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Naive comparison points the ML model must beat."""
    y = test["irrigate_today"].values
    mm = test["irrigation_mm"].values
    pos = y == 1
    mean_pos = float(train.loc[train["irrigation_mm"] > 0, "irrigation_mm"].mean())
    by_crop = train[train["irrigation_mm"] > 0].groupby("crop_type")["irrigation_mm"].mean().to_dict()
    # a single global soil-moisture trigger, tuned on the training fields
    grid = np.arange(5, 60, 1.0)
    best_t = max(grid, key=lambda t: f1_score(train["irrigate_today"], train["soil_moisture"] < t, zero_division=0))
    trig = (test["soil_moisture"].values < best_t)
    depth = np.array([by_crop.get(c, mean_pos) for c in test["crop_type"]])
    return {
        "always_no_irrigation": {"recall": 0.0, "precision": float("nan"), "f1": 0.0,
                                 "note": "never irrigates; scores well on overall MAE only because 90 % of days are dry"},
        "global_moisture_trigger": {
            "trigger_below_pct": float(best_t),
            "precision": round(float(precision_score(y, trig, zero_division=0)), 4),
            "recall": round(float(recall_score(y, trig, zero_division=0)), 4),
            "f1": round(float(f1_score(y, trig, zero_division=0)), 4),
            "depth_mae_mm_on_irrigation_days": round(float(mean_absolute_error(mm[pos], depth[pos])), 3),
            "note": "irrigate when moisture < trigger, apply the crop's mean training depth"},
        "mean_depth_only": {"depth_mae_mm_on_irrigation_days": round(float(mean_absolute_error(mm[pos], np.full(pos.sum(), mean_pos))), 3)},
    }


# ── training pipeline ─────────────────────────────────────────────────────────────────────────────

def split_fields(frame: pd.DataFrame, holdout_fraction: float, seed: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    fields = np.array(sorted(frame["field_id"].unique()))
    rng = np.random.default_rng(seed)
    rng.shuffle(fields)
    n_hold = max(1, int(round(len(fields) * holdout_fraction)))
    hold = set(fields[:n_hold])
    is_hold = frame["field_id"].isin(hold)
    return frame[~is_hold].reset_index(drop=True), frame[is_hold].reset_index(drop=True)


def cross_validate(kind: str, frame: pd.DataFrame, seed: int, n_splits: int = 5) -> Dict[str, Any]:
    prob = np.zeros(len(frame))
    depth = np.zeros(len(frame))
    splits = min(n_splits, frame["field_id"].nunique())
    for tr, te in GroupKFold(n_splits=splits).split(frame, groups=frame["field_id"]):
        clf, reg = fit_models(kind, frame.iloc[tr], seed)
        prob[te], depth[te] = predict_frame(clf, reg, frame.iloc[te])
    thr = pick_threshold(frame["irrigate_today"].values, prob)
    return {"threshold": thr, "metrics": decision_metrics(frame, prob, depth, thr)}


def train_and_evaluate(frame: pd.DataFrame, *, seed: int = 42, holdout_fraction: float = 0.2, n_splits: int = 5,
                       kinds: Tuple[str, ...] = MODEL_KINDS, tracker=None) -> Tuple[ModelBundle, Dict[str, Any]]:
    """Run the whole protocol. Returns (bundle refit on all fields, evaluation report dict)."""
    train, hold = split_fields(frame, holdout_fraction, seed)
    report: Dict[str, Any] = {
        "protocol": {"seed": seed, "holdout_fraction": holdout_fraction, "cv_splits": n_splits,
                     "train_fields": int(train["field_id"].nunique()), "holdout_fields": int(hold["field_id"].nunique()),
                     "forecast_dropout_in_training": FORECAST_DROPOUT},
        "target_definition": TARGET_DEFINITION, "cross_validation": {}, "holdout": {}, "baselines": baseline_metrics(train, hold)}

    for kind in kinds:
        cv = cross_validate(kind, train, seed, n_splits)
        report["cross_validation"][kind] = cv
        if tracker:
            tracker.log_metrics({f"cv_{kind}_{k}": v for k, v in cv["metrics"].items() if isinstance(v, (int, float))})

    # model choice: best cross-validated F1 (ties broken by ROC-AUC), decided WITHOUT looking at the holdout
    best = max(kinds, key=lambda k: (report["cross_validation"][k]["metrics"]["f1"], report["cross_validation"][k]["metrics"]["roc_auc"]))
    threshold = report["cross_validation"][best]["threshold"]
    report["selected_model"] = best
    report["selected_threshold"] = threshold

    for kind in kinds:  # every model is scored on the untouched holdout for transparency, using its own CV threshold
        clf, reg = fit_models(kind, train, seed)
        p, d = predict_frame(clf, reg, hold)
        entry = {"threshold": report["cross_validation"][kind]["threshold"],
                 "metrics": decision_metrics(hold, p, d, report["cross_validation"][kind]["threshold"])}
        if kind == best:  # robustness: same model, forecast unavailable
            p2, d2 = predict_frame(clf, reg, F.mask_forecast(hold, 1.0, np.random.default_rng(0)))
            entry["metrics_forecast_unavailable"] = decision_metrics(hold, p2, d2, threshold)
            by_crop = {}
            for crop, g in hold.assign(_p=p, _d=d).groupby("crop_type"):
                if g["irrigate_today"].sum() > 0:
                    by_crop[crop] = decision_metrics(g, g["_p"].values, g["_d"].values, threshold)
            entry["by_crop"] = by_crop
        report["holdout"][kind] = entry
        if tracker:
            tracker.log_metrics({f"holdout_{kind}_{k}": v for k, v in entry["metrics"].items() if isinstance(v, (int, float))})

    clf, reg = fit_models(best, frame, seed)           # shipped artifact: all fields
    pos = frame[frame["irrigation_mm"] > 0]["irrigation_mm"]
    meta = {
        "model_name": f"irrigation-hurdle-{best}", "kind": best, "threshold": threshold,
        "feature_columns": F.FEATURE_COLUMNS, "supported_crops": list(F.agro_params.SUPPORTED_CROPS),
        "target_definition": TARGET_DEFINITION, "trained_on": "SYNTHETIC data (scripts/generate_dataset.py)",
        "n_training_rows": int(len(frame)), "n_training_fields": int(frame["field_id"].nunique()),
        "training_depth_range_mm": [round(float(pos.min()), 2), round(float(pos.max()), 2)],
        "decision_time_assumption": "trained on 06:00 local-time decisions (one decision per field-day)",
        "feature_ranges": {c: [round(float(frame[c].min()), 3), round(float(frame[c].max()), 3)]
                           for c in ("days_after_sowing", "soil_moisture", "soil_moisture_change_24h", "rain_forecast_next24h_mm")},
        "libraries": {"scikit-learn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
        "holdout_metrics": report["holdout"][best]["metrics"], "cv_metrics": report["cross_validation"][best]["metrics"],
    }
    return ModelBundle(clf, reg, threshold, best, meta), report


# ── persistence ───────────────────────────────────────────────────────────────────────────────────

def _json_safe(obj: Any) -> Any:
    """NaN/inf are not valid JSON; store them as null so any JSON tool can read the report."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def save_bundle(bundle: ModelBundle, directory: Path, report: Optional[Dict[str, Any]] = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump({"classifier": bundle.classifier, "regressor": bundle.regressor, "threshold": bundle.threshold,
                 "kind": bundle.kind}, directory / MODEL_FILE, compress=3)
    (directory / METADATA_FILE).write_text(json.dumps(_json_safe(bundle.metadata), indent=2, default=str, allow_nan=False), encoding="utf-8")
    if report is not None:
        (directory / "evaluation_report.json").write_text(json.dumps(_json_safe(report), indent=2, default=str, allow_nan=False), encoding="utf-8")
    return directory


def load_bundle(directory: Path) -> ModelBundle:
    """Load a saved bundle. Only call this for directories you trust: joblib files are pickles."""
    model_path, meta_path = directory / MODEL_FILE, directory / METADATA_FILE
    if not model_path.is_file() or not meta_path.is_file():
        raise ModelLoadError(f"No model found in {directory}. Train one with: python scripts/train_irrigation_model.py")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        raw = joblib.load(model_path)
        bundle = ModelBundle(raw["classifier"], raw["regressor"], float(raw["threshold"]), raw["kind"], meta)
    except Exception as exc:  # noqa: BLE001 - unpickling can fail in many ways (version mismatch, corruption)
        raise ModelLoadError(f"Could not load the model in {directory} ({type(exc).__name__}). "
                             "Retrain with: python scripts/train_irrigation_model.py") from exc
    if meta.get("feature_columns") != F.FEATURE_COLUMNS:
        raise ModelLoadError("The saved model was trained with different features than this code expects; retrain it.")
    trained_with = (meta.get("libraries") or {}).get("scikit-learn")
    if trained_with and trained_with.split(".")[:2] != sklearn.__version__.split(".")[:2]:
        bundle.metadata.setdefault("load_warnings", []).append(
            f"Model was trained with scikit-learn {trained_with}, running {sklearn.__version__}; retrain if results look wrong.")
    return bundle
