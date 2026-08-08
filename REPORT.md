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

**Architecture:** A three-stage pipeline —
1. **Baseline (non-AI):** Deterministic rule checks — missing address fields, coordinates
   falling outside Singapore's geographic bounds, exact-duplicate coordinates, and
   operating-hours text that doesn't match a recognizable time-range pattern.
2. **Smart detector:** Adds fuzzy text-similarity matching (via `rapidfuzz`) on
   `BUILDING_NAME + ROAD_NAME`, to catch near-duplicate entries that don't share exact
   coordinates. To keep this efficient at ~9,644 records, comparisons are limited to
   records sharing the same `ROAD_NAME` ("blocking") rather than comparing every record
   against every other record.
3. **Confidence scoring:** Each flag type is combined into a single 0–1 weighted score
   (invalid coordinates weighted highest, malformed hours text weighted lowest), so a
   human reviewer can prioritize the worst records first instead of working through an
   unranked list.

**Input features:** `OPERATING_HOURS`, `ROAD_NAME`, `BUILDING_NAME`, `LATITUDE`, `LONGITUDE`,
`POSTAL_CODE`. Internal fields without documented meaning (`INC_CRC`, `FMEL_UPD_D`) were
deliberately excluded, per the brief's caution against assigning operational meaning to
undocumented fields.

**Training/optimization process:** No model training — this is a rule-based and
similarity-matching system, chosen deliberately for transparency: every flag traces back
to a specific, explainable rule, which matters for a tool a human has to trust and act on.

**Assumptions:** Records on the same road with highly similar names are the primary
duplicate signal; this assumption is documented and may miss duplicates that use
inconsistent road-name spelling.

**Confidence handling:** Every record gets a continuous 0–1 score rather than a binary
flag, so borderline cases are visibly distinguished from clear-cut issues.

**Human-approval point:** The dashboard is a review queue only — no record is auto-edited,
auto-deleted, or auto-confirmed. All actions require a human reviewer decision.

## 3. Baseline & Evaluation

| Metric | Baseline (simple rules) | Smart detector |
|---|---|---|
| Total flagged | 1,557 (16.1%) | 3,336 (34.6%) |
| Missing address | 0 | — |
| Invalid coordinates | 0 | — |
| Duplicate coordinates | 1,456 | — |
| Malformed hours text | 118 | — |
| Fuzzy near-duplicates (new, not caught by baseline) | — | 1,779 |

**Known failure modes / limitations:**
- The malformed-hours check uses a simple pattern match and may flag some valid but
  unusually-formatted hours text as "malformed" (false positive) — this is a documented
  limitation, not a hidden claim of full accuracy
- Fuzzy matching is deliberately restricted to same-road, same-floor (or matching
  location-description) pairs — this avoids the false-positive trap of flagging every
  legitimate multi-AED building (e.g. malls, hospitals with several floors) as
  "duplicates." This trade-off means it may miss a real duplicate that has inconsistent
  floor data entered
- No ground-truth "confirmed duplicate" labels exist for this dataset, so precision/recall
  cannot be computed against verified truth — results here are a **sensitivity analysis**,
  not validated real-world accuracy, consistent with the brief's guidance on datasets
  without ground truth
- Notably, **0 records** had invalid coordinates or missing core address fields — the
  registry is structurally sound on those two dimensions; all flagged issues stem from
  duplicate/near-duplicate entries and inconsistent operating-hours formatting

## 4. Data & Reproducibility

- **Source:** SCDF Public Access AEDs, data.gov.sg, GeoJSON format
- **Dataset date:** February 2020 (per the source page's stated data date)
- **Licence:** Singapore Open Data Licence v1.0
- **Retrieved:** August 2026, for SGTDP 2026 submission
- **Fields used:** See Method Card above
- **No supplemental or synthetic data used** in this submission

## 5. Safety & Privacy Statement

- [x] Every user-facing screen displays the mandatory safety notice
- [x] Uses only the supplied historical registry snapshot — no live incident, dispatch,
      or myResponder data
- [x] Does not claim to detect battery state, pad expiry, or device readiness
- [x] Does not label any AED as currently available or working
- [x] Distinguishes data-quality flags from confirmed real-world faults throughout
- [x] Collects no personal data, names, or contact details
- [x] No credentials or API keys are present in this repository
