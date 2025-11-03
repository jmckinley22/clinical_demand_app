from datetime import datetime
from clinical_demand import ProductParams, DosingParams, calculate_group_demand
import clinical_demand_app as app

# Build sample trials/groups programmatically
all_groups = []

# Trial 1: one group with two products
params1 = DosingParams(
    patients=10,
    products=[
        ProductParams(name="Alpha", product_amount=50.0, admin_points=1, days=28),
        ProductParams(name="Beta", product_amount=20.0, admin_points=2, days=14),
    ],
    buffer_pct=5,
)

total1, by_prod1 = calculate_group_demand(params1)
record1 = {**params1.__dict__, "demand_mg": int(round(total1)), "trial": 1, "trial_name": "Trial 1", "group": 1, "group_name": "Group 1", "product_breakdown": by_prod1}
all_groups.append(record1)

# Trial 2: two groups
params2a = DosingParams(
    patients=5,
    products=[ProductParams(name="Alpha", product_amount=50.0, admin_points=1, days=28)],
    buffer_pct=0,
)

params2b = DosingParams(
    patients=8,
    products=[ProductParams(name="Gamma", product_amount=100.0, admin_points=1, days=7)],
    buffer_pct=10,
)

total2a, by_prod2a = calculate_group_demand(params2a)
record2a = {**params2a.__dict__, "demand_mg": int(round(total2a)), "trial": 2, "trial_name": "Trial 2", "group": 1, "group_name": "Group A", "product_breakdown": by_prod2a}
all_groups.append(record2a)

total2b, by_prod2b = calculate_group_demand(params2b)
record2b = {**params2b.__dict__, "demand_mg": int(round(total2b)), "trial": 2, "trial_name": "Trial 2", "group": 2, "group_name": "Group B", "product_breakdown": by_prod2b}
all_groups.append(record2b)

# Compute aggregated product totals across all groups
product_totals = {}
for g in all_groups:
    pb = g.get("product_breakdown") or {}
    for pname, amt in pb.items():
        product_totals[pname] = product_totals.get(pname, 0.0) + amt

print("Computed product_totals:")
for k, v in sorted(product_totals.items()):
    print(f" - {k}: {int(round(v))} mg")

# Expand rows and generate CSV using the app helpers
expanded_rows, sanitized_map = app.expand_product_rows(all_groups)

# Append summary row similar to the app
if expanded_rows:
    keys = list(expanded_rows[0].keys())
    summary_row = {k: "" for k in keys}
    label_key = None
    for candidate in ("group_name", "trial_name", "group", "trial"):
        if candidate in summary_row:
            label_key = candidate
            break
    if label_key:
        summary_row[label_key] = "TOTAL"
    else:
        summary_row[keys[0]] = "TOTAL"
    for orig_name, san in sanitized_map.items():
        col = f"{san}_mg"
        amt = product_totals.get(orig_name, 0.0)
        summary_row[col] = int(round(amt)) if amt is not None else 0
    # total patients
    try:
        total_patients = sum(int(g.get("patients", 0)) for g in all_groups)
    except Exception:
        total_patients = 0
    if "patients" in summary_row:
        summary_row["patients"] = int(total_patients)
    expanded_rows.append(summary_row)

summary = {
    "Title": "Sample run",
    "GeneratedAtUTC": datetime.utcnow().isoformat(),
    "NumTrials": 2,
}

csv_content = app.format_csv(expanded_rows, summary=summary)

out_path = app.save_csv_to_disk(csv_content, filename="sample_test.csv")
print(f"Wrote sample CSV to: {out_path}")
print("\nCSV head:\n")
print('\n'.join(csv_content.splitlines()[:40]))
