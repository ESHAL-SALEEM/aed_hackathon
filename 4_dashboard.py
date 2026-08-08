"""
STEP 4 — Reviewer dashboard
Run with:  streamlit run 4_dashboard.py

This is a human-in-the-loop review queue — the reviewer sees WHY a record was flagged
and can accept/reject the flag. Nothing here auto-edits the real registry. Once a record
is reviewed, it moves out of the pending queue into a "Confirmed" or "False Positive" tab.
"""

import streamlit as st
import pandas as pd
import os
import re

st.set_page_config(page_title="AED Registry Review Queue", layout="wide")

st.title("🏥 AED Registry & Readiness — Review Queue")

st.warning(
    "⚠️ **Prototype for planning and simulation only — not for emergency use.** "
    "In an emergency in Singapore, call **995** immediately and follow SCDF instructions. "
    "Use official SCDF/myResponder channels. Do not delay emergency action to use this prototype."
)

st.info(
    "📅 **Data note:** This dataset is a historical snapshot from **February 2020**, sourced from "
    "SCDF's Public Access AEDs registry on data.gov.sg. It is not a live feed — it may not reflect "
    "current AED locations, hours, or status."
)

st.info(
    "🤖 **AI layer:** An Isolation Forest model scores every record for how statistically "
    "unusual it looks compared to the rest of the registry, independent of the rule-based "
    "checks. The final priority score blends both: 70% rule-based, 30% AI anomaly score."
)

st.caption(
    "🔍 **What a flag means:** A flag here indicates a possible **data-quality issue** in the "
    "registry record (e.g. a likely duplicate entry, a missing field, an unusual coordinate, "
    "or a statistically unusual pattern the AI model noticed). It is **not** a confirmation "
    "that a physical AED is broken, missing, or inaccessible — every flag requires human "
    "verification before any action is taken."
)

DATA_PATH = "data/aed_final_with_ai.csv"
LOG_PATH = "data/reviewer_decisions.csv"


@st.cache_data
def load_data(path):
    return pd.read_csv(path)


def load_decisions(path):
    if not os.path.exists(path):
        return {}
    log = pd.read_csv(path)
    if log.empty:
        return {}
    log = log.sort_values("reviewed_at").drop_duplicates(subset="AED_ID", keep="last")
    return dict(zip(log["AED_ID"], log["reviewer_decision"]))


def save_decision(aed_id, score, decision):
    log_entry = pd.DataFrame([{
        "AED_ID": aed_id,
        "review_confidence_score": score,
        "reviewer_decision": decision,
        "reviewed_at": pd.Timestamp.now().isoformat(),
    }])
    if os.path.exists(LOG_PATH):
        existing = pd.read_csv(LOG_PATH)
        log_entry = pd.concat([existing, log_entry], ignore_index=True)
    log_entry.to_csv(LOG_PATH, index=False)


def hours_text_is_malformed(text):
    """Recomputes the malformed-hours check live from the actual text, instead of
    trusting the saved flag column — booleans can lose their type after passing through
    several CSV save/reload cycles, so this keeps the displayed reason always accurate."""
    if pd.isna(text) or str(text).strip() == "":
        return True
    has_time_pattern = bool(re.search(r"\d{1,2}[:.]?\d{0,2}\s*(am|pm|hrs|hours|-|to)", str(text), re.IGNORECASE))
    is_common_phrase = str(text).strip().lower() in ["24 hours", "24hrs", "24/7"]
    return not (has_time_pattern or is_common_phrase)


def reasons_for(record):
    reasons = []
    if record.get("flag_missing_address"):
        reasons.append("Missing road name or postal code")
    if record.get("flag_invalid_coords"):
        reasons.append("Coordinates fall outside Singapore's bounds")
    if record.get("flag_duplicate_coords"):
        reasons.append("Same coordinates AND same location description as another record")
    if record.get("flag_fuzzy_duplicate"):
        reasons.append("Very similar address text to another record (same building/floor)")
    if record.get("flag_malformed_hours") or hours_text_is_malformed(record.get("OPERATING_HOURS")):
        reasons.append("Operating hours text doesn't look like a valid time range")
    if record.get("review_confidence_score", 0) == 0 and record.get("ai_anomaly_score", 0) > 0:
        reasons.append("Flagged by the AI model as statistically unusual — no specific rule triggered")
    return reasons if reasons else ["No specific flag triggered — check manually."]


def render_record_inspector(full_df, record_id, key_prefix):
    """One reusable panel: metrics, raw fields, why-flagged, matched-duplicate comparison,
    and confirm/reject buttons. Used both by the top-priority 'Review →' buttons and by
    the Pending tab's manual picker, so there's exactly one place this logic can break."""
    record = full_df.loc[record_id]

    col1, col2 = st.columns(2)
    with col1:
        m1, m2 = st.columns(2)
        m1.metric("Final review score", f"{record['final_review_score']:.2f}")
        m2.metric("AI anomaly score", f"{record.get('ai_anomaly_score', 0):.2f}")
        st.write("**Raw fields:**")
        st.json(record.drop(labels=["_decision"], errors="ignore").dropna().to_dict())

    with col2:
        st.write("**Why flagged:**")
        for r in reasons_for(record):
            st.write(f"- {r}")

        partner_aed_id = record.get("fuzzy_duplicate_partner_aed_id")
        if pd.notna(partner_aed_id) and partner_aed_id in full_df["AED_ID"].values:
            partner = full_df[full_df["AED_ID"] == partner_aed_id].iloc[0]
            st.write("")
            st.write("**Compared against — the matched record:**")
            compare_fields = ["AED_ID", "BUILDING_NAME", "ROAD_NAME",
                               "AED_LOCATION_FLOOR_LEVEL", "AED_LOCATION_DESCRIPTION",
                               "OPERATING_HOURS"]
            comparison = pd.DataFrame({
                "This record": [record.get(f, "") for f in compare_fields],
                "Matched record": [partner.get(f, "") for f in compare_fields],
            }, index=compare_fields)
            st.dataframe(comparison, width="stretch")

        st.write("")
        c1, c2 = st.columns(2)
        confirm_clicked = c1.button("✅ Confirm real issue", key=f"{key_prefix}_confirm_{record_id}")
        reject_clicked = c2.button("❌ Mark false positive", key=f"{key_prefix}_reject_{record_id}")

        if confirm_clicked or reject_clicked:
            decision = "confirmed_real_issue" if confirm_clicked else "false_positive"
            save_decision(record.get("AED_ID", ""), record.get("final_review_score", ""), decision)
            aed_label = record.get("AED_ID", "")
            st.session_state["flash_message"] = (
                f"AED {aed_label} confirmed as a real issue." if decision == "confirmed_real_issue"
                else f"AED {aed_label} marked as a false positive."
            )
            st.session_state.pop("open_record", None)
            st.rerun()


df = load_data(DATA_PATH)
decisions = load_decisions(LOG_PATH)

df = df[df["final_review_score"] > 0].copy()
df["_decision"] = df["AED_ID"].map(decisions).fillna("pending")

if "flash_message" in st.session_state:
    st.toast(st.session_state["flash_message"], icon="✅")
    del st.session_state["flash_message"]

# ---- Sidebar filter (applies within the Pending tab only) ----
st.sidebar.header("Filter (Pending tab)")
min_score = st.sidebar.slider("Minimum final review score", 0.0, 1.0, 0.2, 0.05)
flag_types = st.sidebar.multiselect(
    "Show only these issue types",
    ["flag_missing_address", "flag_invalid_coords", "flag_duplicate_coords",
     "flag_fuzzy_duplicate", "flag_malformed_hours"],
    default=[]
)
ai_only_toggle = st.sidebar.checkbox(
    "Show only AI-caught records (missed by all rules)",
    value=False,
    help="Records with review_confidence_score = 0 but final_review_score > 0 — "
         "these were flagged purely by the anomaly detector, not by any hand-written rule."
)

# ---- Detection layers compared ----
st.subheader("Detection layers compared")
baseline_count = int(df["any_flag"].sum()) if "any_flag" in df.columns else None
rules_count = int((df["review_confidence_score"] > 0).sum())
ai_only_count = int(((df["review_confidence_score"] == 0) & (df["final_review_score"] > 0)).sum())
total_count = int((df["final_review_score"] > 0).sum())

c1, c2, c3, c4 = st.columns(4)
if baseline_count is not None:
    c1.metric("Baseline (simple rules)", f"{baseline_count:,}")
c2.metric("Rules + fuzzy matching", f"{rules_count:,}")
c3.metric("AI-only catches", f"{ai_only_count:,}", "missed by every rule")
c4.metric("Total in review queue", f"{total_count:,}", f"{total_count/len(df):.1%} of records")

st.divider()

# ---- Top priority records — click Review to inspect right here, no jumping around ----
st.subheader("🔥 Top priority records")
st.caption("Click \"Review →\" to open that record's full detail below.")
top5 = df[df["_decision"] == "pending"].sort_values("final_review_score", ascending=False).head(5)
for _, row in top5.iterrows():
    tc1, tc2, tc3, tc4, tc5 = st.columns([1.2, 3, 2, 1, 1])
    tc1.write(row.get("AED_ID", ""))
    tc2.write(row.get("BUILDING_NAME", ""))
    tc3.write(row.get("ROAD_NAME", ""))
    tc4.write(f"{row.get('final_review_score', 0):.2f}")
    if tc5.button("Review →", key=f"toppick_{row.get('AED_ID', '')}"):
        st.session_state["open_record"] = row.name  # row.name = the DataFrame index label

if ("open_record" in st.session_state and st.session_state["open_record"] in df.index
        and df.loc[st.session_state["open_record"], "_decision"] == "pending"):
    st.write("")
    st.markdown("#### Reviewing:")
    render_record_inspector(df, st.session_state["open_record"], key_prefix="top")
    if st.button("Close", key="close_top_inspector"):
        del st.session_state["open_record"]
        st.rerun()

st.divider()

# ---- Static map — no extra dependencies, can't break ----
st.subheader("📍 Flagged locations")
map_data = df[["LATITUDE", "LONGITUDE"]].dropna().rename(columns={"LATITUDE": "lat", "LONGITUDE": "lon"})
if not map_data.empty:
    st.map(map_data, size=15, zoom=11)
else:
    st.info("No flagged records with valid coordinates to show.")

st.divider()

display_cols = [c for c in [
    "AED_ID", "BUILDING_NAME", "ROAD_NAME", "OPERATING_HOURS",
    "final_review_score", "review_confidence_score", "ai_anomaly_score",
    "flag_missing_address", "flag_invalid_coords",
    "flag_duplicate_coords", "flag_fuzzy_duplicate", "flag_malformed_hours"
] if c in df.columns]

tab_pending, tab_confirmed, tab_false = st.tabs([
    f"🕓 Pending Review ({(df['_decision'] == 'pending').sum()})",
    f"✅ Confirmed Real Issues ({(df['_decision'] == 'confirmed_real_issue').sum()})",
    f"❌ False Positives ({(df['_decision'] == 'false_positive').sum()})",
])

# ================= PENDING TAB =================
with tab_pending:
    pending = df[df["_decision"] == "pending"]
    pending = pending[pending["final_review_score"] >= min_score]
    if flag_types:
        pending = pending[pending[flag_types].any(axis=1)]
    if ai_only_toggle:
        pending = pending[(pending["review_confidence_score"] == 0) & (pending["final_review_score"] > 0)]
    pending = pending.sort_values("final_review_score", ascending=False)

    st.subheader(f"{len(pending)} records awaiting review")
    st.dataframe(pending[display_cols], width="stretch")

    st.divider()
    st.subheader("Inspect one record")

    if len(pending) > 0:
        record_id = st.selectbox(
            "Pick a record",
            pending.index.tolist(),
            format_func=lambda idx: f"{pending.loc[idx, 'AED_ID']} — {pending.loc[idx, 'BUILDING_NAME']} (score {pending.loc[idx, 'final_review_score']:.2f})",
            key="pending_select"
        )
        render_record_inspector(df, record_id, key_prefix="pending")
    else:
        st.info("No pending records match the current filters — lower the score threshold in the sidebar, or everything's been reviewed 🎉")

# ================= CONFIRMED TAB =================
with tab_confirmed:
    confirmed = df[df["_decision"] == "confirmed_real_issue"].sort_values("final_review_score", ascending=False)
    st.subheader(f"{len(confirmed)} records confirmed as real issues by a reviewer")
    if len(confirmed) > 0:
        st.dataframe(confirmed[display_cols], width="stretch")
        with st.expander("View full details for each confirmed record"):
            for _, record in confirmed.iterrows():
                st.markdown(f"**{record.get('AED_ID', '')}** — {record.get('BUILDING_NAME', '')}, {record.get('ROAD_NAME', '')}")
                for r in reasons_for(record):
                    st.write(f"  - {r}")
    else:
        st.info("No records confirmed yet — review some in the Pending tab.")

# ================= FALSE POSITIVE TAB =================
with tab_false:
    false_pos = df[df["_decision"] == "false_positive"].sort_values("final_review_score", ascending=False)
    st.subheader(f"{len(false_pos)} records marked as false positives by a reviewer")
    if len(false_pos) > 0:
        st.dataframe(false_pos[display_cols], width="stretch")
        with st.expander("View full details for each false-positive record"):
            for _, record in false_pos.iterrows():
                st.markdown(f"**{record.get('AED_ID', '')}** — {record.get('BUILDING_NAME', '')}, {record.get('ROAD_NAME', '')}")
                for r in reasons_for(record):
                    st.write(f"  - {r}")
    else:
        st.info("No false positives marked yet.")