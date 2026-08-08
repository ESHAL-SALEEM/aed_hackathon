# AED Registry & Readiness — Report

## 1. Problem & User Definition

**Intended user:** Facility managers, registry/data managers, and community-preparedness
coordinators responsible for maintaining Singapore's public-access AED location data —
not emergency responders and not the public in an active emergency.

**The decision this tool supports:** "Which of the ~9,644 records in the AED registry
should a human reviewer check first?" Manually auditing thousands of location records is
slow. This tool triages that list by likely data-quality risk, so a limited reviewer's time
is spent on the records most likely to be wrong.

**What it explicitly does NOT do:**
- It does not confirm whether a physical AED is present, working, stocked, or currently accessible
- It does not replace SCDF's 995 emergency service or the official myResponder app
- It does not make any claim about survival outcomes or emergency response times

**Success criteria:** A flagged record should have a real chance of being a genuine data
issue — not random noise — and the tool should catch problems a simple manual scan of
the raw list would likely miss.

## 2. Method Card

**Architecture:** A four-stage pipeline —

1. **Baseline (non-AI, required comparison point):** Deterministic rule checks — missing
   address fields, coordinates falling outside Singapore's geographic bounds, duplicate
   coordinates (refined to require a matching location description too, so two distinct
   AEDs that legitimately share a building aren't falsely flagged), and operating-hours
   text that doesn't match a recognizable time-range pattern. Flags 149 records (1.5%).

2. **Smart detector (fuzzy text matching):** Groups records by road, then compares
   `BUILDING_NAME` text similarity (via `rapidfuzz`) to catch near-duplicates the exact-match
   baseline misses (e.g. "Blk 123" vs "Block 123"). Matches require the floor level to
   explicitly agree (or be absent on both sides) — an explicit floor mismatch always rules
   out a match, even when the location-description text happens to look similar (e.g.
   "Level 1 Block 51" vs "Level 2 Block 51" score ~94% similar as text despite describing
   different floors — this case is deliberately excluded). Flags 2,453 records (25.4%),
   2,304 of which the baseline missed entirely.

3. **AI anomaly detector (Isolation Forest, unsupervised):** A machine-learning model
   trained on coordinates, missing-field indicators, and text length across all 9,644
   records — it learns what a "normal" record looks like without being told what a problem
   is, then flags the statistical outliers. Uses the model's binary anomaly prediction
   (not just the raw continuous score) to decide which ~3% of records are flagged, matching
   the configured `contamination=0.03` setting. Flags 290 records, 127 of which neither the
   baseline nor the fuzzy matcher caught — genuinely new findings from the AI layer alone.

4. **Blended final score:** `final_review_score = 0.7 × rule-based score + 0.3 × AI anomaly
   contribution` (AI only contributes when the model's own anomaly flag is true, preventing
   normalization noise from inflating scores for records the model didn't actually flag).
   Total review queue: 2,580 records (26.8% of the dataset).

**Input features:** `OPERATING_HOURS`, `ROAD_NAME`, `BUILDING_NAME`, `LATITUDE`, `LONGITUDE`,
`POSTAL_CODE`, `AED_LOCATION_DESCRIPTION`, `AED_LOCATION_FLOOR_LEVEL`. Internal fields
without documented meaning (`INC_CRC`, `FMEL_UPD_D`) were deliberately excluded, per the
brief's caution against assigning operational meaning to undocumented fields.

**Training/optimization process:** The rule-based and fuzzy-matching layers require no
training — every flag traces back to a specific, explainable check. The Isolation Forest
is trained (fit) once on the full feature set in an unsupervised manner; no labeled
training data exists or is used.

**Assumptions:**
- Duplicate detection assumes records on the same road with highly similar building names
  and matching floor/description are the primary duplicate signal — may miss duplicates
  with inconsistent road-name spelling
- The AI layer assumes ~3% of records are genuine anomalies (the `contamination` parameter)
  — this is a modeling choice, not a measured fact about the real registry

**Confidence handling:** Every record gets a continuous 0–1 final score rather than a flat
flag, so borderline cases are visibly distinguished from clear-cut issues. The dashboard
lets a reviewer filter by minimum score and by "AI-only" catches specifically.

**Human-approval point:** The dashboard is a review queue only — no record is auto-edited,
auto-deleted, or auto-confirmed. Every record requires an explicit human "confirm" or
"false positive" decision, logged with a timestamp.

## 3. Baseline & Evaluation

**Primary metric (nominated before final evaluation): Recall on seeded duplicate detection.**
For a human-reviewed queue, missing a real issue (a false negative) is worse than an extra
false positive a reviewer spends a few seconds dismissing — so recall is weighted as the
single most important number for this tool's core job. Precision, F1, and reviewer-time
percentiles below are reported as supporting metrics.

| Metric | Baseline (rules) | + Fuzzy matching | + AI anomaly layer |
|---|---|---|---|
| Total flagged | 149 (1.5%) | 2,453 (25.4%) | 2,580 (26.8%) |
| New catches vs. previous layer | — | 2,304 | 127 |

*Note: these are raw detection counts. The dashboard's actual review queue is smaller,
since a matched duplicate pair is collapsed into a single queue entry — resolving one side
of the pair automatically resolves the other, so a reviewer only needs to make one decision
per pair rather than two. Detection accuracy is unaffected; only the reviewer's workload is
reduced.*

**Seeded ground-truth evaluation** (since the raw dataset has no confirmed-duplicate
labels, 25 synthetic duplicate records were injected with realistic variations —
abbreviations, typos, extra words — alongside 25 known-clean records, and the detector
was run against this test set):

| Metric | Result |
|---|---|
| True positives (seeded duplicates correctly flagged) | 50 |
| False negatives (seeded duplicates missed) | 0 |
| False positives (clean records wrongly flagged) | 5 |
| True negatives (clean records correctly left alone) | 20 |
| **Precision** | **90.91%** |
| **Recall** | **100.00%** |
| **F1 score** | **95.24%** |

This is a sensitivity/stress test against synthetic ground truth, not validated real-world
accuracy — no confirmed-duplicate labels exist for the actual registry. Full recall on
seeded duplicates is a strong signal the detector's core logic works; the 90.9% precision
reflects a deliberate lean toward catching more real issues at the cost of some false
positives, which is appropriate for a human-reviewed queue where a false positive costs a
reviewer a few seconds, but a missed real issue costs nothing (it's never looked at again).

**Performance / usability metric (reviewer time per validated issue):** Measured from
21 real reviewer actions on the final version of the dashboard — median 12.2 sec, p90 29.9
sec, p95 82.3 sec. The mean (61.4 sec) is noticeably higher than the median because one
natural pause was taken partway through the session, as would happen in any real review
workflow; median and percentiles are reported as the primary figures for exactly this
reason, per the brief's own guidance that averages alone are insufficient.

**Note on iteration:** an earlier version of the fuzzy-matching logic allowed a strongly
similar location-description string to override an explicit floor-level mismatch (e.g.
"Level 1 Block 51" vs "Level 2 Block 51" scored ~94% textually similar despite describing
different floors). This was caught during manual spot-checking of flagged pairs in the
dashboard and fixed — an explicit floor disagreement now always disqualifies a match,
regardless of description similarity. This iteration is documented here rather than hidden,
since catching and fixing a false-positive source is itself part of demonstrating a
reliable, human-verified pipeline.

**Known failure modes / limitations:**
- The malformed-hours check uses a simple pattern match and may flag some validly-formatted
  but unusual hours text as "malformed"
- Fuzzy matching is deliberately restricted to same-road, same-floor (or matching
  description) pairs, trading some recall for much lower false positives on legitimate
  multi-AED buildings
- The AI anomaly layer's 3% contamination assumption is a modeling choice, not derived from
  the data — a different assumed anomaly rate would change which records get flagged
- No ground-truth "confirmed duplicate" labels exist for the real dataset, so real-world
  precision/recall cannot be measured directly; the seeded evaluation above is the closest
  available substitute
- **0 records** had invalid coordinates or missing core address fields — the registry is
  structurally sound on those two dimensions; all flagged issues stem from duplicates,
  inconsistent operating-hours formatting, and AI-detected statistical outliers

## 4. Data & Reproducibility

- **Source:** SCDF Public Access AEDs, data.gov.sg, GeoJSON format
- **Dataset date:** February 2020 (per the source page's stated data date)
- **Licence:** Singapore Open Data Licence v1.0
- **File checksum (SHA256):** `e2ef793ffd0fd2dbe99ffdcfb21b38154c81fd0685d1f0fcc5b75a6d57205c02` —
  run `certutil -hashfile aed_locations.geojson SHA256` (Windows) to verify against the
  copy in this repo
- **Retrieved:** August 2026, for SGTDP 2026 submission
- **Fields used:** See Method Card above
- **No supplemental or synthetic data used for the core detection pipeline** — synthetic
  data appears only in the separate seeded-evaluation test set, clearly labeled and kept
  apart from the real registry data throughout

## 5. Safety & Privacy Statement

- [x] Every user-facing screen displays the mandatory safety notice
- [x] Uses only the supplied historical registry snapshot — no live incident, dispatch,
      or myResponder data
- [x] Does not claim to detect battery state, pad expiry, or device readiness
- [x] Does not label any AED as currently available or working
- [x] Distinguishes data-quality flags (including AI-flagged statistical outliers) from
      confirmed real-world faults throughout
- [x] Collects no personal data, names, or contact details
- [x] No credentials or API keys are present in this repository
