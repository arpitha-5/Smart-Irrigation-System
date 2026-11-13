#AI-Powered Smart Irrigation System for Predictive Water Management and Crop Optimization
import pandas as pd

df = pd.read_csv("irrigation_dataset.csv", parse_dates=["date"])
df = df.sort_values(["field_id", "date"]).reset_index(drop=True)

print("Nulls before:")
print(df.isnull().sum()[lambda s: s > 0])

df["soil_moisture_0600"] = (
    df.groupby("field_id")["soil_moisture_0600"]
      .transform(lambda s: s.interpolate(limit_direction="both"))
)

calc = df.groupby("field_id")["soil_moisture_0600"].diff().round(2)
df["soil_moisture_change_24h"] = df["soil_moisture_change_24h"].fillna(calc)
df["soil_moisture_change_24h"] = df["soil_moisture_change_24h"].fillna(0)

print("Nulls after:", int(df.isnull().sum().sum()))
df.to_csv("irrigation_dataset_cleaned.csv", index=False)
print("Saved: irrigation_dataset_cleaned.csv")