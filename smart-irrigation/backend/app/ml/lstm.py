"""Optional LSTM comparison model (sequence of the last N days -> irrigate today / depth).

The sequence construction below is plain numpy and is unit-tested. The network itself needs PyTorch, which is NOT in
requirements.txt; without it ``train_lstm`` raises ``LSTMUnavailable`` and the training script simply skips this model.
The LSTM is for offline comparison only: the served model is the best tree model (see docs/ml_irrigation_model.md).
"""
from __future__ import annotations

import warnings
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from app.ml import features as F

SEQ_FEATURES = ["soil_moisture", "soil_moisture_change_24h", "rain_forecast_next24h_mm", "kc", "days_after_sowing"]


class LSTMUnavailable(RuntimeError):
    pass


def build_sequences(frame: pd.DataFrame, window: int = 7) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Turn the per-day feature frame into (X[n, window, f], y_irrigate[n], y_mm[n], field_ids[n]).

    Rows are ordered by days_after_sowing within each field; a sequence is the ``window`` consecutive-day rows ending on
    the target day. Days are only chained when they are consecutive, so sensor-outage gaps never produce a sequence that
    silently skips days. NaN inputs are filled with the field's column median BEFORE scaling only for this experiment.
    """
    xs, ys, mms, fids = [], [], [], []
    for fid, g in frame.sort_values(["field_id", "days_after_sowing"]).groupby("field_id"):
        das = g["days_after_sowing"].to_numpy()
        vals = g[SEQ_FEATURES].to_numpy(dtype=float)
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(vals, axis=0)
        med = np.where(np.isnan(med), 0.0, med)          # a column that is missing for the whole field becomes 0
        vals = np.where(np.isnan(vals), med, vals)
        y, mm = g["irrigate_today"].to_numpy(), g["irrigation_mm"].to_numpy()
        for i in range(window - 1, len(g)):
            if das[i] - das[i - window + 1] == window - 1:       # strictly consecutive days
                xs.append(vals[i - window + 1:i + 1])
                ys.append(y[i]); mms.append(mm[i]); fids.append(fid)
    if not xs:
        return np.zeros((0, window, len(SEQ_FEATURES))), np.zeros(0), np.zeros(0), np.array([])
    return np.asarray(xs), np.asarray(ys, dtype=float), np.asarray(mms, dtype=float), np.asarray(fids)


def train_lstm(train: pd.DataFrame, test: pd.DataFrame, *, window: int = 7, epochs: int = 40, seed: int = 42) -> Dict[str, float]:
    """Train a small LSTM on ``train`` fields and return decision metrics on ``test`` fields. Needs PyTorch."""
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise LSTMUnavailable("PyTorch is not installed (pip install torch); LSTM comparison skipped.") from exc
    from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

    torch.manual_seed(seed)
    Xtr, ytr, _, _ = build_sequences(train, window)
    Xte, yte, _, _ = build_sequences(test, window)
    if len(Xtr) == 0 or len(Xte) == 0 or ytr.sum() == 0 or yte.sum() == 0:
        raise LSTMUnavailable("Not enough consecutive-day sequences to train/evaluate an LSTM.")
    mu, sd = Xtr.reshape(-1, Xtr.shape[-1]).mean(0), Xtr.reshape(-1, Xtr.shape[-1]).std(0) + 1e-6
    Xtr_t = torch.tensor((Xtr - mu) / sd, dtype=torch.float32)
    Xte_t = torch.tensor((Xte - mu) / sd, dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.float32)

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(Xtr.shape[-1], 32, batch_first=True)
            self.head = nn.Linear(32, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :]).squeeze(-1)

    net = Net()
    opt = torch.optim.Adam(net.parameters(), lr=1e-2)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor((1 - ytr.mean()) / max(ytr.mean(), 1e-6)))
    for _ in range(epochs):
        net.train()
        opt.zero_grad()
        loss = loss_fn(net(Xtr_t), ytr_t)
        loss.backward()
        opt.step()
    net.eval()
    with torch.no_grad():
        p = torch.sigmoid(net(Xte_t)).numpy()
    best_f1 = max(f1_score(yte, p >= t, zero_division=0) for t in np.arange(0.1, 0.91, 0.05))
    return {"roc_auc": round(float(roc_auc_score(yte, p)), 4), "average_precision": round(float(average_precision_score(yte, p)), 4),
            "best_f1_oracle_threshold": round(float(best_f1), 4), "n_sequences_test": int(len(yte)),
            "note": "classification only; threshold tuned on the test set, so optimistic"}
