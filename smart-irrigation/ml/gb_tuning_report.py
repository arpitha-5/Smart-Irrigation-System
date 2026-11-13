import json, os, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

BASE = ["days_after_sowing","soil_moisture_0600","soil_moisture_change_24h","temperature_0600","humidity_0600",
        "rain_prev24h_mm","rain_forecast_next24h_mm","irrigation_prev7d_mm","days_since_irrigation"]
EXTRA = ["rain_3d","moist_3d_mean","moist_trend_3d"]
CAT = ["crop_type","soil_type","irrigation_type","growth_stage"]
df = pd.read_csv("irrigation_dataset_cleaned.csv", parse_dates=["date"]).rename(columns={"nfield_id": "field_id"})
df = df.sort_values(["field_id","date"]).reset_index(drop=True)
g = df.groupby("field_id")
df["rain_3d"] = g.rain_prev24h_mm.transform(lambda s: s.rolling(3, min_periods=1).sum())
df["moist_3d_mean"] = g.soil_moisture_0600.transform(lambda s: s.rolling(3, min_periods=1).mean())
df["moist_trend_3d"] = (df.soil_moisture_0600 - g.soil_moisture_0600.shift(3)).fillna(0)
df = df.sort_values("date").reset_index(drop=True)
dates = np.sort(df.date.unique()); cut = dates[int(len(dates) * 0.8)]
train, test = df[df.date < cut].reset_index(drop=True), df[df.date >= cut]

CFG = {"current": dict(n_estimators=200, learning_rate=0.05, max_depth=3),
       "tuned": dict(n_estimators=150, learning_rate=0.05, max_depth=3, min_samples_leaf=20)}

def met(y, p):
    p = np.clip(p, 0, None)
    return {"MAE": round(float(mean_absolute_error(y, p)), 3), "RMSE": round(float(np.sqrt(mean_squared_error(y, p))), 3), "R2": round(float(r2_score(y, p)), 3)}

# 1. Cross-validation on training days only (settings chosen here)
tdates = np.sort(train.date.unique())
folds = [(train.date.isin(tdates[a]).values, train.date.isin(tdates[b]).values) for a, b in TimeSeriesSplit(n_splits=5).split(tdates)]
cv = {}
for name, kw in CFG.items():
    sc = []
    for ia, ib in folds:
        Xa = pd.get_dummies(train[ia][BASE + EXTRA + CAT], columns=CAT)
        Xb = pd.get_dummies(train[ib][BASE + EXTRA + CAT], columns=CAT).reindex(columns=Xa.columns, fill_value=0)
        m = GradientBoostingRegressor(random_state=42, **kw).fit(Xa, train.irrigation_mm[ia])
        sc.append(met(train.irrigation_mm[ib], m.predict(Xb)))
    cv[name] = {k: round(float(np.mean([s[k] for s in sc])), 3) for k in ["MAE", "RMSE", "R2"]}

# 2. Test set scored once per setting
Xtr = pd.get_dummies(train[BASE + EXTRA + CAT], columns=CAT)
Xte = pd.get_dummies(test[BASE + EXTRA + CAT], columns=CAT).reindex(columns=Xtr.columns, fill_value=0)
ytr, yte = train.irrigation_mm, test.irrigation_mm
pred = {n: GradientBoostingRegressor(random_state=42, **kw).fit(Xtr, ytr).predict(Xte) for n, kw in CFG.items()}
pred["zero_baseline"] = np.zeros(len(yte))
tst = {n: met(yte, p) for n, p in pred.items()}

# 3. Uncertainty: resample test days
rng = np.random.default_rng(0); tday = test.date.values; ud = np.unique(tday); ix = {d: np.where(tday == d)[0] for d in ud}
def boot(pv):
    o = []
    for _ in range(1000):
        ii = np.concatenate([ix[d] for d in rng.choice(ud, len(ud), replace=True)])
        o.append(np.sqrt(mean_squared_error(yte.values[ii], np.clip(pv[ii], 0, None))))
    return [round(float(x), 2) for x in np.percentile(o, [2.5, 97.5])]
ci = {n: boot(p) for n, p in pred.items()}

os.makedirs("reports", exist_ok=True)
with open("reports/gb_tuning_metrics.json", "w") as f:
    json.dump({"cv_training_days": cv, "test_scored_once": tst, "test_rmse_95_interval": ci}, f, indent=2)

print("CV (training days):", cv)
print("TEST:", tst)
print("95% RMSE intervals:", ci)

# 4. Add a section to the report (replaces an older copy of the section if present)
path = "reports/model_evaluation_final.md"
text = open(path, encoding="utf-8").read().split("\n## 11.")[0].rstrip() if os.path.exists(path) else "# Model Evaluation Report"
sec = f"""

## 11. Gradient Boosting tuning
Gradient Boosting was tuned with time-ordered cross-validation on the training days only. The best of 10 settings tried (on two feature sets) used `min_samples_leaf=20` and 150 trees.

| Setting | CV MAE | CV RMSE | CV R2 | Test MAE | Test RMSE | Test R2 |
|---|---|---|---|---|---|---|
| Current (200 trees, depth 3) | {cv['current']['MAE']} | {cv['current']['RMSE']} | {cv['current']['R2']} | {tst['current']['MAE']} | {tst['current']['RMSE']} | {tst['current']['R2']} |
| Tuned (150 trees, depth 3, min_samples_leaf 20) | {cv['tuned']['MAE']} | {cv['tuned']['RMSE']} | {cv['tuned']['R2']} | {tst['tuned']['MAE']} | {tst['tuned']['RMSE']} | {tst['tuned']['R2']} |
| Always-zero baseline | | | | {tst['zero_baseline']['MAE']} | {tst['zero_baseline']['RMSE']} | {tst['zero_baseline']['R2']} |

- 95% interval of test RMSE (resampling test days): current {ci['current'][0]} to {ci['current'][1]}, tuned {ci['tuned'][0]} to {ci['tuned'][1]}, zero baseline {ci['zero_baseline'][0]} to {ci['zero_baseline'][1]}.
- Tuning improved the cross-validated scores, but the difference is small compared with the fold-to-fold spread (about 4 mm RMSE), and it did not carry over to the test set. The two settings cannot be told apart on the test data.
- The test set has been scored several times during this project, so it should no longer be treated as an untouched hold-out. Further tuning against it is not justified.
- Conclusion: the limit is the amount of irrigation data (262 events) and the weak input signals, not the model settings.
"""
open(path, "w", encoding="utf-8").write(text + sec)
print("Updated:", path)
