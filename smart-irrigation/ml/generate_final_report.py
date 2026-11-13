import json
import pandas as pd

with open("reports/final_metrics.json") as f:
    r = json.load(f)
df = pd.read_csv("irrigation_dataset_cleaned.csv", parse_dates=["date"])
zero_pct = (df["irrigation_mm"] == 0).mean() * 100
nz = df.loc[df["irrigation_mm"] > 0, "irrigation_mm"]
t = r["test_metrics_scored_once"]
tr = r["chosen_train_metrics"]

names = {"two_stage_expected_value (chosen)": "Two-stage, expected value (selected by CV)",
         "random_forest": "Random Forest", "gradient_boosting": "Gradient Boosting",
         "baseline_zero": "Baseline: always zero", "baseline_train_mean": "Baseline: training mean"}
rows = ""
for k, v in t.items():
    rows += "| " + names.get(k, k) + " | " + str(v["MAE"]) + " | " + str(v["RMSE"]) + " | " + str(v["R2"]) + " |\n"

report = f"""# Model Evaluation Report: Irrigation Water Quantity (Regression)

## 1. Objective
Predict `irrigation_mm`, the irrigation water amount for a field on a given day.
Unit note: the unit (millimetres) is inferred from the column name and is not documented in the dataset. It should be confirmed with the data owner.

## 2. Dataset
- File: `irrigation_dataset_cleaned.csv`, {len(df)} rows, 24 fields, {df['date'].min().date()} to {df['date'].max().date()}
- No missing values after cleaning (106 soil moisture values were filled by interpolation within each field, so they are estimates)
- No duplicate rows and no impossible values were found
- Target: {zero_pct:.1f}% of rows are 0 (no irrigation). The {len(nz)} irrigation events range from {nz.min():.1f} to {nz.max():.1f} mm (mean {nz.mean():.1f} mm)

## 3. Features
- 9 numeric inputs: days_after_sowing, soil_moisture_0600, soil_moisture_change_24h, temperature_0600, humidity_0600, rain_prev24h_mm, rain_forecast_next24h_mm, irrigation_prev7d_mm, days_since_irrigation
- 4 categorical inputs (one-hot encoded): crop_type, soil_type, irrigation_type, growth_stage
- 3 engineered inputs built from past days only: rain over the last 3 days, 3-day mean soil moisture, 3-day moisture trend
- Excluded: `irrigate_today` (it is 1 exactly when the target is above 0, so it would leak the answer), `field_id` (identifier), `date` (used only to split the data)
- Total model inputs after encoding: {r['n_features']}
- Verified checks: `days_since_irrigation` is never 0, and `irrigation_prev7d_mm` matches the previous 7 days excluding today in 98.1% of rows. Both appear to use past information only; how they are computed should be confirmed with the data source.

## 4. Method
- Chronological split: first 80% of days for training ({r['train_rows']} rows), last 20% for testing ({r['test_rows']} rows). No dates are shared.
- Models were compared and chosen with time-ordered cross-validation (5 folds) on the training days only.
- The test set was scored once, after the model was chosen.
- Random seed 42 everywhere.

## 5. Cross-validation results (training days only)
| Features | Model | CV RMSE (mm) | CV R2 |
|---|---|---|---|
| Base | Random Forest (depth 10, leaf 5) | 11.65 | 0.215 |
| Base | Gradient Boosting | 11.97 | 0.154 |
| Base | Two-stage, expected value | 11.60 | 0.214 |
| Base + 3-day rain and moisture | Random Forest | 11.56 | 0.229 |
| Base + 3-day rain and moisture | Gradient Boosting | 11.81 | 0.185 |
| Base + 3-day rain and moisture | **Two-stage, expected value** | **11.36** | **0.255** |

The spread of RMSE across folds is about 4 mm, so the differences between these models are small relative to the noise. A small tuning grid (depth, trees, learning rate) changed CV RMSE by less than 0.3 mm, so the original settings were kept.

## 6. Test results (scored once)
| Model | MAE (mm) | RMSE (mm) | R2 |
|---|---|---|---|
{rows}
- Selected model on the training rows: MAE {tr['MAE']}, RMSE {tr['RMSE']}, R2 {tr['R2']}. The gap to the test R2 shows overfitting.
- 95% intervals of test RMSE (resampling test days): selected model 13.56 to 20.48, Random Forest 13.90 to 20.15, Gradient Boosting 13.68 to 18.78, always-zero baseline 17.50 to 25.42.
- The test set contains only 33 irrigation days, and they are larger than in training (mean about 68 mm vs about 39 mm).

## 7. Model selection and interpretation
The two-stage expected-value model was selected because it had the best cross-validated RMSE and R2. On the test set the three models cannot be told apart (their RMSE intervals overlap heavily), and Gradient Boosting scored slightly better there. The choice was not changed after seeing test scores, to avoid selecting on the test set.
All models beat both baselines on RMSE and R2. The always-zero baseline has a low MAE because most days need no irrigation, so MAE alone is misleading for this target.

## 8. Limitations
- Only {len(nz)} irrigation events, and weak links between inputs and the amount (strongest correlation about -0.19), so predictions explain only part of the variation.
- Large irrigation events are under-predicted and small amounts are predicted on many zero days.
- The test period is short and has larger events than training, so test scores are noisy and may not represent other seasons.
- The unit (mm) is unconfirmed. Some values look unusual (median Drip events are larger than Flood events), which should be checked with the data owner.
- Interpolated moisture values used neighbouring days on both sides, a small leakage risk.

## 9. Recommendations
- Collect more seasons and more irrigation events.
- Add inputs such as evapotranspiration, soil water capacity and crop coefficients.
- Confirm the unit and the way past-irrigation features are computed.

## 10. Saving and reusing the model
The model is saved as `models/irrigation_model_v2.joblib` (a dictionary with the classifier, the regressor and the column list).

    import joblib, numpy as np
    saved = joblib.load("models/irrigation_model_v2.joblib")
    # X: a DataFrame with the same inputs, one-hot encoded for the 4 categorical columns
    X = X.reindex(columns=saved["columns"], fill_value=0)
    p = saved["classifier"].predict_proba(X)[:, 1]
    amount = saved["regressor"].predict(X)
    prediction_mm = np.clip(p * amount, 0, None)
"""
with open("reports/model_evaluation_final.md", "w", encoding="utf-8") as f:
    f.write(report)
print("Saved: reports/model_evaluation_final.md")
