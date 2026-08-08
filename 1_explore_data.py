"""
STEP 1 — Explore the AED dataset
Run this first once you have the organizer-provided frozen copy of SCDF's
Public Access AEDs dataset (originally from data.gov.sg, GeoJSON format).

This just loads the data and shows you what's there — no analysis yet.
"""

import json
import pandas as pd

# ---- EDIT THIS ----
DATA_PATH = "aed_locations.geojson"   # <-- point at the organizer file once downloaded
# --------------------

EXPECTED_FIELDS = [
    "OBJECTID", "AED_ID", "OPERATING_HOURS", "HOUSE_NUMBER", "ROAD_NAME",
    "BUILDING_NAME", "UNIT_NUMBER", "POSTAL_CODE", "AED_LOCATION_DESCRIPTION",
    "AED_LOCATION_FLOOR_LEVEL", "LATITUDE", "LONGITUDE", "XVAL", "YVAL",
    "INC_CRC", "FMEL_UPD_D",
]


def load_geojson_as_dataframe(path):
    with open(path, "r") as f:
        geo = json.load(f)

    rows = []
    for feature in geo["features"]:
        props = feature["properties"]
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [None, None])
        row = dict(props)
        row["geo_longitude"] = coords[0]
        row["geo_latitude"] = coords[1]
        rows.append(row)

    return pd.DataFrame(rows)


def main():
    df = load_geojson_as_dataframe(DATA_PATH)

    print("=" * 60)
    print(f"Shape: {df.shape[0]} AED records, {df.shape[1]} fields")
    print("=" * 60)

    print("\nColumns present:")
    print(list(df.columns))

    missing_expected = [f for f in EXPECTED_FIELDS if f not in df.columns]
    if missing_expected:
        print(f"\n[!] Expected fields not found (naming may differ slightly): {missing_expected}")

    print("\nMissing values per column:")
    print(df.isna().sum()[df.isna().sum() > 0])

    print("\nSample OPERATING_HOURS text (this field is messy — you'll clean it in step 2):")
    if "OPERATING_HOURS" in df.columns:
        print(df["OPERATING_HOURS"].dropna().unique()[:15])

    print("\nDuplicate coordinate pairs (potential duplicate AED entries):")
    if "LATITUDE" in df.columns and "LONGITUDE" in df.columns:
        dupes = df[df.duplicated(subset=["LATITUDE", "LONGITUDE"], keep=False)]
        print(f"{len(dupes)} rows share coordinates with at least one other row")

    print("\nFirst 5 rows:")
    print(df.head())

    df.to_csv("data/aed_flat.csv", index=False)
    print("\nSaved a flat CSV copy to data/aed_flat.csv for the next steps.")


if __name__ == "__main__":
    main()
