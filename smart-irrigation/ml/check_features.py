import pandas as pd

df = pd.read_csv("irrigation_dataset_cleaned.csv")

print("Column names:")
print(df.columns.tolist())
print()

for col in ["crop_type", "soil_type", "irrigation_type", "growth_stage"]:
    print(col, "->", df[col].unique().tolist())

print()
print("date range:", df["date"].min(), "to", df["date"].max())
print("days_since_irrigation == 99:", (df["days_since_irrigation"] == 99).sum())