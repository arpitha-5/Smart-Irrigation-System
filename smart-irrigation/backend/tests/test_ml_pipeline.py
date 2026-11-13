"""ML pipeline tests: parameter drift, train/serve feature parity, leakage-free split, save/load, predictor, tracking, LSTM prep."""
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml import features as F
from app.ml.lstm import LSTMUnavailable, build_sequences, train_lstm
from app.ml.predictor import IrrigationPredictor
from app.ml.tracking import LocalTracker
from app.ml.training import ModelLoadError, load_bundle, save_bundle, split_fields, train_and_evaluate
from app.services import agro_params

BACKEND = Path(__file__).resolve().parents[1]
GEN = BACKEND / "scripts" / "generate_dataset.py"


def _generator():
    spec = importlib.util.spec_from_file_location("generate_dataset_for_test", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dataset(tmp_path, fields=14, days=70, seed=3):
    subprocess.run([sys.executable, str(GEN), "--out", str(tmp_path), "--fields", str(fields), "--days", str(days),
                    "--seed", str(seed)], check=True, capture_output=True)
    return pd.read_csv(tmp_path / "irrigation_dataset.csv")


# ── parameters must match the generator the model was trained with ───────────────────────────────────
def test_agro_params_match_the_data_generator():
    g = _generator()
    for crop, spec in g.CROPS.items():
        key = crop.lower()
        assert agro_params.CROP_KC[key] == spec["kc"] and agro_params.CROP_STAGE_DAYS[key] == spec["days"]
        for das in (0, 10, 25, 60, 100, 140):
            assert math.isclose(agro_params.kc_at(key, das), g.kc_at(crop, das))
            assert agro_params.stage_at(key, das) == g.stage_at(crop, das)
    assert set(agro_params.SUPPORTED_CROPS) == {c.lower() for c in g.CROPS}


# ── feature engineering ──────────────────────────────────────────────────────────────────────────────
def test_build_feature_row_valid_and_column_order():
    row = F.build_feature_row({"crop_type": " Rice ", "days_after_sowing": 60, "soil_moisture": 25.0,
                               "soil_moisture_change_24h": -1.2, "rain_forecast_next24h_mm": 0})
    assert list(row) == F.FEATURE_COLUMNS
    assert row["crop_rice"] == 1.0 and row["crop_wheat"] == 0.0 and row["stage_idx"] == 2.0
    assert math.isclose(row["kc"], agro_params.kc_at("rice", 60))


def test_build_feature_row_rejects_bad_required_inputs():
    ok = {"crop_type": "rice", "days_after_sowing": 30, "soil_moisture": 20.0}
    F.build_feature_row(ok)
    for patch in ({"crop_type": "banana"}, {"crop_type": None}, {"soil_moisture": None}, {"soil_moisture": 120},
                  {"soil_moisture": float("nan")}, {"soil_moisture": True}, {"days_after_sowing": -1}, {"days_after_sowing": "x"}):
        try:
            F.build_feature_row({**ok, **patch})
        except F.FeatureError:
            continue
        raise AssertionError(f"accepted bad input {patch}")


def test_optional_features_become_nan_not_made_up_values():
    row = F.build_feature_row({"crop_type": "maize", "days_after_sowing": 30, "soil_moisture": 20.0,
                               "soil_moisture_change_24h": "bad", "rain_forecast_next24h_mm": -4})
    assert math.isnan(row["soil_moisture_change_24h"]) and math.isnan(row["rain_forecast_next24h_mm"])


def test_training_and_serving_features_are_identical(tmp_path):
    frame = F.frame_from_dataset(_dataset(tmp_path))
    for i in np.linspace(0, len(frame) - 1, 25).astype(int):
        r = frame.iloc[i]
        served = F.build_feature_row({"crop_type": r["crop_type"], "days_after_sowing": r["days_after_sowing"],
                                      "soil_moisture": r["soil_moisture"], "soil_moisture_change_24h": r["soil_moisture_change_24h"],
                                      "rain_forecast_next24h_mm": r["rain_forecast_next24h_mm"]})
        for col in F.FEATURE_COLUMNS:
            a, b = float(r[col]), served[col]
            assert (math.isnan(a) and math.isnan(b)) or math.isclose(a, b, abs_tol=1e-9), col


def test_rows_without_a_moisture_reading_are_dropped(tmp_path):
    raw = _dataset(tmp_path)
    frame = F.frame_from_dataset(raw)
    assert len(frame) == raw["soil_moisture_0600"].notna().sum() and frame["soil_moisture"].notna().all()


def test_mask_forecast_only_touches_the_forecast(tmp_path):
    frame = F.frame_from_dataset(_dataset(tmp_path))
    masked = F.mask_forecast(frame, 0.5, np.random.default_rng(0))
    assert 0.35 < masked["rain_forecast_next24h_mm"].isna().mean() < 0.65
    assert masked["soil_moisture"].equals(frame["soil_moisture"]) and frame["rain_forecast_next24h_mm"].notna().all()


# ── validation protocol ──────────────────────────────────────────────────────────────────────────────
def test_holdout_split_shares_no_field(tmp_path):
    frame = F.frame_from_dataset(_dataset(tmp_path))
    train, hold = split_fields(frame, 0.25, seed=1)
    assert set(train.field_id).isdisjoint(set(hold.field_id)) and len(hold) > 0 and len(train) > 0
    assert set(train.field_id) | set(hold.field_id) == set(frame.field_id)


# ── train / save / load / predict ────────────────────────────────────────────────────────────────────
def _trained(tmp_path):
    frame = F.frame_from_dataset(_dataset(tmp_path))
    return train_and_evaluate(frame, seed=5, n_splits=3)


def test_training_report_is_complete_and_roundtrip_is_exact(tmp_path):
    bundle, report = _trained(tmp_path)
    assert report["selected_model"] in report["cross_validation"] and 0.1 <= bundle.threshold <= 0.9
    h = report["holdout"][report["selected_model"]]
    assert {"roc_auc", "precision", "recall", "f1", "depth_mae_mm_on_irrigation_days"} <= set(h["metrics"])
    assert "metrics_forecast_unavailable" in h and "global_moisture_trigger" in report["baselines"]
    save_bundle(bundle, tmp_path / "irrigation" / "t1", report)
    (tmp_path / "irrigation" / "latest.txt").write_text("t1")
    a, b = IrrigationPredictor(bundle, "t1"), IrrigationPredictor.load(tmp_path)
    raw = {"crop_type": "rice", "days_after_sowing": 55, "soil_moisture": 21.0, "soil_moisture_change_24h": -1.0,
           "rain_forecast_next24h_mm": 0.0}
    assert a.predict(raw).to_dict() == b.predict(raw).to_dict()
    meta = json.loads((tmp_path / "irrigation" / "t1" / "metadata.json").read_text())
    assert meta["feature_columns"] == F.FEATURE_COLUMNS and "SYNTHETIC" in meta["trained_on"] and "gross" in meta["target_definition"]


def test_predictor_never_guesses(tmp_path):
    bundle, _ = _trained(tmp_path)
    p = IrrigationPredictor(bundle, "t")
    good = {"crop_type": "rice", "days_after_sowing": 55, "soil_moisture": 21.0}
    assert p.predict(good).available
    for patch, word in (({"crop_type": "banana"}, "not supported"), ({"soil_moisture": None}, "soil_moisture"),
                        ({"days_after_sowing": None}, "days_after_sowing")):
        r = p.predict({**good, **patch})
        assert r.available is False and word in r.reason and r.depth_mm is None


def test_predictor_flags_missing_optionals_and_extrapolation(tmp_path):
    bundle, _ = _trained(tmp_path)
    p = IrrigationPredictor(bundle, "t")
    r = p.predict({"crop_type": "rice", "days_after_sowing": 55, "soil_moisture": 21.0})
    assert set(r.missing_optional_features) == {"soil_moisture_change_24h", "rain_forecast_next24h_mm"} and r.warnings
    far = p.predict({"crop_type": "rice", "days_after_sowing": 55, "soil_moisture": 90.0})
    assert far.available and any("outside the range" in w for w in far.warnings)


def test_depth_is_zero_unless_the_model_says_irrigate(tmp_path):
    bundle, _ = _trained(tmp_path)
    p = IrrigationPredictor(bundle, "t")
    for m in (12, 18, 24, 30, 36):
        r = p.predict({"crop_type": "rice", "days_after_sowing": 55, "soil_moisture": m, "rain_forecast_next24h_mm": 0})
        assert (r.depth_mm > 0) == r.irrigate and 0 <= r.probability <= 1


def test_load_errors_are_clean(tmp_path):
    for bad in ("../x", "..", ".hidden", "a/b", ""):
        (tmp_path / "irrigation").mkdir(exist_ok=True)
        try:
            IrrigationPredictor.load(tmp_path, bad)
        except ModelLoadError:
            continue
        raise AssertionError(f"accepted version {bad!r}")
    try:
        IrrigationPredictor.load(tmp_path / "nowhere")
    except ModelLoadError as exc:
        assert "train_irrigation_model" in str(exc)
    else:
        raise AssertionError("loaded a model that does not exist")
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "model.joblib").write_bytes(b"not a pickle")
    (tmp_path / "broken" / "metadata.json").write_text("{}")
    try:
        load_bundle(tmp_path / "broken")
    except ModelLoadError:
        pass
    else:
        raise AssertionError("loaded a corrupt model")


def test_feature_mismatch_is_rejected(tmp_path):
    bundle, report = _trained(tmp_path)
    bundle.metadata["feature_columns"] = ["something_else"]
    save_bundle(bundle, tmp_path / "m")
    try:
        load_bundle(tmp_path / "m")
    except ModelLoadError as exc:
        assert "different features" in str(exc)
    else:
        raise AssertionError("accepted a model with other features")


# ── shipped artifact (backend/models) ────────────────────────────────────────────────────────────────
def test_shipped_model_behaves_sensibly():
    models = BACKEND / "models"
    if not (models / "irrigation" / "latest.txt").is_file():
        return                                    # no artifact in this checkout; nothing to assert
    p = IrrigationPredictor.load(models)
    rice = {"crop_type": "rice", "days_after_sowing": 60, "soil_moisture_change_24h": -1.0, "rain_forecast_next24h_mm": 0.0}
    dry, wet = p.predict({**rice, "soil_moisture": 16.0}), p.predict({**rice, "soil_moisture": 36.0})
    assert dry.irrigate and dry.depth_mm > 0 and not wet.irrigate and dry.probability > wet.probability
    rainy = p.predict({**rice, "soil_moisture": 22.0, "rain_forecast_next24h_mm": 30.0})
    dry22 = p.predict({**rice, "soil_moisture": 22.0})
    assert rainy.probability < dry22.probability
    assert "SYNTHETIC" in p.metadata["trained_on"]


# ── tracking and LSTM data prep ──────────────────────────────────────────────────────────────────────
def test_local_tracker_writes_run_and_index(tmp_path):
    t = LocalTracker(tmp_path, "exp", "r1")
    t.log_params({"a": 1}); t.log_metrics({"final_f1": 0.5, "other": 1}); t.log_artifact("x/model.joblib")
    run_id = t.finish()
    assert (tmp_path / "runs" / f"{run_id}.json").is_file()
    index = json.loads((tmp_path / "registry.json").read_text())
    assert index[-1]["run_id"] == run_id and index[-1]["headline_metrics"] == {"final_f1": 0.5}


def test_lstm_sequences_only_chain_consecutive_days():
    days = [1, 2, 3, 4, 5, 6, 7, 8, 12, 13, 14, 15, 16, 17, 18]          # a gap between day 8 and day 12
    df = pd.DataFrame({"field_id": "F1", "days_after_sowing": days, "soil_moisture": 20.0, "soil_moisture_change_24h": np.nan,
                       "rain_forecast_next24h_mm": 0.0, "kc": 1.0, "irrigate_today": 0, "irrigation_mm": 0.0})
    X, y, mm, fid = build_sequences(df, window=7)
    assert X.shape == (3, 7, 5)                                    # windows ending on day 7, 8 and 18 only
    assert not np.isnan(X).any()
    assert build_sequences(df.iloc[:3], window=7)[0].shape[0] == 0


def test_lstm_skips_cleanly_without_torch(tmp_path):
    try:
        import torch  # noqa: F401
        return                                    # torch present: the real training path is exercised elsewhere
    except ImportError:
        pass
    frame = F.frame_from_dataset(_dataset(tmp_path))
    train, hold = split_fields(frame, 0.25, seed=1)
    try:
        train_lstm(train, hold)
    except LSTMUnavailable:
        return
    raise AssertionError("expected LSTMUnavailable")
