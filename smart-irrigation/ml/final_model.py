import json, os, joblib, warnings
import numpy as np, pandas as pd, matplotlib
warnings.filterwarnings("ignore")
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE = ["days_after_sowing","soil_moisture_0600","soil_moisture_change_24h","temperature_0600","humidity_0600",
        "rain_prev24h_mm","rain_forecast_next24h_mm","irrigation_prev7d_mm","days_since_irrigation"]
EXTRA = ["rain_3d","moist_3d_mean","moist_trend_3d"]      # built from past days only
CAT = ["crop_type","soil_type","irrigation_type","growth_stage"]
TARGET = "irrigation_mm"

df = pd.read_csv("irrigation_dataset_cleaned.csv", parse_dates=["date"]).rename(columns={"nfield_id": "field_id"})
df = df.sort_values(["field_id","date"]).reset_index(drop=True)
g = df.groupby("field_id")
df["rain_3d"] = g.rain_prev24h_mm.transform(lambda s: s.rolling(3, min_periods=1).sum())
df["moist_3d_mean"] = g.soil_moisture_0600.transform(lambda s: s.rolling(3, min_periods=1).mean())
df["moist_trend_3d"] = (df.soil_moisture_0600 - g.soil_moisture_0600.shift(3)).fillna(0)

# Chronological split: last 20% of days = test (used ONCE, at the end)
df = df.sort_values("date").reset_index(drop=True)
dates = np.sort(df.date.unique()); cut = dates[int(len(dates) * 0.8)]
train, test = df[df.date < cut], df[df.date >= cut]
Xtr = pd.get_dummies(train[BASE + EXTRA + CAT], columns=CAT)
Xte = pd.get_dummies(test[BASE + EXTRA + CAT], columns=CAT).reindex(columns=Xtr.columns, fill_value=0)
ytr, yte = train[TARGET], test[TARGET]
print(f"Train rows {len(Xtr)} | Test rows {len(Xte)} | Features {Xtr.shape[1]}")

# Chosen BEFORE looking at test results: best CV RMSE = two-stage model with expected-value prediction
clf = GradientBoostingClassifier(n_estimators=150, learning_rate=0.05, max_depth=3, random_state=42).fit(Xtr, ytr > 0)
reg = GradientBoostingRegressor(n_estimators=150, learning_rate=0.05, max_depth=3, random_state=42).fit(Xtr[ytr > 0], ytr[ytr > 0])
def hurdle_predict(X):
    return np.clip(clf.predict_proba(X)[:, 1] * reg.predict(X), 0, None)

rf = RandomForestRegressor(n_estimators=200, max_depth=10, min_samples_leaf=5, random_state=42, n_jobs=-1).fit(Xtr, ytr)
gb = GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, max_depth=3, random_state=42).fit(Xtr, ytr)

def met(y, p):
    return {"MAE": round(float(mean_absolute_error(y, p)), 3),
            "RMSE": round(float(np.sqrt(mean_squared_error(y, p))), 3),
            "R2": round(float(r2_score(y, p)), 3)}

pred = {"two_stage_expected_value (chosen)": hurdle_predict(Xte),
        "random_forest": np.clip(rf.predict(Xte), 0, None),
        "gradient_boosting": np.clip(gb.predict(Xte), 0, None),
        "baseline_zero": np.zeros(len(yte)),
        "baseline_train_mean": np.full(len(yte), ytr.mean())}
results = {k: met(yte, v) for k, v in pred.items()}
print(f"\n{'Model (TEST, scored once)':36s} {'MAE':>7s} {'RMSE':>8s} {'R2':>7s}")
for k, m in results.items():
    print(f"{k:36s} {m['MAE']:7.3f} {m['RMSE']:8.3f} {m['R2']:7.3f}")

tr_m = met(ytr, hurdle_predict(Xtr))
print("\nChosen model on TRAINING rows (overfitting check):", tr_m)

p = pred["two_stage_expected_value (chosen)"]; nz = yte.values > 0; r = yte.values - p
print(f"MAE on zero days {np.abs(r[~nz]).mean():.2f} mm | MAE on irrigation days {np.abs(r[nz]).mean():.2f} mm")
print(f"Mean residual on zero days {r[~nz].mean():+.2f} | on irrigation days {r[nz].mean():+.2f}")

os.makedirs("models", exist_ok=True); os.makedirs("reports", exist_ok=True)
joblib.dump({"type": "two_stage_expected_value", "classifier": clf, "regressor": reg,
             "columns": list(Xtr.columns)}, "models/irrigation_model_v2.joblib")
with open("reports/final_metrics.json", "w") as f:
    json.dump({"train_rows": len(Xtr), "test_rows": len(Xte), "n_features": int(Xtr.shape[1]),
               "chosen_by": "time-ordered cross-validation on training days",
               "test_metrics_scored_once": results, "chosen_train_metrics": tr_m}, f, indent=2)
fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
ax[0].scatter(yte, p, s=12, alpha=.5); ax[0].plot([0, 100], [0, 100], "r--"); ax[0].set_xlabel("actual mm"); ax[0].set_ylabel("predicted mm"); ax[0].set_title("Actual vs predicted (test)")
ax[1].scatter(p, r, s=12, alpha=.5); ax[1].axhline(0, color="r", ls="--"); ax[1].set_xlabel("predicted mm"); ax[1].set_ylabel("actual - predicted"); ax[1].set_title("Residuals (test)")
plt.tight_layout(); plt.savefig("reports/final_residuals.png", dpi=110)
print("\nSaved: models/irrigation_model_v2.joblib, reports/final_metrics.json, reports/final_residuals.png")

# ---- uncertainty of the test scores (resample test days, 1000 times) ----
rng = np.random.default_rng(0)
tday = test.date.values; udays = np.unique(tday)
idx_by_day = {d: np.where(tday == d)[0] for d in udays}
def boot(model_pred):
    out = []
    for _ in range(1000):
        pick = rng.choice(udays, size=len(udays), replace=True)
        ii = np.concatenate([idx_by_day[d] for d in pick])
        out.append(np.sqrt(mean_squared_error(yte.values[ii], model_pred[ii])))
    return np.percentile(out, [2.5, 97.5])
print("\n95% interval of test RMSE (resampling test days):")
for k in ["two_stage_expected_value (chosen)", "random_forest", "gradient_boosting", "baseline_zero"]:
    lo, hi = boot(pred[k]); print(f"  {k:36s} {lo:6.2f} to {hi:6.2f}")
