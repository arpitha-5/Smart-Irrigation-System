# Verified Model Evaluation Report: Irrigation Water Quantity

## 1. Objective & Target Verification
- **Prediction Target:** Daily field irrigation depth (`irrigation_mm`).
- **Verified Unit:** **Millimetres (mm)** (1 mm = 10 m³/ha = 1 litre/m²).
- **Target Distribution:** Mean = 4.02 mm, Median = 0.00 mm, Max = 95.53 mm.
- **Zero-Inflation:** 90.7% zeros in training set, 90.5% zeros in test set.

## 2. Leakage-Free Chronological Split
- **Training Set:** First 80% of calendar dates (2025-06-19 to 2026-01-29), 2462 rows.
- **Test Set:** Last 20% of calendar dates (2026-01-30 to 2026-03-24), 346 rows.
- **Feature Set:** 21 features (categorical one-hot encoded, sentinel `99` corrected).
- **Leakage Guards:** Strict exclusion of target leakers (`irrigate_today`) and spatial identifiers (`field_id`/`nfield_id`).

## 3. Verified Evaluation Results on Held-out Test Set
| Model | MAE (mm) | RMSE (mm) | R² | MAE (Zero Days) | MAE (Active Days) |
|---|---|---|---|---|---|
| baseline_zero | 6.516 | 21.508 | -0.101 | 0.0 | 68.317 |
| baseline_mean | 9.483 | 20.694 | -0.019 | 3.667 | 64.65 |
| random_forest | 8.742 | 16.708 | 0.336 | 4.976 | 44.46 |
| gradient_boosting | 8.169 | 16.127 | 0.381 | 4.658 | 41.471 |
| two_stage_hurdle | 6.114 | 20.183 | 0.03 | 1.724 | 47.753 |
| two_stage_expected_value | 7.389 | 16.38 | 0.361 | 3.562 | 43.687 |

## 4. Cross-Validation Results (5 Time-Ordered Folds on Training Days)
| Model | CV MAE (mm) | CV RMSE (mm) | RMSE std | CV R² | R² std |
|---|---|---|---|---|---|
| random_forest | 4.563 | 11.682 | 4.214 | 0.211 | 0.166 |
| gradient_boosting | 5.788 | 12.089 | 3.479 | 0.138 | 0.036 |
| two_stage_hurdle | 3.277 | 12.632 | 4.051 | 0.069 | 0.09 |
| two_stage_expected_value | 4.123 | 11.602 | 3.819 | 0.215 | 0.119 |

## 5. Architectural Trade-Off Analysis
1. **The MAE vs RMSE Paradox:**
   - Single-stage models (Gradient Boosting, Random Forest) predict continuous expectations ($2 - 8\text{ mm}$) on zero days, accumulating MAE.
   - The Two-Stage Hurdle model with hard thresholding beats `baseline_zero` on MAE (6.114 mm), but incurs squared-error penalties when borderline active days are missed, raising RMSE.
   - The Two-Stage Expected Value formulation ($P(\text{irrigate}) \times \text{amount}$) achieves an optimal compromise by smoothing borderline predictions.

## 6. Selected Production Model
- **Selected Model:** **`gradient_boosting`** (Saved to `models/irrigation_model.joblib`).
- **Justification:** Demonstrates superior variance explanation ($R^2$) and minimal large-error exposure (lowest RMSE) on unseen future days.
- **Diagnostic Visualizations:** Saved to `reports/residuals_diagnostic.png`.
