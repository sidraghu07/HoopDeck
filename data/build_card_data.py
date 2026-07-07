import pandas as pd
import numpy as np
import json
import os
import warnings
warnings.filterwarnings("ignore")

from rating_lib import (
    MIN_GP_BY_LEAGUE, MIN_MPG, PLAYOFF_MIN_GP, build_pool, compute_subscores, parse_positions,
    percentile_rating, safe,
)
from db.loader import load_playoff_seasons_to_postgres, load_to_postgres

STATS_CSVS = {
    "NBA":  "data/csv/nba_player_base_stats.csv",
    "WNBA": "data/csv/wnba_player_base_stats.csv",
}
PLAYOFF_STATS_CSVS = {
    "NBA":  "data/csv/nba_player_playoff_stats.csv",
    "WNBA": "data/csv/wnba_player_playoff_stats.csv",
}
SHOTS_ZONES_CSVS = {
    "NBA":  "data/csv/nba_shot_zone_summary.csv",
    "WNBA": "data/csv/wnba_shot_zone_summary.csv",
}
OUT_JSON        = "data/output/players.json"
FITTED_WEIGHTS_JSONS = {
    "NBA":  "data/output/fitted_weights_nba.json",
    "WNBA": "data/output/fitted_weights_wnba.json",
}
DATABASE_URL    = os.environ.get("DATABASE_URL", "dbname=nba_cards")

MIN_ZONE_ATTEMPTS = 20

print("Loading data…")
stats_frames = []
zones_frames = []
for league, path in STATS_CSVS.items():
    if not os.path.exists(path):
        print(f"  [skip] {path} not found — no {league} data yet")
        continue
    df = pd.read_csv(path, dtype={"SEASON": str})
    df["LEAGUE"] = league
    stats_frames.append(df)
    zpath = SHOTS_ZONES_CSVS[league]
    if os.path.exists(zpath):
        zdf = pd.read_csv(zpath, dtype={"SEASON": str})
        zdf["LEAGUE"] = league
        zones_frames.append(zdf)

if not stats_frames:
    raise SystemExit("No player stats CSVs found — run generate_player_dataset.py first")

stats = pd.concat(stats_frames, ignore_index=True)
zones = pd.concat(zones_frames, ignore_index=True) if zones_frames else pd.DataFrame()
print(f"  Stats : {stats.shape[0]:,} rows ({stats['LEAGUE'].value_counts().to_dict()})")
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

_min_gp_threshold = stats["LEAGUE"].map(MIN_GP_BY_LEAGUE)
stats_f = stats[(stats["GP"] >= _min_gp_threshold) & (stats["MIN"] >= MIN_MPG)].copy()
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

# "Played about half the season" games-count floor — an absolute number, so it
# has to scale with each league's season length (NBA 82 games vs WNBA ~40).
FLOOR_MIN_GP_BY_LEAGUE = {"NBA": 41, "WNBA": 20}

# Position groups behind the tiering impact bonuses below. NBA uses its 5-way
# taxonomy; WNBA basketball-reference only distinguishes G/F/C.
SCORING_ALPHA_POSITIONS = {"NBA": ["PG", "SG", "SF"], "WNBA": ["G"]}
RIM_ANCHOR_POSITIONS    = {"NBA": ["C"], "WNBA": ["C"]}

def _zscore(s: pd.Series) -> pd.Series:
    std = s.std(ddof=0)
    if std == 0 or pd.isna(std):
        return s * 0
    return (s - s.mean()) / std

def _recompute_tiers(df: pd.DataFrame) -> pd.DataFrame:
    # Cross-season "did this player's tier persist" state below must never mix
    # leagues — WNBA and NBA season strings sort interleaved (e.g. "2024" sorts
    # right before "2024-25"), so a combined multi-league frame would leak one
    # league's persisted Franchise Player/All-Star status into the other's very
    # next iteration. Self-defend by splitting and recursing per league.
    if "LEAGUE" in df.columns and df["LEAGUE"].nunique() > 1:
        return pd.concat(
            [_recompute_tiers(g) for _, g in df.groupby("LEAGUE")],
            ignore_index=False,
        )
    league = df["LEAGUE"].iloc[0] if "LEAGUE" in df.columns and len(df) else "NBA"
    _floor_min_gp = FLOOR_MIN_GP_BY_LEAGUE.get(league, 41)
    _scoring_alpha_positions = SCORING_ALPHA_POSITIONS.get(league, SCORING_ALPHA_POSITIONS["NBA"])
    _rim_anchor_positions = RIM_ANCHOR_POSITIONS.get(league, RIM_ANCHOR_POSITIONS["NBA"])

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
        scoring_alpha = (usg >= 0.28) & (ast >= 0.18) & pos.isin(_scoring_alpha_positions)
        rim_anchor    = pos.isin(_rim_anchor_positions) & (usg < 0.18) & (ast < 0.12)
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
            if t in ("Rotation", "Bench") and mpg >= _STARTER_FLOOR_MPG and gp >= _floor_min_gp:
                df.loc[idx, "TIER"] = "Starter"
            elif t == "Bench" and mpg >= _ROTATION_FLOOR_MPG and gp >= _floor_min_gp:
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
    "NBA": {
        "PG":      (0.38, 0.37, 0.13, 0.07, 0.05),
        "SG":      (0.43, 0.20, 0.20, 0.12, 0.05),
        "SF":      (0.36, 0.20, 0.27, 0.12, 0.05),
        "PF":      (0.28, 0.14, 0.32, 0.21, 0.05),
        "C":       (0.28, 0.13, 0.32, 0.22, 0.05),
        "Forward": (0.33, 0.18, 0.30, 0.14, 0.05),
        "Guard":   (0.38, 0.30, 0.19, 0.08, 0.05),
        "Unknown": (0.38, 0.28, 0.22, 0.07, 0.05),
    },
    "WNBA": {
        "G":       (0.40, 0.30, 0.20, 0.10, 0.05),
        "F":       (0.34, 0.19, 0.29, 0.13, 0.05),
        "C":       (0.28, 0.13, 0.32, 0.22, 0.05),
        "Unknown": (0.35, 0.22, 0.26, 0.12, 0.05),
    },
}

def _load_position_weights(league: str) -> dict:
    path = FITTED_WEIGHTS_JSONS[league]
    if not os.path.exists(path):
        print(
            f"\n  [warn] {path} not found — using hardcoded fallback "
            f"position weights for {league}. Run `python data/fit_weights.py` "
            "to calibrate these from data instead."
        )
        return _FALLBACK_POSITION_WEIGHTS[league]
    with open(path) as f:
        fitted = json.load(f)
    weights = {
        pos: (w["scoring"], w["playmaking"], w["defense"], w["impact"], w["availability"])
        for pos, w in fitted.items()
        if pos != "meta"
    }
    print(f"\n  Loaded fitted {league} position weights from {path} "
          f"(fitted_at={fitted.get('meta', {}).get('fitted_at', '?')})")
    return weights

POSITION_WEIGHTS = {league: _load_position_weights(league) for league in STATS_CSVS}

def get_position_weights(position_list: list, league: str) -> tuple:
    weights = POSITION_WEIGHTS[league]
    for pos in position_list:
        if pos in weights:
            return weights[pos]
    primary = position_list[0] if position_list else "Unknown"
    for key in weights:
        if primary.startswith(key):
            return weights[key]
    return weights["Unknown"]


TIER_BOOSTS = {
    "Franchise Player": 7,
    "All-Star":     1,
    "Starter":      0,
    "Rotation":     0,
    "Bench":        0,
}

def ratings_from_row(row, p: dict, position_list=None, league="NBA") -> dict:
    w_scoring, w_play, w_def, w_impact, w_avail = (
        get_position_weights(position_list, league)
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
    league = row["LEAGUE"]

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

    league_rating      = ratings_from_row(row, league_pools[season], row["POSITION_LIST"], league)
    ratings_by_position = {}
    for pos in row["POSITION_LIST"]:
        pool = position_pools.get((season, pos))
        if pool is not None:
            ratings_by_position[pos] = ratings_from_row(row, pool, [pos], league)

    card = {
        "player_id":   pid,
        "player_name": row["PLAYER_NAME"],
        "season":      season,
        "league":      league,
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
        "min_games_filter":                 MIN_GP_BY_LEAGUE,
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
            league: {
                pos: dict(zip(["scoring", "playmaking", "defense", "impact", "availability"], w))
                for pos, w in weights.items()
            }
            for league, weights in POSITION_WEIGHTS.items()
        },
    },
    "players": cards,
}

with open(OUT_JSON, "w") as f:
    json.dump(payload, f, indent=2)

size_kb = os.path.getsize(OUT_JSON) / 1024
print(f"  Written → {OUT_JSON}  ({size_kb:,.0f} KB)")


load_to_postgres(cards, DATABASE_URL)


print("\nBuilding playoff cards…")
playoff_frames = []
for league, path in PLAYOFF_STATS_CSVS.items():
    if not os.path.exists(path):
        print(f"  [skip] {path} not found — no {league} playoff data yet")
        continue
    pdf = pd.read_csv(path, dtype={"SEASON": str})
    pdf["LEAGUE"] = league
    playoff_frames.append(pdf)

playoff_cards = []
if playoff_frames:
    playoff_stats = pd.concat(playoff_frames, ignore_index=True)
    playoff_stats["POSITION_LIST"] = playoff_stats["POSITION"].apply(parse_positions)
    playoff_stats["PRIMARY_POSITION"] = playoff_stats["POSITION_LIST"].apply(lambda lst: lst[0])

    playoff_stats_f = playoff_stats[playoff_stats["GP"] >= PLAYOFF_MIN_GP].copy()
    print(f"  Playoff rows after GP filter: {len(playoff_stats_f):,} (from {len(playoff_stats):,})")

    # Fully separate from the regular-season pools above — a playoff run's
    # per-game stats (small, survivorship-biased samples) must never be
    # percentile-ranked against the regular-season population or vice versa.
    playoff_pools = {s: build_pool(g) for s, g in playoff_stats_f.groupby("SEASON")}

    # Stateless cutoff label, recomputed fresh every run — no cross-season
    # persistence, unlike the Franchise Player/All-Star tier system (which
    # doesn't translate to ~4-28 game playoff samples; see generate_player_dataset.py).
    def playoff_badge_for(overall: int) -> str | None:
        if overall >= 90:
            return "Playoff Elite"
        if overall >= 75:
            return "Playoff Riser"
        return None

    for _, row in playoff_stats_f.iterrows():
        season = row["SEASON"]
        pid    = int(row["PLAYER_ID"])
        league = row["LEAGUE"]

        rating = ratings_from_row(row, playoff_pools[season], row["POSITION_LIST"], league)

        playoff_cards.append({
            "player_id":   pid,
            "player_name": row["PLAYER_NAME"],
            "season":      season,
            "league":      league,
            "team":        row["TEAM_ABBREVIATION"],
            "age":         safe(row["AGE"]),

            "positions":        row["POSITION_LIST"],
            "primary_position": row["PRIMARY_POSITION"],

            "playoff_badge": playoff_badge_for(rating["overall"]),
            "games_played":  int(row["GP"]),

            "ratings": rating,

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
        })

    print(f"✓ {len(playoff_cards):,} playoff cards")
else:
    print("  No playoff CSVs found — skipping playoff cards.")

load_playoff_seasons_to_postgres(playoff_cards, DATABASE_URL)


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

