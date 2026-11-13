# ML irrigation model, scheduler and alerts (Milestone 2)

This document describes what the trained model predicts, how it was validated, how it plugs into the recommendation flow,
how emergency alerts and time-slot plans work, and what it can **not** do. Every number below is read from
`backend/models/irrigation/v1/evaluation_report.json`, produced by
`python scripts/train_irrigation_model.py`.

> **All training data is synthetic.** It comes from `scripts/generate_dataset.py` (a weather generator, FAO-56 style crop
> water use, a soil-water balance and a simulated farmer who irrigates by a noisy threshold rule). The metrics measure how
> well the model reproduces that simulator. They are **not** evidence of agronomic accuracy on real farms. Retrain and
> re-evaluate on real multi-season field data before relying on it.

## 1. What the model predicts

* **Target:** `irrigation_mm`, the *gross* depth of water applied on the day (net crop need divided by system efficiency).
  1 mm over 1 ha = 10,000 L. Because it is gross, the litres computed by the scheduler are the water to pump at the source.
  *(This definition came from the generator; confirm it with your ML/data teammates if real data defines it differently.)*
* **Structure ("hurdle"):** 90 % of field-days have no irrigation, so there are two models. A classifier estimates
  P(irrigate today); a regressor, trained only on irrigation days, estimates the depth. Recommended depth =
  regressor if P >= threshold, otherwise 0.
* **Selected model:** `gradient boosting` with decision threshold 0.55 (chosen by grouped cross-validation).
  Random Forest and Gradient Boosting were compared; the selection margin was tiny (see below), so treat them as equivalent.
* **Decision time:** trained on one decision per field-day at 06:00 local time. Calls at other times are approximations.

## 2. Features (all obtainable in the running system)

| Feature | Source in the live system |
|---|---|
| `soil_moisture` | latest sensor reading (volumetric %), or the manual value in the request |
| `soil_moisture_change_24h` | latest reading minus the reading about 24 h earlier (+/- 3 h); missing if none |
| `rain_forecast_next24h_mm` | weather adapter 24 h forecast; missing if the forecast is unavailable |
| `days_after_sowing` | today minus the crop record's `planting_date` |
| `kc`, `stage_idx` | derived from crop and days after sowing (`app/services/agro_params.py`) |
| `crop_rice`, `crop_maize`, `crop_cotton`, `crop_wheat` | crop type (one-hot) |

**Deliberately not used:** soil type, irrigation method and irrigation history. The dataset has them, but the `Field` model
does not store them. An ablation (grouped CV, 48 fields) showed that adding irrigation history to the runtime feature set gave
no benefit beyond the 24 h moisture trend, so no new database table was needed. Missing values are kept as missing, never
imputed with invented numbers; training hides the forecast for 15 % of rows so the model copes with weather-API downtime.

## 3. Validation protocol

1. 10 of 48 fields were held out and never used for fitting, model choice or the threshold.
2. On the other 38 fields, 5-fold cross-validation **grouped by field** compared the models and chose the threshold.
3. The chosen recipe was refit on the training fields and scored once on the held-out fields.
4. The shipped file is refit on all fields.

Grouping by field matters: consecutive days of one field are highly correlated, and a random row split would overstate accuracy.

### Cross-validation (training fields)

| Model | ROC-AUC | Precision | Recall | F1 | Depth MAE (mm) | Depth R² |
|---|---|---|---|---|---|---|
| random forest | 0.872 | 0.453 | 0.576 | 0.507 | 8.94 | 0.627 |
| gradient boosting | 0.805 | 0.489 | 0.532 | 0.510 | 8.86 | 0.623 |

### Held-out fields (final)

| Model | ROC-AUC | Precision | Recall | F1 | Depth MAE (mm) | Depth R² |
|---|---|---|---|---|---|---|
| random forest | 0.919 | 0.481 | 0.793 | 0.599 | 6.91 | 0.678 |
| gradient boosting (selected) | 0.930 | 0.457 | 0.757 | 0.570 | 7.79 | 0.592 |

Selection rule (fixed before looking at held-out results): best cross-validated F1, ties broken by ROC-AUC. Gradient Boosting
won by 0.0025 F1, which is noise-level; on the held-out fields Random Forest
scored slightly higher. With 111 irrigation days in the hold-out the differences are not statistically meaningful.

### Baselines

| Baseline | Result |
|---|---|
| Never irrigate | recall 0; looks good on overall MAE only because most days are dry |
| One global moisture trigger (irrigate below 21 %), crop mean depth | precision 0.220, recall 0.432, F1 0.292, depth MAE 6.78 mm |
| Mean depth only | depth MAE 14.81 mm |
| **Selected model (held-out)** | precision 0.457, recall 0.757, F1 0.570, depth MAE 7.79 mm |

### Robustness: forecast unavailable (selected model, held-out)

| | Precision | Recall | F1 | Depth MAE (mm) |
|---|---|---|---|---|
| Forecast available | 0.457 | 0.757 | 0.570 | 7.79 |
| Forecast unavailable | 0.385 | 0.739 | 0.506 | 6.92 |

### Per crop (selected model, held-out; crops with at least one irrigation day)

| Crop | Irrigation days | ROC-AUC | Precision | Recall | F1 | Depth MAE (mm) |
|---|---|---|---|---|---|---|
| cotton | 7 | 0.910 | 0.667 | 0.286 | 0.400 | 11.89 |
| maize | 16 | 0.845 | 0.125 | 0.250 | 0.167 | 10.76 |
| rice | 77 | 0.900 | 0.590 | 0.896 | 0.711 | 4.97 |
| wheat | 11 | 0.928 | 0.281 | 0.818 | 0.419 | 20.59 |

### How to read these results

* Recall of about 76% means most simulated irrigation days are caught. Precision of about 46% means that **roughly half of
  "irrigate" calls are false alarms** relative to the simulated farmer. The simulated farmer is itself noisy (random skipped days,
  imperfect forecasts), so part of this is irreducible.
* Crops differ a lot: rice is learned well; maize, wheat and cotton have very few irrigation days, so those results are unreliable.
* For a dry rice field the probability can fall just under the threshold when the forecast is missing; this is a known weakness.
* **LSTM:** the comparison code exists (`app/ml/lstm.py`, sequence building is unit-tested) but PyTorch was not installed where
  this was built, so **no LSTM result is reported**. Install `torch` and rerun the training script to include it.
* **MLflow:** tracking uses MLflow when it is installed, otherwise a local JSON registry (`models/registry.json`, `models/runs/`).
  The MLflow path was **not exercised** where this was built (MLflow not installed); the local path is tested.

## 4. How the model is used in a recommendation

`GET /recommendations/irrigation/{field_id}` and `POST /recommendations/irrigation` now do, for a registered field:

1. The existing rule-based engine runs unchanged (its `action` and `recommended_water_mm` stay in the response).
2. Sensor and crop context is read from the database. This does **not** depend on the weather call.
3. The ML model supplies the depth **only if** it can run: model loaded; crop is one of rice, maize, cotton, wheat; the latest crop record
   has a planting date; a soil-moisture reading no older than 24 h (or a manual `soil_moisture`) exists. Otherwise the rule-based
   depth is used and `ml_prediction.reason` says exactly why.
4. The weather-aware scheduler (`irrigation_scheduler`) decides IRRIGATE / DEFER / NO_IRRIGATION_NEEDED / WITHHELD. It never changes the depth.
5. Alerts are evaluated (section 5).
6. If the soil is critically dry (EMERGENCY alert) but the model advises no irrigation, the rule-based depth is used as a **safety net**
   (`schedule_input.source = "rule_based_emergency_override"`).
7. If the action is IRRIGATE, a time-slotted plan is produced (section 6).

**Final decision:** `irrigation_schedule.action`. `ml_prediction` shows what the model said; `schedule_input` shows which source supplied the depth.

New response fields (all optional): `ml_prediction`, `irrigation_plan`, `alerts`.
New endpoints: `GET /recommendations/irrigation-model` (status, version, metrics, limitations) and
`POST /recommendations/irrigation/ml-predict` (run the model on supplied features, no database).

## 5. Emergency alerts (rule-based, independent of the model)

Alerts are rules on purpose: they keep working when the model, forecast or weather API is unavailable. Thresholds come from the same crop
profile the existing engine already reports (`critical_threshold_pct`, `optimal_target_pct`) and are **proposals** for agronomist review.

| Code | Level | Condition |
|---|---|---|
| `DROUGHT_EMERGENCY` | EMERGENCY | soil moisture < 0.70 x critical threshold (0.85 x during flowering/fruiting), reading not stale, and no relieving rain |
| `DROUGHT_RISK` | WARNING | soil moisture < critical threshold (also used when an emergency is downgraded) |
| `OVERWATERING_RISK` | WARNING | soil moisture >= optimal target + 10 points |
| `SENSOR_STALE` | WARNING | latest reading older than 24 h (a stale reading is never an emergency) |
| `NO_SENSOR_DATA` | WARNING | no usable moisture value |
| `SCHEDULE_WITHHELD` / `IRRIGATION_DEFERRED` | INFO | scheduler could not decide / deferred for rain |

"Relieving rain" = rain observed in the last hour (scheduler reason `rain_in_last_hour`) or at least 10 mm forecast within 24 h; the emergency
is then downgraded to a warning with an explanation. Alerts only advise: nothing switches pumps or valves. Delivery channels (push, SMS,
email) are a later milestone; this stage only decides **what** to alert and shows it in the dashboard.

## 6. Time-slotted plan

* Duration = depth / application rate. The rate comes from the request (`application_rate_mm_per_hour`, or `irrigation_method` = drip 3,
  sprinkler 6, flood 15 mm/h, the generator's values). If neither is given, **6 mm/h is assumed and the plan says so** (`rate_assumed`).
* Normal plans use 05:00-09:00 and 17:00-20:00 local time, with sessions of at most 4 h, spread over up to 3 days if needed.
* Emergency plans start immediately (next 5 minutes) regardless of the hour, then continue in normal windows.
* Local time = UTC + `IRRIGATION_UTC_OFFSET_HOURS` (default 5.5); the field's real time zone is not stored.
* DEFER / NO_IRRIGATION_NEEDED / WITHHELD produce no slots (DEFER carries a re-evaluation time).

## 7. Limitations (read before trusting it)

1. **Synthetic training data**; see the banner above.
2. **Moisture scales may disagree.** The model was trained on moisture values from 13.03 % to 39.75 %.
   The existing rule engine uses different per-crop thresholds (for example rice critical ~45 %). A reading can therefore look "dry" to the
   alert rules and "fine" to the model. The emergency override errs on the side of watering, and out-of-range inputs raise a warning, but the two
   scales must be reconciled using real sensor calibration and soil data.
3. **Few crops** (rice, maize, cotton, wheat); others fall back to the rule engine.
4. A field needs a **crop record with a planting date**. `POST /fields` creates a crop record without one, so ML stays off until it is set.
5. Soil type and irrigation method are not stored, so depth and duration cannot be tailored to them.
6. Moderate precision (many false alarms) and weak results for crops with few irrigation days.
7. Model files are pickles (joblib) tied to a scikit-learn version; a mismatch is warned about, and a failed load falls back to the rule engine.
   Only load model files you trust.
8. The scheduler's plausibility ceiling is 100 mm per event; the training depths reach 97.73 mm.

## 8. Retraining

```bash
cd backend
python scripts/train_irrigation_model.py                          # generates synthetic data, trains, saves to models/irrigation/<version>
python scripts/train_irrigation_model.py --data path/to/irrigation_dataset.csv --version v2   # your own data, same columns
```
Writes `model.joblib`, `metadata.json`, `evaluation_report.json`, updates `models/irrigation/latest.txt`, and records the run (MLflow if installed,
else `models/registry.json`). Compare runs there as new seasonal data arrives.
