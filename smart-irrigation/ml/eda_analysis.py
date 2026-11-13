import numpy as np
import pandas as pd

df = pd.read_csv("irrigation_dataset_cleaned.csv", parse_dates=["date"])
ID = df.columns[0]   # first column = field id (check its name in the output)

print("=== 1. Shape, columns, types ===")
print("Shape:", df.shape)
print("First column name:", ID)
print(df.dtypes.to_string())

print("\n=== 2. Missing values and duplicates ===")
print("Total nulls:", int(df.isnull().sum().sum()))
print("Duplicate rows:", int(df.duplicated().sum()))
print("Duplicate (field, date) pairs:", int(df.duplicated([ID, "date"]).sum()))
print("Rows per field (min, max):", df.groupby(ID).size().min(), df.groupby(ID).size().max())

print("\n=== 3. Impossible or inconsistent values ===")
print("humidity > 100:", int((df.humidity_0600 > 100).sum()))
print("negative rain values:", int((df.rain_prev24h_mm < 0).sum() + (df.rain_forecast_next24h_mm < 0).sum()))
print("irrigate_today disagrees with irrigation_mm > 0:", int(((df.irrigate_today == 1) != (df.irrigation_mm > 0)).sum()))
print("days_since_irrigation == 99 (placeholder):", int((df.days_since_irrigation == 99).sum()))

print("\n=== 4. Outliers (IQR rule) - investigate, do not auto-delete ===")
num = df.select_dtypes("number").drop(columns=["irrigate_today"])
for c in num.columns:
    q1, q3 = num[c].quantile([0.25, 0.75])
    n = int(((num[c] < q1 - 1.5 * (q3 - q1)) | (num[c] > q3 + 1.5 * (q3 - q1))).sum())
    print(f"{c:28s} {n:5d} flagged")

print("\n=== 5. Target: irrigation_mm ===")
print(df.irrigation_mm.describe().round(2).to_string())
print("Share of zero days: %.1f%%" % ((df.irrigation_mm == 0).mean() * 100))
print("Skewness: %.2f" % df.irrigation_mm.skew())
print("\nShare of days irrigated, by crop:")
print((df.groupby("crop_type").irrigation_mm.apply(lambda s: (s > 0).mean()) * 100).round(1).to_string())

print("\n=== 6. Correlation with target (numeric features) ===")
feat = ["days_after_sowing", "soil_moisture_0600", "soil_moisture_change_24h", "temperature_0600",
        "humidity_0600", "rain_prev24h_mm", "rain_forecast_next24h_mm",
        "irrigation_prev7d_mm", "days_since_irrigation"]
print(df[feat + ["irrigation_mm"]].corr()["irrigation_mm"].drop("irrigation_mm").round(3).to_string())

print("\n=== 7. Multicollinearity (VIF; above 5 to 10 = high) ===")
Z = (df[feat] - df[feat].mean()) / df[feat].std()
vif = np.diag(np.linalg.inv(Z.corr().values))
print(pd.Series(vif, index=feat).round(2).to_string())
