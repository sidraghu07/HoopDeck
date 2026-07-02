import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import dict_row
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score

from db.loader import load_team_seasons

TEAM_CSV = "data/csv/nba_team_season_stats.csv"
OUT_JSON = "data/output/lineup_model.json"
DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=nba_cards")

HOLDOUT_SEASONS = {"2023-24", "2024-25", "2025-26"}
FEATURES = [
    "avg_scoring", "avg_playmaking", "avg_defense", "avg_impact",
    "avg_overall", "star_power", "bench_overall",
]


def roster_features(sub_df: pd.DataFrame) -> dict:
    w = sub_df["minutes_weight"].values

    def wavg(col: str) -> float:
        return float(np.average(sub_df[col].values, weights=w))

    bench = sub_df.sort_values("minutes_weight", ascending=False).iloc[2:]
    bench_w = bench["minutes_weight"].values
    bench_overall = (
        float(np.average(bench["rating_overall"].values, weights=bench_w))
        if len(bench) and bench_w.sum() > 0
        else wavg("rating_overall")
    )

    return {
        "avg_scoring": wavg("rating_scoring"),
        "avg_playmaking": wavg("rating_playmaking"),
        "avg_defense": wavg("rating_defense"),
        "avg_impact": wavg("rating_impact"),
        "avg_overall": wavg("rating_overall"),
        "star_power": float(sub_df["rating_overall"].max()),
        "bench_overall": bench_overall,
    }


print("Loading team-season outcomes…")
teams = pd.read_csv(TEAM_CSV)

print("Loading player-season ratings from Postgres…")
with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT player_id, season, team, rating_overall, rating_scoring, "
            "rating_playmaking, rating_defense, rating_impact, games_played, pg_min "
            "FROM player_seasons"
        )
        rows = cur.fetchall()
players = pd.DataFrame(rows)
players["minutes_weight"] = players["pg_min"] * players["games_played"]
players = players[players["minutes_weight"] > 0]

print("Building roster feature vectors per real team-season…")
records = []
for (team, season), grp in players.groupby(["team", "season"]):
    if grp["minutes_weight"].sum() <= 0 or len(grp) < 3:
        continue
    records.append({"team": team, "season": season, **roster_features(grp)})

roster_df = pd.DataFrame(records)
merged = roster_df.merge(
    teams[["SEASON", "TEAM_ABBREVIATION", "NET_RATING", "W_PCT"]],
    left_on=["season", "team"], right_on=["SEASON", "TEAM_ABBREVIATION"], how="inner",
)
print(f"  Matched {len(merged)} team-seasons")

train = merged[~merged["season"].isin(HOLDOUT_SEASONS)]
test = merged[merged["season"].isin(HOLDOUT_SEASONS)]

X_train, y_train = train[FEATURES].values, train["NET_RATING"].values
model_a = Ridge(alpha=1.0)
model_a.fit(X_train, y_train)
r2_a_in = r2_score(y_train, model_a.predict(X_train))
r2_a_holdout = (
    r2_score(test["NET_RATING"].values, model_a.predict(test[FEATURES].values))
    if len(test) >= 10 else None
)
print(
    f"Stage A (roster -> net rating): n={len(train)}/{len(test)}  "
    f"R2(train)={r2_a_in:.3f}  R2(holdout)={r2_a_holdout}"
)

teams_train = teams[~teams["SEASON"].isin(HOLDOUT_SEASONS)]
teams_test = teams[teams["SEASON"].isin(HOLDOUT_SEASONS)]
Xb_train, yb_train = teams_train[["NET_RATING"]].values, teams_train["W_PCT"].values
Xb_test, yb_test = teams_test[["NET_RATING"]].values, teams_test["W_PCT"].values

model_b = Ridge(alpha=1.0)
model_b.fit(Xb_train, yb_train)
r2_b_in = r2_score(yb_train, model_b.predict(Xb_train))
r2_b_holdout = r2_score(yb_test, model_b.predict(Xb_test)) if len(Xb_test) else None
print(
    f"Stage B (net rating -> win%): n={len(Xb_train)}/{len(Xb_test)}  "
    f"R2(train)={r2_b_in:.3f}  R2(holdout)={r2_b_holdout}"
)

payload = {
    "stage_a": {
        "features": FEATURES,
        "coef": model_a.coef_.tolist(),
        "intercept": float(model_a.intercept_),
        "r2_in_sample": round(float(r2_a_in), 4),
        "r2_holdout": round(float(r2_a_holdout), 4) if r2_a_holdout is not None else None,
    },
    "stage_b": {
        "coef": float(model_b.coef_[0]),
        "intercept": float(model_b.intercept_),
        "r2_in_sample": round(float(r2_b_in), 4),
        "r2_holdout": round(float(r2_b_holdout), 4) if r2_b_holdout is not None else None,
    },
    "meta": {
        "n_team_seasons_matched": int(len(merged)),
        "holdout_seasons": sorted(HOLDOUT_SEASONS),
        "fitted_at": datetime.now(timezone.utc).isoformat(),
    },
}

os.makedirs("data/output", exist_ok=True)
with open(OUT_JSON, "w") as f:
    json.dump(payload, f, indent=2)
print(f"\n✓ Written → {OUT_JSON}")

load_team_seasons(teams, DATABASE_URL)

bulls_9697 = players[(players["team"] == "CHI") & (players["season"] == "1996-97")]
if not bulls_9697.empty:
    feats = roster_features(bulls_9697)
    net = model_a.predict([[feats[f] for f in FEATURES]])[0]
    win_pct = float(np.clip(model_b.predict([[net]])[0], 0, 1))
    real = teams[(teams["TEAM_ABBREVIATION"] == "CHI") & (teams["SEASON"] == "1996-97")].iloc[0]
    print(
        f"\nSanity check — 1996-97 Bulls: predicted net_rating={net:.2f} "
        f"predicted win%={win_pct:.3f}  (real: {real['NET_RATING']:.1f}, {real['W_PCT']:.3f})"
    )
