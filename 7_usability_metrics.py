"""
STEP 7 — Usability metric: reviewer time per validated issue

The brief names this exact metric for the Registry & Readiness lane, and requires tail
results (90th/95th percentile), not just an average. This computes both from the real
timestamps already logged every time someone clicks Confirm/False Positive in the dashboard.

Run this AFTER you've reviewed at least a handful of records in the dashboard — the more
real reviews logged, the more meaningful this number is. 15-20 clicks is enough for a
reasonable sample.
"""

import pandas as pd

LOG_PATH = "data/reviewer_decisions.csv"

df = pd.read_csv(LOG_PATH)
df["reviewed_at"] = pd.to_datetime(df["reviewed_at"])
df = df.sort_values("reviewed_at").reset_index(drop=True)

if len(df) < 2:
    print("Not enough reviewed records yet — review at least a few more in the dashboard, then rerun.")
else:
    # Time between consecutive review actions = time spent per record
    deltas_seconds = df["reviewed_at"].diff().dt.total_seconds().dropna()

    median_time = deltas_seconds.median()
    p90_time = deltas_seconds.quantile(0.90)
    p95_time = deltas_seconds.quantile(0.95)
    mean_time = deltas_seconds.mean()

    print("=" * 60)
    print("USABILITY METRIC: reviewer time per validated issue")
    print("=" * 60)
    print(f"Records reviewed so far: {len(df)}")
    print(f"Mean time per review:    {mean_time:.1f} sec")
    print(f"Median time per review:  {median_time:.1f} sec")
    print(f"p90 time per review:     {p90_time:.1f} sec")
    print(f"p95 time per review:     {p95_time:.1f} sec")
    print("=" * 60)
    print("\nCopy these numbers into REPORT.md's evaluation section.")