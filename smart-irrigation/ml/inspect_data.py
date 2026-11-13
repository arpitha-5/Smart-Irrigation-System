import pandas as pd

df = pd.read_csv("irrigation_dataset_cleaned.csv")

print("Shape:", df.shape)
print()
print("Columns and types:")
print(df.dtypes)
print()
print("Nulls:", df.isnull().sum().sum())
print()
print("Target: irrigation_mm")
print(df["irrigation_mm"].describe())
print()
print("Rows with irrigation_mm = 0:", (df["irrigation_mm"] == 0).sum())
print("Rows with irrigation_mm > 0:", (df["irrigation_mm"] > 0).sum())