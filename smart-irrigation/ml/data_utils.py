import os
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin

# ========================================================
# Two-Stage Model Architecture for Zero-Inflated Targets
# ========================================================
class TwoStageIrrigationModel(BaseEstimator, RegressorMixin):
    """
    Two-Stage Hurdle / Expected Value Model:
    Stage 1: Binary classifier (predicts whether irrigation is needed today).
    Stage 2: Continuous regressor (trained strictly on positive days y > 0).
    
    Modes:
      - 'expected_value': P(irrigate > 0 | X) * E[y | y > 0, X] (prevents severe RMSE penalties)
      - 'hurdle': Hard thresholding at given threshold (minimizes MAE)
    """
    def __init__(self, classifier=None, regressor=None, threshold=0.40, mode="expected_value"):
        self.classifier = classifier
        self.regressor = regressor
        self.threshold = threshold
        self.mode = mode

    def fit(self, X, y):
        y_arr = np.asarray(y)
        # Stage 1: Train classifier on all data (0 vs > 0)
        y_binary = (y_arr > 0).astype(int)
        self.classifier.fit(X, y_binary)

        # Stage 2: Train regressor strictly on positive days
        pos_mask = (y_arr > 0)
        X_pos = X.loc[pos_mask] if hasattr(X, "loc") else X[pos_mask]
        y_pos = y_arr[pos_mask]
        self.regressor.fit(X_pos, y_pos)
        return self

    def predict(self, X):
        proba = self.classifier.predict_proba(X)[:, 1]
        amounts = np.maximum(0.0, self.regressor.predict(X))
        if self.mode == "expected_value":
            return proba * amounts
        else:
            return np.where(proba >= self.threshold, amounts, 0.0)


# ========================================================
# Data Loading and Preprocessing
# ========================================================
def load_split(filepath="irrigation_dataset_cleaned.csv", split_ratio=0.8):
    """
    Loads dataset, fixes sentinel values, applies one-hot encoding,
    and performs a chronological date-based 80/20 train/test split.
    """
    if not os.path.isabs(filepath):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(base_dir, filepath)

    df = pd.read_csv(filepath)

    # 1. Sort safely by date (and field_id only if it exists)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        sort_cols = [c for c in ["date", "field_id", "nfield_id"] if c in df.columns]
        df = df.sort_values(by=sort_cols).reset_index(drop=True)

    # 2. FIX SENTINEL VALUE 99:
    if "days_since_irrigation" in df.columns:
        df["never_irrigated"] = (df["days_since_irrigation"] == 99).astype(int)
        cap_val = (
            df["days_after_sowing"]
            if "days_after_sowing" in df.columns
            else df.loc[df["days_since_irrigation"] < 99, "days_since_irrigation"].max()
        )
        df["days_since_irrigation"] = np.where(
            df["days_since_irrigation"] == 99,
            cap_val,
            df["days_since_irrigation"]
        )

    # Target variable
    target = "irrigation_mm"

    # Exclude non-feature columns, spatial IDs, and target leakers
    excluded = ["irrigate_today", "field_id", "nfield_id", "date", target]
    feature_cols = [c for c in df.columns if c not in excluded]

    # Automatically identify categorical columns to one-hot encode
    cat_cols = df[feature_cols].select_dtypes(include=["object", "category"]).columns.tolist()
    if cat_cols:
        df_encoded = pd.get_dummies(df[feature_cols], columns=cat_cols, drop_first=True)
    else:
        df_encoded = df[feature_cols].copy()

    # 3. Chronological date-based split
    if "date" in df.columns:
        unique_dates = df["date"].drop_duplicates().sort_values().values
        split_idx = int(len(unique_dates) * split_ratio)
        split_date = unique_dates[split_idx]

        train_mask = df["date"] < split_date
        test_mask = df["date"] >= split_date
    else:
        split_idx = int(len(df) * split_ratio)
        train_mask = df.index < split_idx
        test_mask = df.index >= split_idx

    X_train = df_encoded.loc[train_mask].copy()
    y_train = df.loc[train_mask, target].values

    X_test = df_encoded.loc[test_mask].copy()
    y_test = df.loc[test_mask, target].values

    return X_train, X_test, y_train, y_test
