import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED = 42
NUMERIC = ["days_after_sowing", "soil_moisture_0600", "soil_moisture_change_24h",
           "temperature_0600", "humidity_0600", "rain_prev24h_mm",
           "rain_forecast_next24h_mm", "irrigation_prev7d_mm", "days_since_irrigation"]
CATEGORY = ["crop_type", "soil_type", "irrigation_type", "growth_stage"]
TARGET = "irrigation_mm"

df = pd.read_csv("irrigation_dataset_cleaned.csv", parse_dates=["date"])
df = df.sort_values("date").reset_index(drop=True)

# Same date-based split as before: the last 20% of days are the locked test set
dates = np.sort(df["date"].unique())
cut = dates[int(len(dates) * 0.8)]
train = df[df["date"] < cut].reset_index(drop=True)
print("Training rows:", len(train), "| Test rows (NOT used here):", int((df["date"] >= cut).sum()))


def make_pipe(model, scale):
    num = StandardScaler() if scale else "passthrough"
    pre = ColumnTransformer([("num", num, NUMERIC),
                             ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORY)])
    return Pipeline([("prep", pre), ("model", model)])


candidates = {
    "Linear Regression": make_pipe(LinearRegression(), True),
    "Ridge (alpha=1)": make_pipe(Ridge(alpha=1.0), True),
    "Lasso (alpha=0.1)": make_pipe(Lasso(alpha=0.1, max_iter=10000), True),
    "Random Forest": make_pipe(RandomForestRegressor(n_estimators=200, random_state=SEED, n_jobs=-1), False),
    "Gradient Boosting": make_pipe(GradientBoostingRegressor(n_estimators=200, learning_rate=0.05,
                                                             max_depth=3, random_state=SEED), False),
}

# Time-ordered cross-validation on TRAINING days only (each fold tests on later days)
train_dates = np.sort(train["date"].unique())
folds = []
for tr_i, va_i in TimeSeriesSplit(n_splits=5).split(train_dates):
    tr_mask = train["date"].isin(train_dates[tr_i])
    va_mask = train["date"].isin(train_dates[va_i])
    folds.append((np.where(tr_mask)[0], np.where(va_mask)[0]))

X, y = train[NUMERIC + CATEGORY], train[TARGET]
rows = []
for name, pipe in candidates.items():
    mae, rmse, r2 = [], [], []
    for tr_idx, va_idx in folds:
        pipe.fit(X.iloc[tr_idx], y.iloc[tr_idx])
        p = pipe.predict(X.iloc[va_idx])
        mae.append(mean_absolute_error(y.iloc[va_idx], p))
        rmse.append(np.sqrt(mean_squared_error(y.iloc[va_idx], p)))
        r2.append(r2_score(y.iloc[va_idx], p))
    rows.append([name, np.mean(mae), np.mean(rmse), np.std(rmse), np.mean(r2), np.std(r2)])

# Baselines per fold (mean of earlier days / always zero)
for label, fn in [("Baseline: train mean", lambda ytr, n: np.full(n, ytr.mean())),
                  ("Baseline: always zero", lambda ytr, n: np.zeros(n))]:
    mae, rmse, r2 = [], [], []
    for tr_idx, va_idx in folds:
        p = fn(y.iloc[tr_idx], len(va_idx))
        mae.append(mean_absolute_error(y.iloc[va_idx], p))
        rmse.append(np.sqrt(mean_squared_error(y.iloc[va_idx], p)))
        r2.append(r2_score(y.iloc[va_idx], p))
    rows.append([label, np.mean(mae), np.mean(rmse), np.std(rmse), np.mean(r2), np.std(r2)])

res = pd.DataFrame(rows, columns=["Model", "CV MAE", "CV RMSE", "RMSE std", "CV R2", "R2 std"]).round(3)
print("\nCross-validation on training days only (5 time-ordered folds):")
print(res.sort_values("CV RMSE").to_string(index=False))
