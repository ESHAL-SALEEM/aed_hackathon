# AED Registry & Readiness — Review Tool

**SGTDP 2026 — Sofstica AI Hackathon — AED Accessibility, Lane 3**

A decision-support tool that scans Singapore's public AED location registry (9,644
records from SCDF/data.gov.sg) and flags entries likely to have data-quality problems —
duplicates, missing fields, inconsistent formatting, statistical outliers — so a human
reviewer knows where to look first instead of manually checking thousands of records.

> ⚠️ **Prototype for planning and simulation only — not for emergency use.** In an
> emergency in Singapore, call **995** immediately and follow SCDF instructions. This tool
> does not confirm live AED availability and is not affiliated with SCDF or myResponder.

See [`REPORT.md`](./REPORT.md) for the full problem definition, method card, evaluation
results, and safety statement (all required deliverables for this challenge).

## How it works — 4 layers

1. **Baseline (non-AI rules)** — missing address, invalid coordinates, exact duplicate
   coordinates + matching description, malformed operating hours.
2. **Fuzzy duplicate matching** — catches near-duplicates like "Blk 123" vs "Block 123"
   that exact-match rules miss, restricted to same-road, same-floor pairs to avoid
   false-flagging legitimate multi-AED buildings.
3. **AI anomaly detector** — an Isolation Forest model (unsupervised ML) flags the ~3%
   most statistically unusual records, independent of any hand-written rule.
4. **Blended score + human review dashboard** — every record gets a 0–1 priority score;
   a reviewer confirms or rejects each flag in a Streamlit app. Nothing is auto-corrected.

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
pip install pandas rapidfuzz streamlit scikit-learn
```

## Get the data

Download the Public Access AEDs GeoJSON from
[data.gov.sg](https://data.gov.sg/datasets/d_4e6b82c58a8a832f6f1fee5dfa6d47ea/view) and
save it as `aed_locations.geojson` in this folder.

## Run order

```bash
python 1_explore_data.py          # loads raw data, saves data/aed_flat.csv
python 2_baseline_rules.py        # non-AI baseline, saves data/aed_baseline_flags.csv
python 3_smart_detector.py        # fuzzy matching + confidence score, saves data/aed_final_scored.csv
python 6_anomaly_detector.py      # AI anomaly layer, saves data/aed_final_with_ai.csv
streamlit run 4_dashboard.py      # opens the review dashboard in your browser
```

Optional, after reviewing some records in the dashboard:

```bash
python 5_evaluation.py            # seeded ground-truth precision/recall/F1
python 7_usability_metrics.py     # reviewer time per validated issue (median/p90/p95)
```

## Project structure

| File | Purpose |
|---|---|
| `1_explore_data.py` | Load and inspect the raw GeoJSON |
| `2_baseline_rules.py` | Non-AI baseline (required comparison point) |
| `3_smart_detector.py` | Fuzzy duplicate matching + confidence scoring |
| `4_dashboard.py` | Streamlit reviewer dashboard |
| `5_evaluation.py` | Seeded precision/recall/F1 evaluation |
| `6_anomaly_detector.py` | Isolation Forest AI anomaly layer |
| `7_usability_metrics.py` | Reviewer time metrics from real dashboard usage |
| `REPORT.md` | Problem definition, method card, evaluation, safety statement |
| `data/` | Generated CSVs at each pipeline stage (created when scripts run) |

## Data source

SCDF Public Access AEDs, [data.gov.sg](https://data.gov.sg/datasets/d_4e6b82c58a8a832f6f1fee5dfa6d47ea/view),
GeoJSON format, historical snapshot dated February 2020. Singapore Open Data Licence v1.0.
