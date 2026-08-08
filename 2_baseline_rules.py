"""
STEP 2 — Baseline: deterministic validation rules
The challenge requires comparing your smarter detector against a simple, non-AI baseline.
This file IS that baseline: plain, hard-coded checks. Fast to build, and mandatory.

Each rule below returns True if a record LOOKS problematic. A human still reviews everything —
this never auto-deletes or auto-corrects data.
"""

import pandas as pd
import re

DATA_PATH = "data/aed_flat.csv"


def flag_missing_address(row):
    """Missing core address components."""
    return pd.isna(row.get("ROAD_NAME")) or pd.isna(row.get("POSTAL_CODE"))


def flag_invalid_coordinates(row):
    """Singapore's lat/long range roughly: lat 1.2–1.5, long 103.6–104.1.
    Anything outside this is very likely a data error."""
    lat, lon = row.get("LATITUDE"), row.get("LONGITUDE")
    if pd.isna(lat) or pd.isna(lon):
        return True
    return not (1.1 <= lat <= 1.5 and 103.5 <= lon <= 104.2)


def flag_duplicate_coordinates(df):

    coord_dupes = df.duplicated(
        subset=["LATITUDE", "LONGITUDE"],
        keep=False
    )

    # only suspicious if coordinates duplicate
    # AND location description duplicates

    desc_dupes = df.duplicated(
        subset=[
            "LATITUDE",
            "LONGITUDE",
            "AED_LOCATION_DESCRIPTION"
        ],
        keep=False
    )

    return coord_dupes & desc_dupes

def flag_malformed_hours(row):
    """Very rough check: does OPERATING_HOURS contain recognizable time-like text?
    Flags entries that are empty, or don't look like a time range at all."""
    text = row.get("OPERATING_HOURS")
    if pd.isna(text) or str(text).strip() == "":
        return True
    # crude pattern: looks for digits + am/pm/hrs/: something
    has_time_pattern = bool(re.search(r"\d{1,2}[:.]?\d{0,2}\s*(am|pm|hrs|hours|-|to)", str(text), re.IGNORECASE))
    is_common_phrase = str(text).strip().lower() in ["24 hours", "24hrs", "24/7"]
    return not (has_time_pattern or is_common_phrase)


def run_baseline(df):
    df = df.copy()
    df["flag_missing_address"] = df.apply(flag_missing_address, axis=1)
    df["flag_invalid_coords"] = df.apply(flag_invalid_coordinates, axis=1)
    df["flag_duplicate_coords"] = flag_duplicate_coordinates(df)
    df["flag_malformed_hours"] = df.apply(flag_malformed_hours, axis=1)

    df["any_flag"] = df[[
        "flag_missing_address", "flag_invalid_coords",
        "flag_duplicate_coords", "flag_malformed_hours"
    ]].any(axis=1)

    print("=== Baseline rule results ===")
    print(f"Total records: {len(df)}")
    print(f"Missing address:     {df['flag_missing_address'].sum()}")
    print(f"Invalid coordinates: {df['flag_invalid_coords'].sum()}")
    print(f"Duplicate coords:    {df['flag_duplicate_coords'].sum()}")
    print(f"Malformed hours:     {df['flag_malformed_hours'].sum()}")
    print(f"Any issue at all:    {df['any_flag'].sum()} ({df['any_flag'].mean():.1%} of records)")

    return df


if __name__ == "__main__":
    df = pd.read_csv(DATA_PATH)
    flagged_df = run_baseline(df)
    flagged_df.to_csv("data/aed_baseline_flags.csv", index=False)
    print("\nSaved flagged results to data/aed_baseline_flags.csv")