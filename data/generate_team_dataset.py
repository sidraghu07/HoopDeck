import time
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats

seasons = [f"{y}-{(y + 1) % 100:02d}" for y in range(1996, 2026)]

all_team_data = []

for season in seasons:
    print(f"\n── {season} ──")
    try:
        result = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            measure_type_detailed_defense="Advanced",
        ).get_data_frames()[0]
        result["SEASON"] = season
        all_team_data.append(result)
        print(f"  {len(result)} teams")
        time.sleep(2)
    except Exception as e:
        print(f"    Failed {season}: {e}")
        time.sleep(2)

if not all_team_data:
    print("No team data retrieved. Exiting.")
    exit()

teams_final = pd.concat(all_team_data, ignore_index=True)
teams_final = teams_final[[
    "SEASON", "TEAM_ID", "TEAM_NAME", "GP", "W", "L", "W_PCT",
    "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE",
]]

players = pd.read_csv("data/csv/nba_player_base_stats.csv")
team_abbrev_lookup = (
    players[["SEASON", "TEAM_ID", "TEAM_ABBREVIATION"]]
    .drop_duplicates(subset=["SEASON", "TEAM_ID"])
)

teams_final = teams_final.merge(team_abbrev_lookup, on=["SEASON", "TEAM_ID"], how="left")

missing = teams_final["TEAM_ABBREVIATION"].isna().sum()
print(f"\nTeam-seasons with no abbreviation match against player data: {missing}")
if missing > 0:
    print(teams_final[teams_final["TEAM_ABBREVIATION"].isna()][["SEASON", "TEAM_NAME"]].to_string(index=False))

teams_final = teams_final[[
    "SEASON", "TEAM_ABBREVIATION", "TEAM_NAME", "GP", "W", "L", "W_PCT",
    "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE",
]]

teams_final.to_csv("data/csv/nba_team_season_stats.csv", index=False)
print(
    f"\n✓ Saved {len(teams_final)} rows × {len(teams_final.columns)} columns "
    f"→ data/csv/nba_team_season_stats.csv"
)

check = teams_final[(teams_final["SEASON"] == "1996-97") & (teams_final["TEAM_NAME"] == "Chicago Bulls")]
if not check.empty:
    print("\nSanity check — 1996-97 Bulls:")
    print(check.to_string(index=False))
