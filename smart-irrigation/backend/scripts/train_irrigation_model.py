"""Train, evaluate and save the irrigation ML model.

  python scripts/train_irrigation_model.py                       # generates synthetic data, trains, saves
  python scripts/train_irrigation_model.py --data data/synthetic/irrigation_dataset.csv --version v2

Outputs ``backend/models/irrigation/<version>/{model.joblib,metadata.json,evaluation_report.json}`` and a ``latest.txt``
pointer, and records the run with MLflow (if installed) or the local JSON registry (models/registry.json).
ALL training data is synthetic; see docs/ml_irrigation_model.md for what the metrics do and do not mean.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import pandas as pd  # noqa: E402

from app.ml import features as F  # noqa: E402
from app.ml.lstm import LSTMUnavailable, train_lstm  # noqa: E402
from app.ml.tracking import start_tracker  # noqa: E402
from app.ml.training import save_bundle, split_fields, train_and_evaluate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="irrigation_dataset.csv; omit to generate synthetic data with --fields/--days/--seed")
    ap.add_argument("--fields", type=int, default=48)
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--version", default=None, help="model version label (default: UTC timestamp)")
    ap.add_argument("--models-dir", default=str(BACKEND / "models"))
    ap.add_argument("--no-mlflow", action="store_true", help="force the local JSON registry even if mlflow is installed")
    ap.add_argument("--skip-lstm", action="store_true")
    a = ap.parse_args()

    models_dir = Path(a.models_dir)
    version = a.version or datetime.now(timezone.utc).strftime("v%Y%m%d-%H%M%S")
    if a.data:
        csv = Path(a.data)
    else:
        tmp = Path(tempfile.mkdtemp(prefix="irrig_syn_"))
        subprocess.run([sys.executable, str(BACKEND / "scripts" / "generate_dataset.py"), "--out", str(tmp), "--fields",
                        str(a.fields), "--days", str(a.days), "--seed", str(a.seed)], check=True)
        csv = tmp / "irrigation_dataset.csv"
    frame = F.frame_from_dataset(pd.read_csv(csv))
    print(f"Training rows: {len(frame)} from {frame['field_id'].nunique()} fields (rows with a missing moisture reading are dropped)")

    tracker = start_tracker(models_dir, run_name=version, prefer_mlflow=not a.no_mlflow)
    tracker.log_params({"version": version, "seed": a.seed, "data": str(csv), "n_rows": len(frame)})
    bundle, report = train_and_evaluate(frame, seed=a.seed, tracker=tracker)

    if not a.skip_lstm:
        train, hold = split_fields(frame, report["protocol"]["holdout_fraction"], a.seed)
        try:
            report["holdout"]["lstm"] = {"metrics": train_lstm(train, hold, seed=a.seed)}
        except LSTMUnavailable as exc:
            report["holdout"]["lstm"] = {"skipped": str(exc)}
            print(f"LSTM: {exc}")

    out_dir = save_bundle(bundle, models_dir / "irrigation" / version, report)
    (models_dir / "irrigation" / "latest.txt").write_text(version, encoding="utf-8")
    tracker.log_metrics({f"final_{k}": v for k, v in report["holdout"][report["selected_model"]]["metrics"].items()
                         if isinstance(v, (int, float)) and v == v})
    for f in out_dir.iterdir():
        tracker.log_artifact(str(f))
    run_id = tracker.finish()

    h = report["holdout"][report["selected_model"]]["metrics"]
    print(f"\nSelected model: {report['selected_model']} (CV F1 {report['cross_validation'][report['selected_model']]['metrics']['f1']})")
    print(f"Held-out FIELDS: AUC {h['roc_auc']}  precision {h['precision']}  recall {h['recall']}  F1 {h['f1']}  "
          f"depth MAE {h['depth_mae_mm_on_irrigation_days']} mm  R2 {h['depth_r2_on_irrigation_days']}")
    print(f"Saved to {out_dir}  | tracking: {tracker.backend} run {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
