import pandas as pd
import numpy as np
import json
import os
import warnings
warnings.filterwarnings("ignore")

from rating_lib import (
    MIN_GP, MIN_MPG, build_pool, compute_subscores, parse_positions, percentile_rating, safe,
)
from db.loader import load_to_postgres

STATS_CSV       = "data/csv/nba_player_base_stats.csv"
SHOTS_ZONES_CSV = "data/csv/nba_shot_zone_summary.csv"
OUT_JSON        = "data/output/players.json"
FITTED_WEIGHTS_JSON = "data/output/fitted_weights.json"
DATABASE_URL    = os.environ.get("DATABASE_URL", "dbname=nba_cards")

MIN_ZONE_ATTEMPTS = 20

print("Loading data…")
stats = pd.read_csv(STATS_CSV)
zones = pd.read_csv(SHOTS_ZONES_CSV)
print(f"  Stats : {stats.shape[0]:,} rows")
print(f"  Zones : {zones.shape[0]:,} rows")


ZONES = [
    "Restricted Area",
    "In The Paint (Non-RA)",
    "Mid-Range",
    "Left Corner 3",
    "Right Corner 3",
    "Above the Break 3",
]
THREE_ZONES = {"Left Corner 3", "Right Corner 3", "Above the Break 3"}

def zone_slug(z: str) -> str:
    return (z.lower()
             .replace(" ", "_")
             .replace("(", "").replace(")", "")
             .replace("-", "_"))

print("\nBuilding hot-zone profiles…")

zones_basic = (
    zones[zones["SHOT_ZONE_BASIC"].isin(ZONES)]
    .groupby(["PLAYER_ID", "SEASON", "SHOT_ZONE_BASIC"], as_index=False)
    .agg(MAKES=("MAKES", "sum"), MISSES=("MISSES", "sum"), FGA=("FGA", "sum"))
)
zones_basic["FG_PCT"] = (zones_basic["MAKES"] / zones_basic["FGA"]).round(4)

total_fga_by_player_season = (
    zones_basic.groupby(["PLAYER_ID", "SEASON"])["FGA"].sum()
    .reset_index(name="total_zone_fga")
)
zones_basic = zones_basic.merge(total_fga_by_player_season, on=["PLAYER_ID", "SEASON"])
zones_basic["freq_pct"] = (zones_basic["FGA"] / zones_basic["total_zone_fga"]).round(4)

zone_pools = {}
for (season, zone), grp in zones_basic.groupby(["SEASON", "SHOT_ZONE_BASIC"]):
    qualified = grp[grp["FGA"] >= MIN_ZONE_ATTEMPTS]
    zone_pools[(season, zone)] = {
        "fga":    qualified["FGA"],
        "fg_pct": qualified["FG_PCT"],
    }

def build_zone_profile(pid, season, grp_df) -> dict:
    profile = {}
    for _, row in grp_df.iterrows():
        zone = row["SHOT_ZONE_BASIC"]
        slug = zone_slug(zone)
        pool = zone_pools.get((season, zone))

        insufficient_sample = pool is None or row["FGA"] < MIN_ZONE_ATTEMPTS
        if not insufficient_sample:
            vol_rating = percentile_rating(pool["fga"],    row["FGA"])
            eff_rating = percentile_rating(pool["fg_pct"], row["FG_PCT"])
        else:
            vol_rating = 40
            eff_rating = 40

        hot_score = int(round(0.5 * vol_rating + 0.5 * eff_rating))

        profile[slug] = {
            "attempts":            int(row["FGA"]),
            "makes":               int(row["MAKES"]),
            "misses":              int(row["MISSES"]),
            "fg_pct":              safe(row["FG_PCT"]),
            "freq_pct":            safe(row["freq_pct"]),
            "is_3pt":              zone in THREE_ZONES,
            "volume_rating":       vol_rating,
            "efficiency_rating":   eff_rating,
            "hot_score":           hot_score,
            "is_hot_zone":         (vol_rating >= 60 and eff_rating >= 60),
            "insufficient_sample": insufficient_sample,
        }

    for z in ZONES:
        s = zone_slug(z)
        if s not in profile:
            profile[s] = {
                "attempts": 0, "makes": 0, "misses": 0, "fg_pct": None,
                "freq_pct": 0.0, "is_3pt": z in THREE_ZONES,
                "volume_rating": 40, "efficiency_rating": 40,
                "hot_score": 40, "is_hot_zone": False,
                "insufficient_sample": True,
            }
    return profile

zone_groups = {key: grp for key, grp in zones_basic.groupby(["PLAYER_ID", "SEASON"])}


stats["POSITION_LIST"]    = stats["POSITION"].apply(parse_positions)
stats["PRIMARY_POSITION"] = stats["POSITION_LIST"].apply(lambda lst: lst[0])

stats_f = stats[(stats["GP"] >= MIN_GP) & (stats["MIN"] >= MIN_MPG)].copy()
print(f"  Players after GP/MIN filter: {len(stats_f):,} (from {len(stats):,})")


_FIRST_OPTION_PCTILE   = 0.95
_SECOND_STAR_PCTILE    = 0.98
_ALL_STAR_PCTILE       = 0.90
_STARTER_PCTILE        = 0.70
_ROTATION_PCTILE       = 0.40
_MASSIVE_DROP_PCTILE   = 0.85
_ALL_STAR_PERSIST_PCTILE = 0.60
_MIN_AVAIL             = 0.40
_MIN_AVAIL_PROMOTE     = 0.55
_MIN_MPG_TIER          = 10.0
_STARTER_FLOOR_MPG     = 28.0
_ROTATION_FLOOR_MPG    = 15.0
_FLOOR_MIN_GP          = 41

def _zscore(s: pd.Series) -> pd.Series:
    std = s.std(ddof=0)
    if std == 0 or pd.isna(std):
        return s * 0
    return (s - s.mean()) / std

def _recompute_tiers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["PIE", "NET_RATING", "TS_PCT", "USG_PCT", "AST_PCT",
                "STL", "BLK", "AST_TO", "E_TOV_PCT",
                "PCT_UAST_FGM", "CLUTCH_PLUS_MINUS"]:
        if col not in df.columns:
            df[col] = 0.0

    df["IMPACT_SCORE"]  = float("nan")
    df["IMPACT_PCTILE"] = float("nan")
    df["TIER"]          = "Bench"

    sorted_seasons = sorted(df["SEASON"].unique())

    for season in sorted_seasons:
        mask  = df["SEASON"] == season
        group = df[mask]
        eligible = (
            (group["AVAILABILITY_PCT"] >= _MIN_AVAIL)
            & (group["MIN"] >= _MIN_MPG_TIER)
        )
        elig_idx = group.index[eligible]
        if len(elig_idx) == 0:
            continue
        e = group.loc[elig_idx]

        impact = (
            _zscore(e["PIE"])              * 0.22
            + _zscore(e["NET_RATING"])     * 0.15
            + _zscore(e["TS_PCT"])         * 0.08
            + _zscore(e["USG_PCT"])        * 0.10
            + _zscore(e["AST_PCT"])        * 0.10
            + _zscore(e["STL"])            * 0.09
            + _zscore(e["BLK"])            * 0.06
            + _zscore(e["AST_TO"])         * 0.06
            - _zscore(e["E_TOV_PCT"])      * 0.04
            + _zscore(e["PCT_UAST_FGM"])   * 0.04
            + _zscore(e["CLUTCH_PLUS_MINUS"]) * 0.06
        )

        pos = e["POSITION"] if "POSITION" in e.columns else pd.Series("Unknown", index=elig_idx)
        usg = e["USG_PCT"]
        ast = e["AST_PCT"]
        heliocentric  = (usg >= 0.26) & (ast >= 0.25)
        scoring_alpha = (usg >= 0.28) & (ast >= 0.18) & pos.isin(["PG", "SG", "SF"])
        rim_anchor    = (pos == "C")  & (usg < 0.18)  & (ast < 0.12)
        impact[heliocentric]                   += 0.50
        impact[scoring_alpha & ~heliocentric]  += 0.50
        impact[rim_anchor]                     -= 0.45

        total_min  = e["MIN"] * e["GP"]
        min_weight = (np.log1p(total_min) / np.log1p(2000)).clip(0, 1)
        impact     = impact * min_weight

        df.loc[elig_idx, "IMPACT_SCORE"]  = impact.values
        df.loc[elig_idx, "IMPACT_PCTILE"] = impact.rank(pct=True).values

    previous_first_options: set = set()
    previous_all_stars:     set = set()

    for season in sorted_seasons:
        season_mask   = df["SEASON"] == season
        eligible_mask = season_mask & df["IMPACT_PCTILE"].notna()
        elig_idx      = df[eligible_mask].index
        demoted_this:  set = set()

        if len(elig_idx) == 0:
            continue

        pctiles = df.loc[elig_idx, "IMPACT_PCTILE"]
        tier    = pd.Series("Bench", index=elig_idx, dtype="object")
        tier.loc[pctiles >= _ROTATION_PCTILE]     = "Rotation"
        tier.loc[pctiles >= _STARTER_PCTILE]      = "Starter"
        tier.loc[pctiles >= _ALL_STAR_PCTILE]     = "All-Star"
        tier.loc[pctiles >= _FIRST_OPTION_PCTILE] = "Franchise Player"

        for idx in elig_idx:
            name   = df.loc[idx, "PLAYER_NAME"]
            pctile = df.loc[idx, "IMPACT_PCTILE"]
            if name in previous_first_options:
                if pctile >= _MASSIVE_DROP_PCTILE:
                    if tier.loc[idx] != "Franchise Player":
                        tier.loc[idx] = "Franchise Player"
                else:
                    print(f"    [{season}] {name}: lost Franchise Player (pctile={pctile:.2f})")
            elif name in previous_all_stars and tier.loc[idx] not in ("Franchise Player", "All-Star"):
                if pctile >= _ALL_STAR_PERSIST_PCTILE:
                    tier.loc[idx] = "All-Star"
                else:
                    print(f"    [{season}] {name}: lost All-Star (pctile={pctile:.2f})")

        df.loc[elig_idx, "TIER"] = tier

        fo_mask    = eligible_mask & (df["TIER"] == "Franchise Player")
        for team, tdf in df[fo_mask].groupby("TEAM_ABBREVIATION"):
            if len(tdf) <= 1:
                continue
            best = tdf["IMPACT_SCORE"].idxmax()
            for didx, drow in tdf.drop(best).iterrows():
                if drow["IMPACT_PCTILE"] >= _SECOND_STAR_PCTILE:
                    print(
                        f"    [{season}] {drow['PLAYER_NAME']}: kept as a second "
                        f"Franchise Player on {team} (pctile={drow['IMPACT_PCTILE']:.2f})"
                    )
                    continue
                df.loc[didx, "TIER"] = "All-Star"
                demoted_this.add(drow["PLAYER_NAME"])

        for idx in df[eligible_mask].index:
            t   = df.loc[idx, "TIER"]
            pts = df.loc[idx, "PTS"]
            usg = df.loc[idx, "USG_PCT"]
            if t == "Franchise Player" and not ((pts >= 17) or (usg >= 0.27)):
                df.loc[idx, "TIER"] = "All-Star"
                print(f"    [{season}] {df.loc[idx,'PLAYER_NAME']}: Franchise Player→All-Star gate ({pts:.1f}pts, {usg:.1%}usg)")
            elif t == "All-Star" and not ((pts >= 14) or (usg >= 0.24)):
                df.loc[idx, "TIER"] = "Starter"
                print(f"    [{season}] {df.loc[idx,'PLAYER_NAME']}: All-Star→Starter gate ({pts:.1f}pts, {usg:.1%}usg)")

        for idx in df[eligible_mask].index:
            t   = df.loc[idx, "TIER"]
            mpg = df.loc[idx, "MIN"]
            gp  = df.loc[idx, "GP"]
            if t in ("Rotation", "Bench") and mpg >= _STARTER_FLOOR_MPG and gp >= _FLOOR_MIN_GP:
                df.loc[idx, "TIER"] = "Starter"
            elif t == "Bench" and mpg >= _ROTATION_FLOOR_MPG and gp >= _FLOOR_MIN_GP:
                df.loc[idx, "TIER"] = "Rotation"

        fo_after = eligible_mask & (df["TIER"] == "Franchise Player")
        teams_with_fo = set(df[fo_after]["TEAM_ABBREVIATION"].dropna())
        for team, tdf in df[eligible_mask].groupby("TEAM_ABBREVIATION"):
            if team in teams_with_fo:
                continue

            primary = tdf[
                (tdf["TIER"] == "All-Star")
                & (tdf["IMPACT_PCTILE"] >= 0.88)
                & (tdf["PTS"] >= 15)
                & (tdf["AVAILABILITY_PCT"] >= _MIN_AVAIL_PROMOTE)
            ]
            if not primary.empty:
                best_idx = primary["IMPACT_PCTILE"].idxmax()
                df.loc[best_idx, "TIER"] = "Franchise Player"
                print(
                    f"    [{season}] {df.loc[best_idx,'PLAYER_NAME']}: "
                    f"promoted to Franchise Player (impact: "
                    f"{df.loc[best_idx,'PTS']:.1f}pts, pctile={df.loc[best_idx,'IMPACT_PCTILE']:.2f})"
                )

        previous_first_options = set(
            df[season_mask & (df["TIER"] == "Franchise Player")]["PLAYER_NAME"]
        )
        previous_all_stars = set(
            df[season_mask & (df["TIER"] == "All-Star")]["PLAYER_NAME"]
        )

    return df

print("\nRe-computing tiers with fixed logic…")
stats_f = _recompute_tiers(stats_f)
tier_counts = stats_f["TIER"].value_counts()
print(f"  Tier breakdown:\n{tier_counts.to_string()}")
for name in ["T.J. McConnell", "Nikola Jokic", "Pascal Siakam", "Scottie Barnes", "Brandon Ingram"]:
    rows = stats_f[stats_f["PLAYER_NAME"] == name][["PLAYER_NAME","SEASON","TIER","PTS","USG_PCT"]].tail(2)
    if not rows.empty:
        print(f"\n  {name}:")
        print(rows.to_string(index=False))


print("\nBuilding per-season percentile pools…")
league_pools = {s: build_pool(g) for s, g in stats_f.groupby("SEASON")}

print("Building per-season-per-position percentile pools…")
stats_exploded = stats_f.explode("POSITION_LIST").rename(columns={"POSITION_LIST": "POS"})
position_pools = {
    (season, pos): build_pool(g)
    for (season, pos), g in stats_exploded.groupby(["SEASON", "POS"])
}


_FALLBACK_POSITION_WEIGHTS = {
    "PG":      (0.38, 0.37, 0.13, 0.07, 0.05),
    "SG":      (0.43, 0.20, 0.20, 0.12, 0.05),
    "SF":      (0.36, 0.20, 0.27, 0.12, 0.05),
    "PF":      (0.28, 0.14, 0.32, 0.21, 0.05),
    "C":       (0.28, 0.13, 0.32, 0.22, 0.05),
    "Forward": (0.33, 0.18, 0.30, 0.14, 0.05),
    "Guard":   (0.38, 0.30, 0.19, 0.08, 0.05),
    "Unknown": (0.38, 0.28, 0.22, 0.07, 0.05),
}

def _load_position_weights() -> dict:
    if not os.path.exists(FITTED_WEIGHTS_JSON):
        print(
            f"\n  [warn] {FITTED_WEIGHTS_JSON} not found — using hardcoded fallback "
            "position weights. Run `python data/fit_weights.py` to calibrate these "
            "from data instead."
        )
        return _FALLBACK_POSITION_WEIGHTS
    with open(FITTED_WEIGHTS_JSON) as f:
        fitted = json.load(f)
    weights = {
        pos: (w["scoring"], w["playmaking"], w["defense"], w["impact"], w["availability"])
        for pos, w in fitted.items()
        if pos != "meta"
    }
    print(f"\n  Loaded fitted position weights from {FITTED_WEIGHTS_JSON} "
          f"(fitted_at={fitted.get('meta', {}).get('fitted_at', '?')})")
    return weights

POSITION_WEIGHTS = _load_position_weights()

def get_position_weights(position_list: list) -> tuple:
    for pos in position_list:
        if pos in POSITION_WEIGHTS:
            return POSITION_WEIGHTS[pos]
    primary = position_list[0] if position_list else "Unknown"
    for key in POSITION_WEIGHTS:
        if primary.startswith(key):
            return POSITION_WEIGHTS[key]
    return POSITION_WEIGHTS["Unknown"]


TIER_BOOSTS = {
    "Franchise Player": 7,
    "All-Star":     1,
    "Starter":      0,
    "Rotation":     0,
    "Bench":        0,
}

def ratings_from_row(row, p: dict, position_list=None) -> dict:
    w_scoring, w_play, w_def, w_impact, w_avail = (
        get_position_weights(position_list)
        if position_list is not None
        else (0.38, 0.28, 0.22, 0.07, 0.05)
    )

    sub = compute_subscores(row, p, position_list)
    scoring, playmaking, defense, impact, availability = (
        sub["scoring"], sub["playmaking"], sub["defense"], sub["impact"], sub["availability"]
    )

    overall = int(round(
        w_scoring * scoring      +
        w_play    * playmaking   +
        w_def     * defense      +
        w_impact  * impact       +
        w_avail   * availability
    ))

    tier = row.get("TIER", "")
    overall += TIER_BOOSTS.get(tier, 0)

    if row["USG_PCT"] >= 32 and row["AST_PCT"] >= 35:
        overall += 2
    if row["PTS"] >= 30 and row["AST"] >= 7:
        overall += 2
    if row["USG_PCT"] >= 35:
        overall += 1
    if row["TS_PCT"] >= 0.62:
        overall += 1

    if row["STL"] + row["BLK"] >= 3.0:
        overall += 2
    elif row["STL"] + row["BLK"] >= 2.0:
        overall += 1

    if row["DREB_PCT"] >= 25 and row["BLK"] >= 1.5:
        overall += 1

    if row["NET_RATING"] >= 10:
        overall += 2
    if row["PLUS_MINUS"] >= 8:
        overall += 1
    if row["W_PCT"] >= 0.70:
        overall += 1

    clutch_pm = row.get("CLUTCH_PLUS_MINUS", np.nan)
    if not pd.isna(clutch_pm) and clutch_pm >= 5:
        overall += 1

    if row["AVAILABILITY_PCT"] < 0.60:
        overall -= 1

    clamp = lambda x: max(40, min(99, x))
    return {
        "overall":    clamp(overall),
        "scoring":    clamp(scoring),
        "playmaking": clamp(playmaking),
        "defense":    clamp(defense),
        "impact":     clamp(impact),
    }


print("\nBuilding player cards…")
cards = []

for _, row in stats_f.iterrows():
    season = row["SEASON"]
    pid    = int(row["PLAYER_ID"])

    grp = zone_groups.get((pid, season))
    if grp is not None:
        zone_prof      = build_zone_profile(pid, season, grp)
        total_zone_fga = int(grp["FGA"].sum())
    else:
        zone_prof = {zone_slug(z): {
            "attempts": 0, "makes": 0, "misses": 0, "fg_pct": None, "freq_pct": 0.0,
            "is_3pt": z in THREE_ZONES, "volume_rating": 40, "efficiency_rating": 40,
            "hot_score": 40, "is_hot_zone": False, "insufficient_sample": True,
        } for z in ZONES}
        total_zone_fga = 0

    hottest_zone = max(zone_prof.items(), key=lambda kv: kv[1]["hot_score"])[0] if zone_prof else None

    league_rating      = ratings_from_row(row, league_pools[season], row["POSITION_LIST"])
    ratings_by_position = {}
    for pos in row["POSITION_LIST"]:
        pool = position_pools.get((season, pos))
        if pool is not None:
            ratings_by_position[pos] = ratings_from_row(row, pool, [pos])

    card = {
        "player_id":   pid,
        "player_name": row["PLAYER_NAME"],
        "season":      season,
        "team":        row["TEAM_ABBREVIATION"],
        "age":         safe(row["AGE"]),

        "positions":        row["POSITION_LIST"],
        "primary_position": row["PRIMARY_POSITION"],

        "tier": row.get("TIER", None),

        "availability": {
            "games_played":     int(row["GP"]),
            "scheduled_games":  safe(row.get("SCHEDULED_GAMES")),
            "availability_pct": safe(row.get("AVAILABILITY_PCT")),
            "roster_status":    row.get("ROSTERSTATUS"),
        },

        "ratings":             league_rating,
        "ratings_by_position": ratings_by_position,

        "per_game": {
            "pts":  safe(row["PTS"]),
            "reb":  safe(row["REB"]),
            "ast":  safe(row["AST"]),
            "stl":  safe(row["STL"]),
            "blk":  safe(row["BLK"]),
            "tov":  safe(row["TOV"]),
            "min":  safe(row["MIN"]),
            "oreb": safe(row["OREB"]),
            "dreb": safe(row["DREB"]),
        },

        "scoring": {
            "fg_pct":        safe(row["FG_PCT"]),
            "fg3_pct":       safe(row["FG3_PCT"]),
            "ft_pct":        safe(row["FT_PCT"]),
            "efg_pct":       safe(row["EFG_PCT"]),
            "ts_pct":        safe(row["TS_PCT"]),
            "fg3a_per_game": safe(row["FG3A"]),
            "fga_per_game":  safe(row["FGA"]),
            "pct_uast_fgm":  safe(row.get("PCT_UAST_FGM")),
        },

        "advanced": {
            "off_rating": safe(row["OFF_RATING"]),
            "def_rating": safe(row["DEF_RATING"]),
            "net_rating": safe(row["NET_RATING"]),
            "ast_pct":    safe(row["AST_PCT"]),
            "ast_to":     safe(row["AST_TO"]),
            "usg_pct":    safe(row["USG_PCT"]),
            "oreb_pct":   safe(row["OREB_PCT"]),
            "dreb_pct":   safe(row["DREB_PCT"]),
            "pie":        safe(row["PIE"]),
            "pace":       safe(row["PACE"]),
            "plus_minus": safe(row["PLUS_MINUS"]),
            "e_tov_pct":  safe(row["E_TOV_PCT"]),
        },

        "clutch": {
            "clutch_plus_minus": safe(row.get("CLUTCH_PLUS_MINUS")),
        },

        "shot_zones":        zone_prof,
        "hottest_zone":      hottest_zone,
        "total_charted_fga": total_zone_fga,
    }

    cards.append(card)

cards.sort(key=lambda c: (-c["ratings"]["overall"], -c["ratings"]["impact"], c["player_name"], c["season"]))

from collections import defaultdict as _defaultdict

_by_player: dict = _defaultdict(list)
for _i, _c in enumerate(cards):
    _by_player[_c["player_id"]].append((_c["season"], _i))

for _season_idx_list in _by_player.values():
    _season_idx_list.sort()
    _prev_raw: int | None = None
    for _season_str, _idx in _season_idx_list:
        _card  = cards[_idx]
        _avail = _card["availability"]["availability_pct"] or 1.0
        _raw   = _card["ratings"]["overall"]
        if _prev_raw is not None:
            _blended = int(round(_avail * _raw + (1.0 - _avail) * _prev_raw))
            _blended = max(40, min(99, _blended))
            if _blended != _raw:
                cards[_idx]["ratings"] = dict(_card["ratings"], overall=_blended)
        _prev_raw = _raw

OVR_TIER_FLOOR = 80
for _card in cards:
    if _card["tier"] in ("Franchise Player", "All-Star") and _card["ratings"]["overall"] < OVR_TIER_FLOOR:
        _card["tier"] = "Starter"

seasons_list = sorted({c["season"] for c in cards})
print(f"\n✓ {len(cards):,} player-season cards across {seasons_list}")


os.makedirs("data/output", exist_ok=True)
payload = {
    "meta": {
        "total_cards":                      len(cards),
        "seasons":                          seasons_list,
        "min_games_filter":                 MIN_GP,
        "min_mpg_filter":                   MIN_MPG,
        "min_zone_attempts_for_percentile": MIN_ZONE_ATTEMPTS,
        "tier_system": (
            "5 tiers: Franchise Player / All-Star / Starter / Rotation / Bench. "
            "Assigned chronologically with tier persistence (injured players keep "
            "their role) and cross-season overall blending (missed games penalise "
            "the OVR rating by pulling it toward the previous season's baseline)."
        ),
        "shot_zone_note": (
            "shot_zones.*.attempts/makes/misses/fg_pct reflect all charted shots. "
            "freq_pct = share of the player's own shot diet from that zone. "
            "volume_rating/efficiency_rating are percentiles vs league peers "
            "with >= min_zone_attempts in that zone/season. "
            "is_hot_zone = above-average on both volume AND efficiency."
        ),
        "position_note": (
            "ratings_by_position gives a separate rating block per position the "
            "player is eligible at, computed against position-filtered peers. "
            "Top-level ratings use position-aware overall weights."
        ),
        "new_fields_note": (
            "clutch.clutch_plus_minus: +/- in last-5-minutes situations. "
            "scoring.pct_uast_fgm: % of FGM that were unassisted (shot creation). "
            "DEF_WS/STL_PCT/BLK_PCT excluded — NBA API returns 0.0 sentinel values "
            "for uncalculated rate stats; raw STL/BLK per game used instead."
        ),
        "position_weights": {
            pos: dict(zip(["scoring", "playmaking", "defense", "impact", "availability"], w))
            for pos, w in POSITION_WEIGHTS.items()
        },
    },
    "players": cards,
}

with open(OUT_JSON, "w") as f:
    json.dump(payload, f, indent=2)

size_kb = os.path.getsize(OUT_JSON) / 1024
print(f"  Written → {OUT_JSON}  ({size_kb:,.0f} KB)")


load_to_postgres(cards, DATABASE_URL)


print("\n── Top 30 overall (latest season) ──")
latest = max(seasons_list)
top5   = [c for c in cards if c["season"] == latest][:30]
for c in top5:
    r     = c["ratings"]
    pg    = c["per_game"]
    avail = c["availability"]
    print(f"  {c['player_name']:25s} {c['team']}  Tier={c['tier']}  "
          f"OVR={r['overall']}  SHT={r['scoring']} PLY={r['playmaking']} "
          f"DEF={r['defense']} IMP={r['impact']}  "
          f"| {pg['pts']}/{pg['reb']}/{pg['ast']}  "
          f"| Avail={avail['availability_pct']}  "
          f"| Hot zone: {c['hottest_zone']}")

print("\n── SGA season progression ──")
sga = [c for c in cards if c["player_name"] == "Shai Gilgeous-Alexander"]
for c in sorted(sga, key=lambda x: x["season"]):
    r = c["ratings"]
    print(f"  {c['season']}  Tier={c['tier']}  OVR={r['overall']}  "
          f"SHT={r['scoring']} PLY={r['playmaking']} DEF={r['defense']} IMP={r['impact']}  "
          f"| Hot zone: {c['hottest_zone']}")


def debug_player(name, season=None):
    rows = stats_f[stats_f["PLAYER_NAME"] == name]
    if season:
        rows = rows[rows["SEASON"] == season]
    for _, row in rows.iterrows():
        p        = league_pools[row["SEASON"]]
        pos_list = row["POSITION_LIST"]
        weights  = get_position_weights(pos_list)
        labels   = ["scr", "ply", "def", "imp", "avl"]
        w_str    = "  ".join(f"{l}={v}" for l, v in zip(labels, weights))
        print(f"\n{name} — {row['SEASON']}  pos={pos_list}  tier={row.get('TIER')}  weights=({w_str})")
        p_local = p
        print(f"  TS%={row['TS_PCT']:.3f}  EFG%={row['EFG_PCT']:.3f}  3P%={row['FG3_PCT']:.3f}  "
              f"UAST%={row.get('PCT_UAST_FGM','N/A')}")
        print(f"  AST%={row['AST_PCT']:.3f}  AST/TO={row['AST_TO']:.2f}  TOV%={row['E_TOV_PCT']:.3f}")
        print(f"  DEF_RTG={row['DEF_RATING']:.1f}  DREB%={row['DREB_PCT']:.3f}  STL={row['STL']:.1f}  BLK={row['BLK']:.1f}")
        print(f"  NET_RTG={row['NET_RATING']:.1f}  PIE={row['PIE']:.3f}  PTS={row['PTS']:.1f}  "
              f"CLUTCH_PM={row.get('CLUTCH_PLUS_MINUS','N/A')}")
        r = ratings_from_row(row, p, pos_list)
        print(f"  → OVR={r['overall']}  SHT={r['scoring']} PLY={r['playmaking']} "
              f"DEF={r['defense']} IMP={r['impact']}")


debug_player("Jamal Murray",          "2025-26")
debug_player("Anthony Edwards",       "2025-26")
debug_player("Nikola Jokić",          "2025-26")
