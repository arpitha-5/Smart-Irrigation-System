import os
import joblib
import numpy as np
from sklearn.ensemble import (
    RandomForestRegressor,
    GradientBoostingRegressor,
    GradientBoostingClassifier,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from data_utils import load_split, TwoStageIrrigationModel

# 1. Load data
X_train, X_test, y_train, y_test = load_split()
print("Train rows:", len(X_train), "| Test rows:", len(X_test),
      "| Features:", X_train.shape[1])

# 2. Define models
models = {
    "random_forest": RandomForestRegressor(
        n_estimators=200, max_depth=10, min_samples_leaf=5, random_state=42, n_jobs=-1
    ),
    "gradient_boosting": GradientBoostingRegressor(
        n_estimators=200, learning_rate=0.05, max_depth=3, random_state=42
    ),
    "two_stage_hurdle": TwoStageIrrigationModel(
        classifier=GradientBoostingClassifier(
            n_estimators=150, learning_rate=0.05, max_depth=3, random_state=42
        ),
        regressor=GradientBoostingRegressor(
            n_estimators=150, learning_rate=0.05, max_depth=3, random_state=42
        ),
        threshold=0.45,
        mode="hurdle"
    ),
    "two_stage_expected_value": TwoStageIrrigationModel(
        classifier=GradientBoostingClassifier(
            n_estimators=150, learning_rate=0.05, max_depth=3, random_state=42
        ),
        regressor=GradientBoostingRegressor(
            n_estimators=150, learning_rate=0.05, max_depth=3, random_state=42
        ),
        mode="expected_value"
    ),
}

# 3. Train, Evaluate & Save
os.makedirs("models", exist_ok=True)
best_rmse = float("inf")
best_model_name = None

print("\n--- Model Evaluation on Test Set ---")
print(f"{'Model':<26} {'MAE (mm)':<12} {'RMSE (mm)':<12} {'R2':<10}")
print("-" * 62)

# Reference baseline (predicting zero)
base_zero_mae = mean_absolute_error(y_test, np.zeros_like(y_test))
base_zero_rmse = np.sqrt(mean_squared_error(y_test, np.zeros_like(y_test)))
base_zero_r2 = r2_score(y_test, np.zeros_like(y_test))
print(f"{'baseline_zero':<26} {base_zero_mae:<12.3f} {base_zero_rmse:<12.3f} {base_zero_r2:<10.3f}")

# Reference baseline (predicting train mean)
base_mean_mae = mean_absolute_error(y_test, np.full_like(y_test, y_train.mean()))
base_mean_rmse = np.sqrt(mean_squared_error(y_test, np.full_like(y_test, y_train.mean())))
base_mean_r2 = r2_score(y_test, np.full_like(y_test, y_train.mean()))
print(f"{'baseline_mean':<26} {base_mean_mae:<12.3f} {base_mean_rmse:<12.3f} {base_mean_r2:<10.3f}")

for name, model in models.items():
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print(f"{name:<26} {mae:<12.3f} {rmse:<12.3f} {r2:<10.3f}")

    # Save model in exact format expected by your project
    joblib.dump({"model": model, "columns": list(X_train.columns)}, f"models/{name}.joblib")

    # Track best model by RMSE
    if rmse < best_rmse:
        best_rmse = rmse
        best_model_name = name

# Save the winning model as models/irrigation_model.joblib
best_payload = {"model": models[best_model_name], "columns": list(X_train.columns)}
joblib.dump(best_payload, "models/irrigation_model.joblib")

print("-" * 62)
print(f"[SUCCESS] Best model is '{best_model_name}' (RMSE: {best_rmse:.3f} mm).")
print(f"[SUCCESS] Saved to 'models/irrigation_model.joblib'.")
