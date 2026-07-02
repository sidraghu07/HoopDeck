import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score

from rating_lib import MIN_GP, MIN_MPG, _pr, build_pool, parse_positions

STATS_CSV = "data/csv/nba_player_base_stats.csv"
OUT_JSON = "data/output/fitted_weights.json"

HOLDOUT_SEASONS = {"2023-24", "2024-25", "2025-26"}

POSITION_GROUPS = ["PG", "SG", "SF", "PF", "C", "Forward", "Guard", "Unknown"]

FIXED_IMPACT_WEIGHT = {
    "PG": 0.07, "SG": 0.12, "SF": 0.12, "PF": 0.21, "C": 0.22,
    "Forward": 0.14, "Guard": 0.08, "Unknown": 0.07,
}

BUCKET_FEATURES = {
    "scoring": [
        ("ts_pct", False, "TS_PCT"), ("efg_pct", False, "EFG_PCT"),
        ("fg3_pct", False, "FG3_PCT"), ("pts", False, "PTS"),
        ("usg_pct", False, "USG_PCT"), ("pct_uast_fgm", False, "PCT_UAST_FGM"),
    ],
    "playmaking": [
        ("ast_pct", False, "AST_PCT"), ("ast_to", False, "AST_TO"),
        ("tov_pct", True, "E_TOV_PCT"),
    ],
    "defense": [
        ("dreb_pct", False, "DREB_PCT"), ("stl", False, "STL"), ("blk", False, "BLK"),
    ],
    "availability": [
        ("availability_pct", False, "AVAILABILITY_PCT"),
    ],
}
FEATURE_COLS = [feat for feats in BUCKET_FEATURES.values() for feat, _, _ in feats]
FEATURE_SPECS = [(f, li, src) for feats in BUCKET_FEATURES.values() for f, li, src in feats]

print("Loading data…")
stats = pd.read_csv(STATS_CSV)
stats["POSITION_LIST"] = stats["POSITION"].apply(parse_positions)
stats["PRIMARY_POSITION"] = stats["POSITION_LIST"].apply(lambda lst: lst[0])

stats_f = stats[(stats["GP"] >= MIN_GP) & (stats["MIN"] >= MIN_MPG)].copy()
print(f"  Eligible rows: {len(stats_f):,} (from {len(stats):,})")

league_pools = {s: build_pool(g) for s, g in stats_f.groupby("SEASON")}

print("\nComputing raw stat percentiles…")
records = []
for _, row in stats_f.iterrows():
    pool = league_pools[row["SEASON"]]
    rec = {"position": row["PRIMARY_POSITION"], "season": row["SEASON"], "net_rating": row["NET_RATING"]}
    for feat, low_is_good, src in FEATURE_SPECS:
        rec[feat] = _pr(pool, feat, row.get(src, np.nan), low_is_good=low_is_good)
    records.append(rec)

df = pd.DataFrame(records)


def fit_position(group: pd.DataFrame) -> dict | None:
    train = group[~group["season"].isin(HOLDOUT_SEASONS)]
    test = group[group["season"].isin(HOLDOUT_SEASONS)]

    if len(train) < 30:
        return None

    X_train, y_train = train[FEATURE_COLS].values, train["net_rating"].values

    try:
        model = Ridge(alpha=1.0, positive=True)
        model.fit(X_train, y_train)
        coefs = model.coef_
    except Exception:
        model = Ridge(alpha=1.0)
        model.fit(X_train, y_train)
        coefs = np.clip(model.coef_, 0, None)

    coef_by_feature = dict(zip(FEATURE_COLS, coefs))
    bucket_totals = {
        bucket: sum(coef_by_feature[feat] for feat, _, _ in feats)
        for bucket, feats in BUCKET_FEATURES.items()
    }
    total = sum(bucket_totals.values())
    fitted_weights = (
        {b: 1.0 / len(bucket_totals) for b in bucket_totals}
        if total <= 0
        else {b: v / total for b, v in bucket_totals.items()}
    )

    r2_in = r2_score(y_train, model.predict(X_train))
    r2_holdout = None
    if len(test) >= 10:
        r2_holdout = r2_score(test["net_rating"].values, model.predict(test[FEATURE_COLS].values))

    return {
        "fitted_weights": fitted_weights,
        "r2_in_sample": round(float(r2_in), 4),
        "r2_holdout": round(float(r2_holdout), 4) if r2_holdout is not None else None,
        "n_train": int(len(train)),
        "n_holdout": int(len(test)),
    }


def apply_fixed_impact(fitted_weights: dict, position: str) -> dict:
    impact_w = FIXED_IMPACT_WEIGHT.get(position, 0.10)
    remaining = 1.0 - impact_w
    return {
        **{b: round(float(v) * remaining, 4) for b, v in fitted_weights.items()},
        "impact": round(impact_w, 4),
    }


print("\nFitting scoring/playmaking/defense/availability weights (target: NET_RATING)…")
print("'impact' keeps its fixed, hand-set weight.\n")
fitted: dict = {}
for position in POSITION_GROUPS:
    result = fit_position(df[df["position"] == position])
    if result is None:
        print(f"  {position:8s}: skipped (too few eligible rows)")
        continue
    weights = apply_fixed_impact(result["fitted_weights"], position)
    fitted[position] = {k: round(float(v), 4) for k, v in weights.items()}
    r2h = f"{result['r2_holdout']:.3f}" if result["r2_holdout"] is not None else "n/a"
    rounded = {k: round(v, 2) for k, v in weights.items()}
    print(
        f"  {position:8s}: n={result['n_train']:>5}/{result['n_holdout']:<4}  "
        f"R2(train)={result['r2_in_sample']:.3f}  R2(holdout)={r2h}  weights={rounded}"
    )

missing = [p for p in POSITION_GROUPS if p not in fitted]
if missing:
    print(f"\nBackfilling {missing} from the pooled (all-position) fit…")
    pooled = fit_position(df)
    for p in missing:
        base = pooled["fitted_weights"] if pooled else {b: 1.0 / len(BUCKET_FEATURES) for b in BUCKET_FEATURES}
        fitted[p] = {k: round(float(v), 4) for k, v in apply_fixed_impact(base, p).items()}

payload = {
    **fitted,
    "meta": {
        "target": "NET_RATING",
        "fitted_buckets": {b: [f for f, _, _ in feats] for b, feats in BUCKET_FEATURES.items()},
        "fixed_impact_weight": FIXED_IMPACT_WEIGHT,
        "holdout_seasons": sorted(HOLDOUT_SEASONS),
        "fitted_at": datetime.now(timezone.utc).isoformat(),
        "caveat": (
            "Fit on raw stat percentiles (not the pre-aggregated buckets) to "
            "avoid collinearity between composite features. OFF_RATING/"
            "DEF_RATING/NET_RATING excluded since NET_RATING is defined from "
            "the first two. 'impact' is not regression-fit at all — every "
            "candidate impact stat (PIE, PLUS_MINUS, CLUTCH_PLUS_MINUS, "
            "W_PCT) is itself a flavor of on-court team outcome, so it kept "
            "swallowing most of the fitted weight. It uses a fixed, hand-set "
            "weight instead; scoring/playmaking/defense/availability split "
            "the remaining budget by fitted coefficient."
        ),
    },
}

with open(OUT_JSON, "w") as f:
    json.dump(payload, f, indent=2)

print(f"\n✓ Written → {OUT_JSON}")
