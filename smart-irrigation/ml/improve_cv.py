import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

BASE = ["days_after_sowing","soil_moisture_0600","soil_moisture_change_24h","temperature_0600","humidity_0600",
        "rain_prev24h_mm","rain_forecast_next24h_mm","irrigation_prev7d_mm","days_since_irrigation"]
CAT = ["crop_type","soil_type","irrigation_type","growth_stage"]
df = pd.read_csv("irrigation_dataset_cleaned.csv", parse_dates=["date"])
df = df.rename(columns={"nfield_id": "field_id"})
df = df.sort_values(["field_id","date"]).reset_index(drop=True)

# candidate features built ONLY from past information
g = df.groupby("field_id")
df["rain_3d"] = g.rain_prev24h_mm.transform(lambda s: s.rolling(3, min_periods=1).sum())
df["moist_3d_mean"] = g.soil_moisture_0600.transform(lambda s: s.rolling(3, min_periods=1).mean())
df["moist_trend_3d"] = (df.soil_moisture_0600 - g.soil_moisture_0600.shift(3)).fillna(0)

SETS = {
  "A. base": BASE,
  "C. base + 3-day rain and moisture features": BASE + ["rain_3d","moist_3d_mean","moist_trend_3d"],
}

df = df.sort_values("date").reset_index(drop=True)
dates = np.sort(df.date.unique()); cut = dates[int(len(dates)*0.8)]
tr = df[df.date < cut].reset_index(drop=True)          # TRAINING DAYS ONLY
tdates = np.sort(tr.date.unique())
folds = [(tr.date.isin(tdates[a]).values, tr.date.isin(tdates[b]).values) for a, b in TimeSeriesSplit(n_splits=5).split(tdates)]

def X_of(a, cols, ref=None):
    X = pd.get_dummies(a[cols + CAT], columns=CAT); return X if ref is None else X.reindex(columns=ref, fill_value=0)

def score(y, p):
    p = np.clip(p, 0, None)
    return mean_absolute_error(y,p), np.sqrt(mean_squared_error(y,p)), r2_score(y,p)

rows = []
for name, cols in SETS.items():
    R = {"Random Forest": [], "Gradient Boosting": [], "Hurdle expected value": []}
    for ia, ib in folds:
        Xa = X_of(tr[ia], cols); Xb = X_of(tr[ib], cols, Xa.columns); ya, yb = tr.irrigation_mm[ia], tr.irrigation_mm[ib]
        R["Random Forest"].append(score(yb, RandomForestRegressor(n_estimators=200, max_depth=10, min_samples_leaf=5, random_state=42, n_jobs=-1).fit(Xa, ya).predict(Xb)))
        R["Gradient Boosting"].append(score(yb, GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, max_depth=3, random_state=42).fit(Xa, ya).predict(Xb)))
        clf = GradientBoostingClassifier(n_estimators=150, learning_rate=0.05, max_depth=3, random_state=42).fit(Xa, ya>0)
        reg = GradientBoostingRegressor(n_estimators=150, learning_rate=0.05, max_depth=3, random_state=42).fit(Xa[ya>0], ya[ya>0])
        R["Hurdle expected value"].append(score(yb, clf.predict_proba(Xb)[:,1] * reg.predict(Xb)))
    for m, v in R.items():
        v = np.array(v); rows.append([name, m, v[:,0].mean(), v[:,1].mean(), v[:,1].std(), v[:,2].mean()])
out = pd.DataFrame(rows, columns=["Feature set","Model","CV MAE","CV RMSE","RMSE std","CV R2"]).round(3)
print(out.to_string(index=False))
