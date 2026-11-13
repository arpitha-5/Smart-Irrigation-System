"""Experiment tracking. Uses MLflow when it is installed, otherwise a dependency-free local JSON registry.

Both record the same things (parameters, metrics, artifact paths) so model versions can be compared as new seasonal data
arrives. The local registry is ``<models_dir>/runs/<run_id>.json`` plus ``<models_dir>/registry.json`` (an index).
MLflow is optional: it is not in requirements.txt. Install it (``pip install mlflow``) to get the MLflow UI.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger("irrigation.ml.tracking")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LocalTracker:
    backend = "local-json"

    def __init__(self, models_dir: Path, experiment: str, run_name: str):
        self.dir = Path(models_dir)
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.record: Dict[str, Any] = {"run_id": self.run_id, "experiment": experiment, "run_name": run_name,
                                       "started_at_utc": _now(), "params": {}, "metrics": {}, "artifacts": []}

    def log_params(self, params: Dict[str, Any]) -> None:
        self.record["params"].update({k: v for k, v in params.items()})

    def log_metrics(self, metrics: Dict[str, float]) -> None:
        self.record["metrics"].update(metrics)

    def log_artifact(self, path: str) -> None:
        self.record["artifacts"].append(str(path))

    def finish(self) -> str:
        self.record["finished_at_utc"] = _now()
        runs = self.dir / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / f"{self.run_id}.json").write_text(json.dumps(self.record, indent=2, default=str), encoding="utf-8")
        index_path = self.dir / "registry.json"
        index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else []
        index.append({"run_id": self.run_id, "experiment": self.record["experiment"], "run_name": self.record["run_name"],
                      "finished_at_utc": self.record["finished_at_utc"], "artifacts": self.record["artifacts"],
                      "headline_metrics": {k: v for k, v in self.record["metrics"].items() if k.startswith("final_")}})
        index_path.write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")
        return self.run_id


class MlflowTracker:
    backend = "mlflow"

    def __init__(self, models_dir: Path, experiment: str, run_name: str):
        import mlflow  # imported lazily: optional dependency
        self.mlflow = mlflow
        uri = (Path(models_dir) / "mlruns").resolve().as_uri()
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(experiment)
        self.run = mlflow.start_run(run_name=run_name)
        self.run_id = self.run.info.run_id

    def log_params(self, params: Dict[str, Any]) -> None:
        self.mlflow.log_params({k: str(v)[:250] for k, v in params.items()})

    def log_metrics(self, metrics: Dict[str, float]) -> None:
        self.mlflow.log_metrics({k: float(v) for k, v in metrics.items() if v == v})  # skip NaN

    def log_artifact(self, path: str) -> None:
        self.mlflow.log_artifact(str(path))

    def finish(self) -> str:
        self.mlflow.end_run()
        return self.run_id


def start_tracker(models_dir: Path, experiment: str = "smart-irrigation", run_name: str = "train",
                  prefer_mlflow: bool = True):
    """Return an MlflowTracker if mlflow is importable (and works), else a LocalTracker."""
    if prefer_mlflow:
        try:
            return MlflowTracker(models_dir, experiment, run_name)
        except ImportError:
            log.info("mlflow is not installed; using the local JSON run registry.")
        except Exception as exc:  # noqa: BLE001 - tracking must never block training
            log.warning("mlflow could not start (%s); using the local JSON run registry.", type(exc).__name__)
    return LocalTracker(models_dir, experiment, run_name)
