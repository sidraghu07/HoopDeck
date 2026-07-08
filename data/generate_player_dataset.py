import os
import time
import numpy as np
import requests
import pandas as pd
from io import StringIO
from difflib import get_close_matches
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashplayerclutch
from nba_api.stats.library.parameters import LeagueID

from rating_lib import normalize_name

LEAGUE = os.environ.get("LEAGUE", "NBA")
if LEAGUE not in ("NBA", "WNBA"):
    raise ValueError(f"Unsupported LEAGUE={LEAGUE!r}, expected 'NBA' or 'WNBA'")

SEASON_TYPE = os.environ.get("SEASON_TYPE", "Regular Season")
if SEASON_TYPE not in ("Regular Season", "Playoffs"):
    raise ValueError(f"Unsupported SEASON_TYPE={SEASON_TYPE!r}, expected 'Regular Season' or 'Playoffs'")
IS_PLAYOFFS = SEASON_TYPE == "Playoffs"

_prefix = "nba" if LEAGUE == "NBA" else "wnba"
OUT_CSV = f"data/csv/{_prefix}_player_playoff_stats.csv" if IS_PLAYOFFS else f"data/csv/{_prefix}_player_base_stats.csv"

SEASONS_OVERRIDE = os.environ.get("SEASONS_OVERRIDE")


def _season_str(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


if LEAGUE == "NBA":
    seasons = [_season_str(y) for y in range(1996, 2026)]

    SEASON_GAMES = {s: 82 for s in seasons}
    SEASON_GAMES["1998-99"] = 50
    SEASON_GAMES["2011-12"] = 66
    SEASON_GAMES["2020-21"] = 72
    del SEASON_GAMES["2019-20"]

    SEASON_TO_BREF_YEAR = {s: int(s[:4]) + 1 for s in seasons}
else:
    seasons = [str(y) for y in range(1997, 2026)]

    SEASON_GAMES = {"2020": 22}
    SEASON_TO_BREF_YEAR = {s: int(s) for s in seasons}

if SEASONS_OVERRIDE:
    _override_seasons = [s.strip() for s in SEASONS_OVERRIDE.split(",") if s.strip()]
    seasons = [s for s in seasons if s in _override_seasons] or _override_seasons
   
    _bref_year = (lambda s: int(s[:4]) + 1) if LEAGUE == "NBA" else (lambda s: int(s))
    SEASON_TO_BREF_YEAR = {s: _bref_year(s) for s in seasons}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

NAME_OVERRIDES = {
    "nicolas claxton":   "nic claxton",
    "nah'shon hyland":   "bones hyland",
    "gary payton":       "gary payton ii",
    "tim hardaway":      "tim hardaway jr",
    "larry nance":       "larry nance jr",
    "otto porter":       "otto porter jr",
    "michael porter":    "michael porter jr",
    "marvin bagley":     "marvin bagley iii",
    "wendell carter":    "wendell carter jr",
    "jaren jackson":     "jaren jackson jr",
    "marcus morris":     "marcus morris sr",
    "xavier tillman":    "xavier tillman sr",
    "derrick jones":     "derrick jones jr",
    "kevin knox":        "kevin knox ii",
    "juan toscano":      "juan toscano-anderson",
    "mo bamba":          "mo bamba",
    "og anunoby":        "og anunoby",
}

MANUAL_POSITION_OVERRIDES: dict[tuple, str] = {
}

VALID_POSITIONS = {"PG", "SG", "SF", "PF", "C"} if LEAGUE == "NBA" else {"G", "F", "C"}

SCORING_ALPHA_POSITIONS = ["PG", "SG", "SF"] if LEAGUE == "NBA" else ["G"]
RIM_ANCHOR_POSITIONS = ["C"]

FIRST_OPTION_PCTILE = 0.95
ALL_STAR_PCTILE     = 0.90
STARTER_PCTILE      = 0.70
ROTATION_PCTILE     = 0.40

MASSIVE_DROP_PCTILE = 0.85

MIN_AVAILABILITY_PCT         = 0.40
MIN_AVAILABILITY_PCT_PROMOTE = 0.55
ALL_STAR_PERSIST_PCTILE      = 0.60
MIN_MPG                      = 10


def zscore(s: pd.Series) -> pd.Series:
    std = s.std(ddof=0)
    if std == 0 or pd.isna(std):
        return s * 0
    return (s - s.mean()) / std


def scrape_bref_positions(year: int, season_str: str) -> pd.DataFrame:
    url = f"https://www.basketball-reference.com/leagues/NBA_{year}_per_game.html"

    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    table = (
        soup.find("table", {"id": "per_game_stats"})
        or soup.find("table", {"id": "per_game"})
    )
    if table is None:
        raise ValueError(f"Could not find per_game_stats table for {year}")

    df = pd.read_html(StringIO(str(table)), header=0)[0]
    df = df[df["Player"] != "Player"].copy()
    df["Player"] = df["Player"].str.replace(r"\*", "", regex=True).str.strip()
    df = df.rename(columns={"Player": "PLAYER_NAME", "Pos": "POSITION"})
    df = df[["PLAYER_NAME", "POSITION"]].copy()
    df["SEASON"] = season_str

    df["POSITION"] = df["POSITION"].str.split("-").str[0].str.strip()

    df = df.drop_duplicates(subset=["PLAYER_NAME", "SEASON"], keep="first")
    df = df[df["POSITION"].isin(VALID_POSITIONS)].copy()
    df["NAME_NORM"] = df["PLAYER_NAME"].apply(normalize_name)
    return df


def scrape_bref_positions_wnba(year: int, season_str: str) -> pd.DataFrame:
    url = f"https://www.basketball-reference.com/wnba/years/{year}_per_game.html"

    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    table = (
        soup.find("table", {"id": "per_game_stats"})
        or soup.find("table", {"id": "per_game"})
    )
    if table is None:
        raise ValueError(f"Could not find per_game_stats table for {year}")

    tbody = table.find("tbody")
    rows = []
    for tr in tbody.find_all("tr"):
        name_cell = tr.find(attrs={"data-stat": "player"})
        name_link = name_cell.find("a") if name_cell else None
        name = name_link.get_text(strip=True) if name_link else None
        pos_cell = tr.find(attrs={"data-stat": "pos"})
        pos = pos_cell.get_text(strip=True) if pos_cell else None
        if not name or not pos:
            continue
        rows.append({"PLAYER_NAME": name, "POSITION": pos})

    df = pd.DataFrame(rows)
    df["SEASON"] = season_str
    df["POSITION"] = df["POSITION"].str.split("-").str[0].str.strip()
    df = df.drop_duplicates(subset=["PLAYER_NAME", "SEASON"], keep="first")
    df = df[df["POSITION"].isin(VALID_POSITIONS)].copy()
    df["NAME_NORM"] = df["PLAYER_NAME"].apply(normalize_name)
    return df


def add_player_tiers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in [
        "PIE", "NET_RATING", "TS_PCT", "USG_PCT", "AST_PCT", "W_PCT",
        "DEF_WS", "STL_PCT", "BLK_PCT", "AST_TO", "TOV_PCT",
        "CLUTCH_PLUS_MINUS", "PCT_UAST_FGM",
    ]:
        if col not in df.columns:
            df[col] = 0.0

    df["IMPACT_SCORE"]  = float("nan")
    df["IMPACT_PCTILE"] = float("nan")
    df["TIER"] = "Bench"

    sorted_seasons = sorted(df["SEASON"].unique())

    for season in sorted_seasons:
        mask  = df["SEASON"] == season
        group = df[mask]

        eligible = (
            (group["AVAILABILITY_PCT"] >= MIN_AVAILABILITY_PCT)
            & (group["MIN"] >= MIN_MPG)
        )
        elig_idx = group.index[eligible]

        if len(elig_idx) == 0:
            continue

        e = group.loc[elig_idx]

        z_pie    = zscore(e["PIE"])
        z_net    = zscore(e["NET_RATING"])
        z_ts     = zscore(e["TS_PCT"])
        z_usg    = zscore(e["USG_PCT"])
        z_ast    = zscore(e["AST_PCT"])

        z_stl = zscore(e["STL"])
        z_blk = zscore(e["BLK"])

        z_ast_to = zscore(e["AST_TO"])
        z_tov    = zscore(e["TOV_PCT"])

        z_uast   = zscore(e["PCT_UAST_FGM"])

        z_clutch = zscore(e["CLUTCH_PLUS_MINUS"])

        impact = (
            z_pie    * 0.22
            + z_net  * 0.15
            + z_ts   * 0.08
            + z_usg  * 0.10
            + z_ast  * 0.10
            + z_stl  * 0.09
            + z_blk  * 0.06
            + z_ast_to * 0.06
            - z_tov    * 0.04
            + z_uast   * 0.04
            + z_clutch * 0.06
        )

        pos = e["POSITION"]
        usg = e["USG_PCT"]
        ast = e["AST_PCT"]

        heliocentric   = (usg >= 0.26) & (ast >= 0.25)
        scoring_alpha  = (usg >= 0.28) & (ast >= 0.18) & pos.isin(SCORING_ALPHA_POSITIONS)
        rim_anchor     = pos.isin(RIM_ANCHOR_POSITIONS) & (usg < 0.18) & (ast < 0.12)

        impact[heliocentric]                    += 0.50
        impact[scoring_alpha & ~heliocentric]   += 0.50
        impact[rim_anchor]                      -= 0.45

        total_min = e["MIN"] * e["GP"]
        min_weight = (np.log1p(total_min) / np.log1p(2000)).clip(0, 1)
        impact = impact * min_weight

        impact_arr = impact.to_numpy(dtype=float, na_value=0.0)
        pos_arr    = pos.to_numpy()
        blend_arr  = np.zeros(len(elig_idx), dtype=float)

        for pos_group in [["PG", "SG"], ["SF", "PF"], ["C"]]:
            gmask = np.isin(pos_arr, pos_group)
            if gmask.sum() < 3:
                continue
            grp   = impact_arr[gmask]
            std   = grp.std()
            pos_z = (grp - grp.mean()) / (std if std else 1)
            blend_arr[gmask] = pos_z

        impact = pd.Series(
            impact_arr * 0.60 + blend_arr * 0.40,
            index=elig_idx,
        )

        df.loc[elig_idx, "IMPACT_SCORE"]  = impact.values
        df.loc[elig_idx, "IMPACT_PCTILE"] = impact.rank(pct=True).values

    previous_first_options: set[str] = set()
    previous_all_stars:     set[str] = set()

    for season in sorted_seasons:
        season_mask    = df["SEASON"] == season
        eligible_mask  = season_mask & df["IMPACT_PCTILE"].notna()
        elig_idx       = df[eligible_mask].index
        demoted_this_season: set[str] = set()

        if len(elig_idx) == 0:
            continue

        pctiles = df.loc[elig_idx, "IMPACT_PCTILE"]

        tier = pd.Series("Bench", index=elig_idx, dtype="object")
        tier.loc[pctiles >= ROTATION_PCTILE]     = "Rotation"
        tier.loc[pctiles >= STARTER_PCTILE]      = "Starter"
        tier.loc[pctiles >= ALL_STAR_PCTILE]     = "All-Star"
        tier.loc[pctiles >= FIRST_OPTION_PCTILE] = "Franchise Player"

        for idx in elig_idx:
            player_name    = df.loc[idx, "PLAYER_NAME"]
            current_pctile = df.loc[idx, "IMPACT_PCTILE"]

            if player_name in previous_first_options:
                if current_pctile >= MASSIVE_DROP_PCTILE:
                    if tier.loc[idx] != "Franchise Player":
                        tier.loc[idx] = "Franchise Player"
                else:
                    print(
                        f"    [{season}] {player_name}: lost Franchise Player "
                        f"(pctile={current_pctile:.2f})"
                    )
            elif player_name in previous_all_stars and tier.loc[idx] not in ("Franchise Player", "All-Star"):
                if current_pctile >= ALL_STAR_PERSIST_PCTILE:
                    tier.loc[idx] = "All-Star"
                else:
                    print(
                        f"    [{season}] {player_name}: lost All-Star "
                        f"(pctile={current_pctile:.2f})"
                    )

        df.loc[elig_idx, "TIER"] = tier

        first_opt_mask = eligible_mask & (df["TIER"] == "Franchise Player")
        team_groups    = df[first_opt_mask].groupby("TEAM_ABBREVIATION")

        for team, team_df in team_groups:
            if len(team_df) <= 1:
                continue
            best_idx    = team_df["IMPACT_SCORE"].idxmax()
            best_player = team_df.loc[best_idx, "PLAYER_NAME"]

            for demoted_idx, demoted_row in team_df.drop(best_idx).iterrows():
                df.loc[demoted_idx, "TIER"] = "All-Star"
                demoted_this_season.add(demoted_row["PLAYER_NAME"])
                print(
                    f"    [{season}] {team}: {best_player} surpassed "
                    f"{demoted_row['PLAYER_NAME']} → demoted to All-Star"
                )

        for idx in df[eligible_mask].index:
            t   = df.loc[idx, "TIER"]
            pts = df.loc[idx, "PTS"]
            usg = df.loc[idx, "USG_PCT"]

            if t == "Franchise Player":
                qualifies = (pts >= 17) or (usg >= 0.27)
                if not qualifies:
                    df.loc[idx, "TIER"] = "All-Star"
                    print(
                        f"    [{season}] {df.loc[idx,'PLAYER_NAME']}: "
                        f"Franchise Player → All-Star (gate: {pts:.1f} PPG, {usg:.1%} USG)"
                    )

            elif t == "All-Star":
                qualifies = (pts >= 14) or (usg >= 0.24)
                if not qualifies:
                    df.loc[idx, "TIER"] = "Starter"
                    print(
                        f"    [{season}] {df.loc[idx,'PLAYER_NAME']}: "
                        f"All-Star → Starter (gate: {pts:.1f} PPG, {usg:.1%} USG)"
                    )

        fo_after = eligible_mask & (df["TIER"] == "Franchise Player")
        teams_with_fo = set(df[fo_after]["TEAM_ABBREVIATION"].dropna())
        for team, tdf in df[eligible_mask].groupby("TEAM_ABBREVIATION"):
            if team in teams_with_fo:
                continue

            primary = tdf[
                (tdf["TIER"] == "All-Star")
                & (tdf["IMPACT_PCTILE"] >= 0.88)
                & (tdf["PTS"] >= 15)
                & (tdf["AVAILABILITY_PCT"] >= MIN_AVAILABILITY_PCT_PROMOTE)
            ]
            if not primary.empty:
                best_idx = primary["IMPACT_PCTILE"].idxmax()
                df.loc[best_idx, "TIER"] = "Franchise Player"
                print(
                    f"    [{season}] {df.loc[best_idx,'PLAYER_NAME']}: "
                    f"promoted to Franchise Player (impact: "
                    f"{df.loc[best_idx,'PTS']:.1f}pts, pctile={df.loc[best_idx,'IMPACT_PCTILE']:.2f})"
                )
                continue

            secondary = tdf[
                (tdf["TIER"] == "All-Star")
                & ((tdf["PTS"] >= 20) | ((tdf["PTS"] >= 17) & (tdf["USG_PCT"] >= 0.27)))
                & (tdf["IMPACT_PCTILE"] >= 0.75)
                & (tdf["AVAILABILITY_PCT"] >= MIN_AVAILABILITY_PCT_PROMOTE)
            ]
            if not secondary.empty:
                best_idx = secondary["IMPACT_PCTILE"].idxmax()
                df.loc[best_idx, "TIER"] = "Franchise Player"
                print(
                    f"    [{season}] {df.loc[best_idx,'PLAYER_NAME']}: "
                    f"promoted to Franchise Player (scoring: "
                    f"{df.loc[best_idx,'PTS']:.1f}pts, {df.loc[best_idx,'USG_PCT']:.1%}usg, "
                    f"pctile={df.loc[best_idx,'IMPACT_PCTILE']:.2f})"
                )

        previous_first_options = set(
            df[season_mask & (df["TIER"] == "Franchise Player")]["PLAYER_NAME"]
        )
        previous_all_stars = set(
            df[season_mask & (df["TIER"] == "All-Star")]["PLAYER_NAME"]
        )

    return df


all_base_data   = []
all_adv_data    = []
all_def_data    = []
all_scoring_data = []
all_clutch_data = []

LEAGUE_ID_KWARGS = {} if LEAGUE == "NBA" else {"league_id_nullable": LeagueID.wnba}

for season in seasons:
    print(f"\n── {season} ──")

    for label, kwargs in [
        ("BASE",    {"measure_type_detailed_defense": "Base"}),
        ("ADVANCED",{"measure_type_detailed_defense": "Advanced"}),
        ("DEFENSE", {"measure_type_detailed_defense": "Defense"}),
        ("SCORING", {"measure_type_detailed_defense": "Scoring"}),
    ]:
        print(f"  Fetching {label}...")
        try:
            result = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season,
                per_mode_detailed="PerGame",
                season_type_all_star=SEASON_TYPE,
                **kwargs,
                **LEAGUE_ID_KWARGS,
            ).get_data_frames()[0]
            result["SEASON"] = season

            if label == "BASE":
                all_base_data.append(result)
            elif label == "ADVANCED":
                all_adv_data.append(result)
            elif label == "DEFENSE":
                all_def_data.append(result)
            elif label == "SCORING":
                all_scoring_data.append(result)

            time.sleep(2)
        except Exception as e:
            print(f"    Failed {label} for {season}: {e}")

    print("  Fetching CLUTCH...")
    try:
        clutch = leaguedashplayerclutch.LeagueDashPlayerClutch(
            season=season,
            per_mode_detailed="PerGame",
            season_type_all_star=SEASON_TYPE,
            **LEAGUE_ID_KWARGS,
        ).get_data_frames()[0]
        clutch["SEASON"] = season
        all_clutch_data.append(clutch)
        time.sleep(2)
    except Exception as e:
        print(f"    Failed CLUTCH for {season}: {e}")


if not all_base_data:
    print("No base data retrieved. Exiting.")
    exit()

base_final    = pd.concat(all_base_data,    ignore_index=True)
adv_final     = pd.concat(all_adv_data,     ignore_index=True) if all_adv_data    else pd.DataFrame()
def_final     = pd.concat(all_def_data,     ignore_index=True) if all_def_data    else pd.DataFrame()
scoring_final = pd.concat(all_scoring_data, ignore_index=True) if all_scoring_data else pd.DataFrame()
clutch_final  = pd.concat(all_clutch_data,  ignore_index=True) if all_clutch_data  else pd.DataFrame()


def safe_merge(base: pd.DataFrame, other: pd.DataFrame, suffix: str) -> pd.DataFrame:
    if other.empty:
        return base
    new_cols = [
        c for c in other.columns
        if c not in base.columns and c not in ("PLAYER_ID", "SEASON")
    ]
    return base.merge(other[["PLAYER_ID", "SEASON"] + new_cols], on=["PLAYER_ID", "SEASON"], how="left")


final_df = base_final.copy()
final_df = safe_merge(final_df, adv_final,     "adv")
final_df = safe_merge(final_df, def_final,     "def")
final_df = safe_merge(final_df, scoring_final, "scoring")

if not clutch_final.empty and "PLUS_MINUS" in clutch_final.columns:
    clutch_slim = clutch_final[["PLAYER_ID", "SEASON", "PLUS_MINUS"]].rename(
        columns={"PLUS_MINUS": "CLUTCH_PLUS_MINUS"}
    )
    final_df = final_df.merge(clutch_slim, on=["PLAYER_ID", "SEASON"], how="left")

print(f"\nMerged shape: {final_df.shape}")


cols = ["SEASON"] + [c for c in final_df.columns if c != "SEASON"]
final_df = final_df[cols]
final_df["SCHEDULED_GAMES"] = final_df["SEASON"].map(SEASON_GAMES)

for season in final_df["SEASON"].unique():
    if pd.isna(SEASON_GAMES.get(season, float("nan"))):
        mask = final_df["SEASON"] == season
        final_df.loc[mask, "SCHEDULED_GAMES"] = final_df.loc[mask, "GP"].max()

final_df["AVAILABILITY_PCT"] = (final_df["GP"] / final_df["SCHEDULED_GAMES"]).round(3)


print("\nScraping positions from Basketball Reference...")
bref_frames = []
_scrape_positions = scrape_bref_positions if LEAGUE == "NBA" else scrape_bref_positions_wnba

for season_str, year in SEASON_TO_BREF_YEAR.items():
    try:
        bref_df_season = _scrape_positions(year, season_str)
        print(
            f"  {season_str}: {len(bref_df_season)} players — "
            f"{bref_df_season['POSITION'].value_counts().to_dict()}"
        )
        bref_frames.append(bref_df_season)
        time.sleep(4)
    except Exception as e:
        print(f"  Failed {season_str}: {e}")
        time.sleep(4)

if not bref_frames:
    print("Warning: All BBRef scraping failed. POSITION set to Unknown.")
    final_df["POSITION"] = "Unknown"
else:
    bref_df = pd.concat(bref_frames, ignore_index=True)

    bref_season_lookup: dict[tuple, str] = {
        (row["NAME_NORM"], row["SEASON"]): row["POSITION"]
        for _, row in bref_df.iterrows()
    }
    bref_any_season: dict[str, str] = (
        bref_df.sort_values("SEASON")
        .drop_duplicates("NAME_NORM", keep="last")
        .set_index("NAME_NORM")["POSITION"]
        .to_dict()
    )
    all_bref_norms = list(bref_any_season.keys())

    def lookup_position(player_name: str, season: str) -> str:
        override_key = (player_name, season)
        if override_key in MANUAL_POSITION_OVERRIDES:
            return MANUAL_POSITION_OVERRIDES[override_key]

        norm     = normalize_name(player_name)
        override = NAME_OVERRIDES.get(norm, norm)

        for key in (override, norm):
            pos = bref_season_lookup.get((key, season))
            if pos:
                return pos

        for key in (override, norm):
            pos = bref_any_season.get(key)
            if pos:
                return pos

        candidates = get_close_matches(norm, all_bref_norms, n=1, cutoff=0.82)
        if candidates:
            pos = bref_any_season.get(candidates[0])
            if pos:
                print(f"    Fuzzy: '{player_name}' → '{candidates[0]}' → {pos}")
                return pos

        if override != norm:
            candidates = get_close_matches(override, all_bref_norms, n=1, cutoff=0.82)
            if candidates:
                pos = bref_any_season.get(candidates[0])
                if pos:
                    print(f"    Fuzzy(override): '{player_name}' → '{candidates[0]}' → {pos}")
                    return pos

        return "Unknown"

    print("\nResolving positions...")
    final_df["POSITION"] = final_df.apply(
        lambda r: lookup_position(r["PLAYER_NAME"], r["SEASON"]), axis=1
    )

    unknown_mask  = final_df["POSITION"] == "Unknown"
    unknown_count = unknown_mask.sum()
    print(f"\n  Unknown after all layers: {unknown_count}")
    if unknown_count > 0:
        print("  Remaining unknowns (not on BBRef at all):")
        print(
            final_df[unknown_mask][["PLAYER_NAME", "SEASON"]]
            .drop_duplicates("PLAYER_NAME")
            .sort_values("PLAYER_NAME")
            .to_string(index=False)
        )

print(f"\nFinal POSITION breakdown:\n{final_df['POSITION'].value_counts().to_string()}")

if SEASONS_OVERRIDE and os.path.exists(OUT_CSV):
    print(f"\nMerging {seasons} into existing {OUT_CSV}...")
    existing_df = pd.read_csv(OUT_CSV, dtype={"SEASON": str})
    existing_df = existing_df[~existing_df["SEASON"].isin(seasons)]
    final_df = pd.concat([existing_df, final_df], ignore_index=True, sort=False)
    print(f"  Merged shape: {final_df.shape}")

if IS_PLAYOFFS:
    print("\nSkipping tier assignment for playoffs data.")
else:
    print("\nAssigning tiers (First Option / All-Star / Starter / Rotation / Bench)...")
    final_df = add_player_tiers(final_df)

    print(f"\nFinal TIER breakdown:\n{final_df['TIER'].value_counts().to_string()}")

    for check_name in ["Nikola Jokic", "Jamal Murray", "Tim Hardaway Jr."]:
        hits = final_df[final_df["PLAYER_NAME"] == check_name][
            ["PLAYER_NAME", "SEASON", "IMPACT_PCTILE", "TIER"]
        ]
        if not hits.empty:
            print(f"\n  Check: {check_name}")
            print(hits.to_string(index=False))


final_df["LEAGUE"] = LEAGUE
final_df.to_csv(OUT_CSV, index=False)
print(
    f"\n✓ Saved {len(final_df)} rows × {len(final_df.columns)} columns "
    f"→ {OUT_CSV}"
)
print(f"  Seasons: {sorted(final_df['SEASON'].unique())}")
