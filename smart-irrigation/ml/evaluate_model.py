import json
import os
import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from data_utils import load_split

X_train, X_test, y_train, y_test = load_split()


def scores(pred):
    return {
        "MAE": round(float(mean_absolute_error(y_test, pred)), 3),
        "RMSE": round(float(np.sqrt(mean_squared_error(y_test, pred))), 3),
        "R2": round(float(r2_score(y_test, pred)), 3),
    }


results = {
    "baseline_mean": scores(np.full(len(y_test), y_train.mean())),
    "baseline_zero": scores(np.zeros(len(y_test))),
}

for name in ["random_forest", "gradient_boosting"]:
    saved = joblib.load(f"models/{name}.joblib")
    pred = saved["model"].predict(X_test[saved["columns"]])
    results[name] = scores(pred)

print(f"{'Model':20s} {'MAE':>8s} {'RMSE':>8s} {'R2':>8s}")
for name, m in results.items():
    print(f"{name:20s} {m['MAE']:8.3f} {m['RMSE']:8.3f} {m['R2']:8.3f}")

# Choose the best real model by lowest RMSE
best = min(["random_forest", "gradient_boosting"], key=lambda n: results[n]["RMSE"])
print("\nBest model:", best)

os.makedirs("reports", exist_ok=True)
joblib.dump(joblib.load(f"models/{best}.joblib"), "models/irrigation_model.joblib")

output = {
    "train_rows": int(len(X_train)),
    "test_rows": int(len(X_test)),
    "n_features": int(X_train.shape[1]),
    "metrics_on_test": results,
    "best_model": best,
}
with open("reports/model_metrics.json", "w") as f:
    json.dump(output, f, indent=2)
print("Saved: models/irrigation_model.joblib and reports/model_metrics.json")
