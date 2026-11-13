import json
import pandas as pd

with open("reports/model_metrics.json") as f:
    r = json.load(f)

df = pd.read_csv("irrigation_dataset_cleaned.csv", parse_dates=["date"])
zero_pct = (df["irrigation_mm"] == 0).mean() * 100
m = r["metrics_on_test"]
best = r["best_model"]

rows = ""
for name, v in m.items():
    rows += f"| {name} | {v['MAE']} | {v['RMSE']} | {v['R2']} |\n"

report = f"""# Model Evaluation Report: Irrigation Water Quantity

## 1. Objective
Predict the irrigation water quantity (`irrigation_mm`, in millimetres) for a field on a given day.

## 2. Dataset
- File: `irrigation_dataset_cleaned.csv`
- Size: {len(df)} rows, {df.shape[1]} columns, 24 fields
- Date range: {df['date'].min().date()} to {df['date'].max().date()}
- Target: `irrigation_mm` (mean {df['irrigation_mm'].mean():.2f} mm, max {df['irrigation_mm'].max():.2f} mm)
- {zero_pct:.1f}% of rows have `irrigation_mm = 0` (no irrigation that day)

## 3. Features
- Numeric: days_after_sowing, soil_moisture_0600, soil_moisture_change_24h, temperature_0600, humidity_0600, rain_prev24h_mm, rain_forecast_next24h_mm, irrigation_prev7d_mm, days_since_irrigation
- Categorical (one-hot encoded): crop_type, soil_type, irrigation_type, growth_stage
- Excluded: `irrigate_today` (leaks the target, it is 1 exactly when irrigation_mm > 0), `field_id` (identifier), `date` (used only for splitting)
- Total model features after encoding: {r['n_features']}

## 4. Method
- Split by date to avoid using future data: first 80% of days for training ({r['train_rows']} rows), last 20% for testing ({r['test_rows']} rows)
- Baselines: predict the training mean, and always predict zero
- Models: RandomForestRegressor (200 trees) and GradientBoostingRegressor (200 trees, learning rate 0.05, max depth 3)
- Metrics on the held-out test set: MAE, RMSE, R2

## 5. Results (test set)
| Model | MAE (mm) | RMSE (mm) | R2 |
|---|---|---|---|
{rows}
## 6. Model selection
The selected model is **{best}**, chosen because it has the lowest RMSE ({m[best]['RMSE']} mm) and the highest R2 ({m[best]['R2']}) among the trained models. It is saved as `models/irrigation_model.joblib`.

## 7. Limitations
- Irrigation is zero on most days, so the data is highly imbalanced. A model that always predicts zero has a low MAE ({m['baseline_zero']['MAE']} mm), which is hard to beat on MAE alone.
- R2 of {m[best]['R2']} means the model explains only part of the variation in irrigation amounts.
- The training score was much higher than the test score for the Random Forest, which indicates overfitting.
- Roughly 106 soil moisture values were filled by interpolation, so they are estimates, not sensor readings.
- `days_since_irrigation = 99` is a placeholder for "never irrigated yet" and is treated as a numeric value.
- The test period covers only about two months, so results may not hold for other seasons.

## 8. Possible improvements
- Two-stage model: first predict whether irrigation is needed, then predict how much.
- Tune hyperparameters and test more models.
- Add more seasons of data.
"""

with open("reports/model_evaluation.md", "w", encoding="utf-8") as f:
    f.write(report)
print("Saved: reports/model_evaluation.md")
