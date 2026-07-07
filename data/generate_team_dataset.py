import os
import time
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats
from nba_api.stats.library.parameters import LeagueID

LEAGUE = os.environ.get("LEAGUE", "NBA")
if LEAGUE not in ("NBA", "WNBA"):
    raise ValueError(f"Unsupported LEAGUE={LEAGUE!r}, expected 'NBA' or 'WNBA'")

# See generate_player_dataset.py for SEASON_TYPE/SEASONS_OVERRIDE semantics.
SEASON_TYPE = os.environ.get("SEASON_TYPE", "Regular Season")
if SEASON_TYPE not in ("Regular Season", "Playoffs"):
    raise ValueError(f"Unsupported SEASON_TYPE={SEASON_TYPE!r}, expected 'Regular Season' or 'Playoffs'")
IS_PLAYOFFS = SEASON_TYPE == "Playoffs"

_prefix = "nba" if LEAGUE == "NBA" else "wnba"
# The team-abbreviation lookup always comes from the regular-season player
# CSV (playoff teams are a subset, and TEAM_ID -> abbreviation doesn't
# depend on season type), regardless of which CSV this run is producing.
PLAYER_CSV = f"data/csv/{_prefix}_player_base_stats.csv"
OUT_CSV = f"data/csv/{_prefix}_team_playoff_stats.csv" if IS_PLAYOFFS else f"data/csv/{_prefix}_team_season_stats.csv"
LEAGUE_ID_KWARGS = {} if LEAGUE == "NBA" else {"league_id_nullable": LeagueID.wnba}

SEASONS_OVERRIDE = os.environ.get("SEASONS_OVERRIDE")

if LEAGUE == "NBA":
    seasons = [f"{y}-{(y + 1) % 100:02d}" for y in range(1996, 2026)]
else:
    seasons = [str(y) for y in range(1997, 2026)]

if SEASONS_OVERRIDE:
    _override_seasons = [s.strip() for s in SEASONS_OVERRIDE.split(",") if s.strip()]
    seasons = [s for s in seasons if s in _override_seasons] or _override_seasons

all_team_data = []

for season in seasons:
    print(f"\n── {season} ──")
    try:
        result = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            measure_type_detailed_defense="Advanced",
            season_type_all_star=SEASON_TYPE,
            **LEAGUE_ID_KWARGS,
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

players = pd.read_csv(PLAYER_CSV, dtype={"SEASON": str})
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

teams_final["LEAGUE"] = LEAGUE

if SEASONS_OVERRIDE and os.path.exists(OUT_CSV):
    print(f"\nMerging {seasons} into existing {OUT_CSV}...")
    existing_teams = pd.read_csv(OUT_CSV, dtype={"SEASON": str})
    existing_teams = existing_teams[~existing_teams["SEASON"].isin(seasons)]
    teams_final = pd.concat([existing_teams, teams_final], ignore_index=True, sort=False)
    print(f"  Merged shape: {teams_final.shape}")

teams_final.to_csv(OUT_CSV, index=False)
print(
    f"\n✓ Saved {len(teams_final)} rows × {len(teams_final.columns)} columns "
    f"→ {OUT_CSV}"
)

check = teams_final[(teams_final["SEASON"] == "1996-97") & (teams_final["TEAM_NAME"] == "Chicago Bulls")]
if not check.empty:
    print("\nSanity check — 1996-97 Bulls:")
    print(check.to_string(index=False))
