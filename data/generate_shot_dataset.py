import os
import pandas as pd
import time
from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.library.parameters import LeagueID

LEAGUE = os.environ.get("LEAGUE", "NBA")
if LEAGUE not in ("NBA", "WNBA"):
    raise ValueError(f"Unsupported LEAGUE={LEAGUE!r}, expected 'NBA' or 'WNBA'")

SEASON_TYPE = os.environ.get("SEASON_TYPE", "Regular Season")
if SEASON_TYPE not in ("Regular Season", "Playoffs"):
    raise ValueError(f"Unsupported SEASON_TYPE={SEASON_TYPE!r}, expected 'Regular Season' or 'Playoffs'")
IS_PLAYOFFS = SEASON_TYPE == "Playoffs"

PREFIX = "nba" if LEAGUE == "NBA" else "wnba"
PLAYER_CSV = (
    f"data/csv/{PREFIX}_player_playoff_stats.csv" if IS_PLAYOFFS
    else f"data/csv/{PREFIX}_player_base_stats.csv"
)
OUT_PREFIX = f"{PREFIX}_playoff" if IS_PLAYOFFS else PREFIX
LEAGUE_ID_KWARGS = {} if LEAGUE == "NBA" else {"league_id": LeagueID.wnba}

SEASONS_OVERRIDE = os.environ.get("SEASONS_OVERRIDE")

final_df = pd.read_csv(PLAYER_CSV, dtype={"SEASON": str})
if SEASONS_OVERRIDE:
    _override_seasons = [s.strip() for s in SEASONS_OVERRIDE.split(",") if s.strip()]
    final_df = final_df[final_df["SEASON"].isin(_override_seasons)]

all_shot_data = []

for row in final_df.itertuples(index=False):
    try:
        shot_data = shotchartdetail.ShotChartDetail(
            team_id=row.TEAM_ID,
            player_id=row.PLAYER_ID,
            season_nullable=row.SEASON,
            season_type_all_star=SEASON_TYPE,
            context_measure_simple='FGA',
            **LEAGUE_ID_KWARGS,
        )
        shots_df = shot_data.get_data_frames()[0]
        shots_df['SEASON']    = row.SEASON
        shots_df['PLAYER_ID'] = row.PLAYER_ID
        all_shot_data.append(shots_df)
        time.sleep(0.5)
    except Exception as e:
        print(f"  Failed shot chart: player {row.PLAYER_ID} ({row.SEASON}): {e}")

def _merge_and_save(df: pd.DataFrame, path: str, seasons: list[str]) -> pd.DataFrame:
    if SEASONS_OVERRIDE and os.path.exists(path):
        existing = pd.read_csv(path, dtype={"SEASON": str})
        existing = existing[~existing["SEASON"].isin(seasons)]
        df = pd.concat([existing, df], ignore_index=True, sort=False)
    df.to_csv(path, index=False)
    return df


if all_shot_data:
    shots_final = pd.concat(all_shot_data, ignore_index=True)
    _override_seasons = (
        [s.strip() for s in SEASONS_OVERRIDE.split(",") if s.strip()] if SEASONS_OVERRIDE else []
    )
    shots_final = _merge_and_save(shots_final, f"data/csv/{OUT_PREFIX}_shot_charts.csv", _override_seasons)
    print(f"Saved shot chart data: {len(shots_final)} rows")

    shots_final['IS_MAKE'] = (shots_final['SHOT_MADE_FLAG'] == 1)
    shots_final['IS_MISS'] = (shots_final['SHOT_MADE_FLAG'] == 0)

    summary = (
        shots_final
        .groupby(['SEASON', 'PLAYER_ID'])
        .agg(
            PLAYER_NAME=('PLAYER_NAME', 'first'),
            MAKES=('IS_MAKE', 'sum'),
            MISSES=('IS_MISS', 'sum'),
            FGA=('SHOT_ATTEMPTED_FLAG', 'sum'),
        )
        .reset_index()
    )
    summary['FG_PCT'] = (summary['MAKES'] / summary['FGA']).round(3)

    summary.to_csv(f"data/csv/{OUT_PREFIX}_shot_makes_misses_summary.csv", index=False)
    print(f"Saved makes/misses summary: {len(summary)} rows")

    zone_summary = (
        shots_final
        .groupby(['SEASON', 'PLAYER_ID', 'PLAYER_NAME',
                  'SHOT_ZONE_BASIC', 'SHOT_ZONE_AREA', 'SHOT_ZONE_RANGE'])
        .agg(
            MAKES=('IS_MAKE', 'sum'),
            MISSES=('IS_MISS', 'sum'),
            FGA=('SHOT_ATTEMPTED_FLAG', 'sum'),
        )
        .reset_index()
    )
    zone_summary['FG_PCT'] = (zone_summary['MAKES'] / zone_summary['FGA']).round(3)

    zone_summary = zone_summary.sort_values(
        ['SEASON', 'PLAYER_ID', 'FGA'], ascending=[True, True, False]
    ).reset_index(drop=True)

    zone_summary.to_csv(f"data/csv/{OUT_PREFIX}_shot_zone_summary.csv", index=False)
    print(f"Saved zone breakdown: {len(zone_summary)} rows "
          f"({zone_summary[['SHOT_ZONE_BASIC','SHOT_ZONE_AREA','SHOT_ZONE_RANGE']].drop_duplicates().shape[0]} unique zone combos)")