"""Two small linked CSVs for the relationship-discovery chapter:
purchases.customer_id -> customers.customer_id, referentially intact."""

import csv
import sys
from pathlib import Path

out = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
out.mkdir(parents=True, exist_ok=True)

with (out / "customers.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["customer_id", "name", "region"])
    for i in range(1, 21):
        w.writerow([i, f"Customer {i}", ["North", "South", "East", "West"][i % 4]])

with (out / "purchases.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["purchase_id", "customer_id", "amount", "purchased_on"])
    for i in range(1, 81):
        w.writerow(
            [
                1000 + i,
                (i % 20) + 1,
                round(20 + (i * 7.3) % 500, 2),
                f"2026-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}",
            ]
        )

print("wrote customers.csv + purchases.csv")
