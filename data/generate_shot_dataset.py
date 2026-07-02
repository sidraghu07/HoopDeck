import pandas as pd
import time
from nba_api.stats.endpoints import shotchartdetail

final_df = pd.read_csv("data/csv/nba_player_base_stats.csv")
all_shot_data = []

for row in final_df.itertuples(index=False):
    try:
        print(row.SEASON)
        shot_data = shotchartdetail.ShotChartDetail(
            team_id=row.TEAM_ID,
            player_id=row.PLAYER_ID,
            season_nullable=row.SEASON,
            season_type_all_star='Regular Season',
            context_measure_simple='FGA'
        )
        shots_df = shot_data.get_data_frames()[0]
        shots_df['SEASON']    = row.SEASON
        shots_df['PLAYER_ID'] = row.PLAYER_ID
        all_shot_data.append(shots_df)
        time.sleep(0.5)
    except Exception as e:
        print(f"  Failed shot chart: player {row.PLAYER_ID} ({row.SEASON}): {e}")

if all_shot_data:
    shots_final = pd.concat(all_shot_data, ignore_index=True)
    shots_final.to_csv("data/csv/nba_shot_charts.csv", index=False)
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

    summary.to_csv("data/csv/nba_shot_makes_misses_summary.csv", index=False)
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

    zone_summary.to_csv("data/csv/nba_shot_zone_summary.csv", index=False)
    print(f"Saved zone breakdown: {len(zone_summary)} rows "
          f"({zone_summary[['SHOT_ZONE_BASIC','SHOT_ZONE_AREA','SHOT_ZONE_RANGE']].drop_duplicates().shape[0]} unique zone combos)")