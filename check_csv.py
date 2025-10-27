import pandas as pd

# Read CSV
df = pd.read_csv('/Users/noice/Downloads/query_result_2025-10-10T00_34_01.722315Z.csv')

print(f"Total rows in CSV: {len(df)}")

# Check for invalid coordinates
invalid_coords = df[(df['partner_latitude'] == 0.0) & (df['partner_longitude'] == 0.0)]
print(f"\n❌ Orders with invalid coordinates (0,0): {len(invalid_coords)}")
if len(invalid_coords) > 0:
    print("\nInvalid orders:")
    for idx, row in invalid_coords.iterrows():
        print(f"  - {row['sale_order_id']}: {row['display_name']}")

# Check for missing coordinates
missing_coords = df[df['partner_latitude'].isna() | df['partner_longitude'].isna()]
print(f"\n❌ Orders with missing coordinates: {len(missing_coords)}")

# Valid orders
valid = df[~((df['partner_latitude'] == 0.0) & (df['partner_longitude'] == 0.0))]
valid = valid[~(valid['partner_latitude'].isna() | valid['partner_longitude'].isna())]
print(f"\n✅ Valid orders (with coordinates): {len(valid)}")

print(f"\n📊 Summary:")
print(f"   Total orders: {len(df)}")
print(f"   Valid: {len(valid)}")
print(f"   Invalid (0,0): {len(invalid_coords)}")
print(f"   Missing coords: {len(missing_coords)}")
print(f"   Expected output: {len(valid)} orders")
