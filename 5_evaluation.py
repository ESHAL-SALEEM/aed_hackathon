"""
STEP 5 — Seeded evaluation (precision / recall / F1)

The brief requires reporting precision, recall, and F1 for the Registry & Readiness lane.
Problem: the raw AED dataset has no "this pair is a confirmed duplicate" labels to check
against — real duplicates might exist, but we don't have ground truth for them.

Standard fix used in data-quality/entity-resolution work: seed a known set of synthetic
duplicates and known-clean records into a copy of the real data, run the detector, and see
how many it actually catches. This gives a real, defensible accuracy number instead of
"we don't know."

Run this AFTER 1_explore_data.py has produced data/aed_flat.csv.
"""

import pandas as pd
import random
import sys
import os

sys.path.append(os.path.dirname(__file__))
from importlib import import_module

baseline_mod = import_module("2_baseline_rules") if os.path.exists("2_baseline_rules.py") else None
smart_mod = import_module("3_smart_detector") if os.path.exists("3_smart_detector.py") else None

DATA_PATH = "data/aed_flat.csv"
N_SEEDED_DUPES = 25   # how many synthetic duplicate pairs to inject
N_SEEDED_CLEAN = 25   # how many genuinely distinct records to sample as the "should NOT flag" set
RANDOM_SEED = 42


def make_synthetic_duplicate(row, variation_style):
    """Takes a real record and creates a near-duplicate with a realistic small change —
    the kind of variation you'd actually see from double data-entry (typo, extra word,
    abbreviation swap) rather than an exact copy, which would be too easy."""
    dup = row.copy()
    building = str(row.get("BUILDING_NAME", "") or "")

    if variation_style == "abbreviation" and "Block" in building:
        dup["BUILDING_NAME"] = building.replace("Block", "Blk")
    elif variation_style == "extra_word":
        dup["BUILDING_NAME"] = building + " Building"
    elif variation_style == "typo" and len(building) > 4:
        # swap two adjacent characters mid-string — simulates a data-entry typo
        i = len(building) // 2
        chars = list(building)
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
        dup["BUILDING_NAME"] = "".join(chars)
    else:
        dup["BUILDING_NAME"] = building  # near-exact, no building name variation

    # Give it a new AED_ID so it's traceable as the injected twin
    dup["AED_ID"] = str(row.get("AED_ID", "")) + "-SEEDED"
    return dup


def build_seeded_test_set(df):
    random.seed(RANDOM_SEED)

    # Only seed duplicates from records that actually have a building name —
    # matches the real-world case the detector is meant to catch.
    candidates = df[df["BUILDING_NAME"].notna() & (df["BUILDING_NAME"].str.strip() != "")]
    dupe_sources = candidates.sample(n=min(N_SEEDED_DUPES, len(candidates)), random_state=RANDOM_SEED)

    variation_styles = ["abbreviation", "extra_word", "typo", "near_exact"]
    seeded_dupes = []
    ground_truth_pairs = []  # (original_AED_ID, seeded_AED_ID)

    for _, row in dupe_sources.iterrows():
        style = random.choice(variation_styles)
        synthetic = make_synthetic_duplicate(row, style)
        seeded_dupes.append(synthetic)
        ground_truth_pairs.append((row["AED_ID"], synthetic["AED_ID"]))

    seeded_df = pd.DataFrame(seeded_dupes)

    # Known-clean sample: real records NOT involved in any seeded pair — the detector
    # should leave these alone. Excludes the dupe_sources rows so we're not double-testing.
    remaining = df[~df["AED_ID"].isin(dupe_sources["AED_ID"])]
    clean_sample = remaining.sample(n=min(N_SEEDED_CLEAN, len(remaining)), random_state=RANDOM_SEED)

    test_set = pd.concat([df, seeded_df], ignore_index=True)
    seeded_ids = set(seeded_df["AED_ID"]) | set(dupe_sources["AED_ID"])
    clean_ids = set(clean_sample["AED_ID"])

    return test_set, seeded_ids, clean_ids, ground_truth_pairs


def evaluate(test_set, seeded_ids, clean_ids):
    baseline_result = baseline_mod.run_baseline(test_set)
    smart_result = smart_mod.find_fuzzy_duplicates(baseline_result)
    smart_result = smart_mod.compute_confidence_score(smart_result)

    flagged_ids = set(smart_result[smart_result["review_confidence_score"] > 0]["AED_ID"])

    tp = len(seeded_ids & flagged_ids)          # seeded duplicate, correctly flagged
    fn = len(seeded_ids - flagged_ids)          # seeded duplicate, MISSED
    fp = len(clean_ids & flagged_ids)           # known-clean record, WRONGLY flagged
    tn = len(clean_ids - flagged_ids)           # known-clean record, correctly left alone

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print("=" * 60)
    print("SEEDED EVALUATION RESULTS (synthetic ground truth)")
    print("=" * 60)
    print(f"Seeded duplicate records injected: {len(seeded_ids)}")
    print(f"Known-clean records sampled:       {len(clean_ids)}")
    print()
    print(f"True positives  (correctly flagged seeded dupes): {tp}")
    print(f"False negatives (missed seeded dupes):             {fn}")
    print(f"False positives (wrongly flagged clean records):   {fp}")
    print(f"True negatives  (correctly left clean records):    {tn}")
    print()
    print(f"Precision: {precision:.2%}")
    print(f"Recall:    {recall:.2%}")
    print(f"F1 score:  {f1:.2%}")
    print("=" * 60)
    print(
        "\nNote: this measures performance against SYNTHETIC seeded duplicates, not\n"
        "verified real-world duplicates (none exist in the source data). Treat this as a\n"
        "sensitivity/stress test of the detection logic, not validated field accuracy."
    )

    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fn": fn, "fp": fp, "tn": tn}


if __name__ == "__main__":
    if baseline_mod is None or smart_mod is None:
        raise SystemExit("Run this from the same folder as 2_baseline_rules.py and 3_smart_detector.py")

    df = pd.read_csv(DATA_PATH)
    test_set, seeded_ids, clean_ids, ground_truth_pairs = build_seeded_test_set(df)
    metrics = evaluate(test_set, seeded_ids, clean_ids)

    pd.DataFrame([metrics]).to_csv("data/seeded_evaluation_results.csv", index=False)
    print("\nSaved metrics to data/seeded_evaluation_results.csv — copy these numbers into REPORT.md")
