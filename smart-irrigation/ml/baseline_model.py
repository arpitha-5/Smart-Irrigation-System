import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

df = pd.read_csv("irrigation_dataset_cleaned.csv", parse_dates=["date"])
df = df.sort_values("date").reset_index(drop=True)

# Split by date: first 80% of days = train, last 20% of days = test
dates = np.sort(df["date"].unique())
cut_date = dates[int(len(dates) * 0.8)]
train = df[df["date"] < cut_date]
test = df[df["date"] >= cut_date]

print("Train rows:", len(train), "| Test rows:", len(test))
print("Train dates:", train["date"].min().date(), "to", train["date"].max().date())
print("Test dates: ", test["date"].min().date(), "to", test["date"].max().date())
print()

y_train = train["irrigation_mm"]
y_test = test["irrigation_mm"]

def show(name, pred):
    mae = mean_absolute_error(y_test, pred)
    rmse = np.sqrt(mean_squared_error(y_test, pred))
    r2 = r2_score(y_test, pred)
    print(f"{name:28s} MAE={mae:.3f}  RMSE={rmse:.3f}  R2={r2:.3f}")

show("Baseline 1: train mean", np.full(len(test), y_train.mean()))
show("Baseline 2: always zero", np.zeros(len(test)))