"""
STEP 6 — AI anomaly layer (Isolation Forest)

Unsupervised model — learns what a "normal" AED record looks like across all 9,644
entries, without being told what a problem looks like, then flags whichever records sit
furthest from that pattern.

IMPORTANT: contamination=0.03 tells the model "assume roughly 3% of records are true
anomalies" — but that setting only affects model.predict()'s binary output (-1 = anomaly,
1 = normal). The continuous anomaly SCORE it also produces is NOT automatically limited to
3% of records — after min-max normalizing that score to 0-1, only the single most "normal"
record in the whole dataset lands exactly at 0, so almost every other record ends up with
some small positive score. Using "score > 0" as the flagging rule (an earlier version of
this script effectively did that downstream, in the dashboard) floods the queue with nearly
the entire dataset. Fix: use the model's actual binary anomaly prediction to decide WHO
gets flagged, and keep the continuous score only for ranking within that flagged group.
"""

import pandas as pd
from sklearn.ensemble import IsolationForest

df = pd.read_csv("data/aed_final_scored.csv")

features = pd.DataFrame()
features["lat"] = df["LATITUDE"]
features["lon"] = df["LONGITUDE"]
features["missing_postal"] = df["POSTAL_CODE"].isna().astype(int)
features["missing_road"] = df["ROAD_NAME"].isna().astype(int)
features["missing_hours"] = df["OPERATING_HOURS"].isna().astype(int)
features["building_length"] = df["BUILDING_NAME"].fillna("").str.len()
features["description_length"] = df["AED_LOCATION_DESCRIPTION"].fillna("").str.len()
features = features.fillna(0)

model = IsolationForest(contamination=0.03, random_state=42)
model.fit(features)

# predict() gives the actual binary decision the contamination setting controls:
# -1 = anomaly, 1 = normal. This is what should decide WHO is flagged.
raw_prediction = model.predict(features)
df["flag_ai_anomaly"] = (raw_prediction == -1)

# score_samples() gives a continuous score, useful for RANKING severity among flagged
# records, but not for deciding the flagged/not-flagged cutoff — that's predict()'s job.
raw_score = -model.score_samples(features)
min_score, max_score = raw_score.min(), raw_score.max()
df["ai_anomaly_score"] = (raw_score - min_score) / (max_score - min_score)

# Only the AI-flagged ~3% contribute to the blended score. Everyone else gets 0 from the
# AI side, so they don't sneak into the review queue just from normalization noise.
ai_contribution = df["ai_anomaly_score"] * df["flag_ai_anomaly"].astype(float)
df["final_review_score"] = (0.7 * df["review_confidence_score"] + 0.3 * ai_contribution).clip(upper=1.0)

df = df.sort_values("final_review_score", ascending=False)
df.to_csv("data/aed_final_with_ai.csv", index=False)

print(f"AI model flagged {df['flag_ai_anomaly'].sum()} records as anomalies (~3% target, contamination=0.03)")
print(f"Records flagged by rules only:        {int((df['review_confidence_score'] > 0).sum())}")
print(f"Records flagged by AI only (rules missed them): {int(((df['review_confidence_score'] == 0) & df['flag_ai_anomaly']).sum())}")
print(f"Total in review queue (final_review_score > 0): {int((df['final_review_score'] > 0).sum())}")
print()
print(df[["AED_ID", "review_confidence_score", "ai_anomaly_score", "flag_ai_anomaly", "final_review_score"]].head(10))