import datetime
import json
import os
import time

import pandas as pd
from nba_api.stats.endpoints import commonteamroster
from nba_api.stats.library.parameters import LeagueID
from nba_api.stats.static import teams as nba_static_teams

from db.loader import load_team_rosters

LEAGUE = os.environ.get("LEAGUE", "NBA")
if LEAGUE not in ("NBA", "WNBA"):
    raise ValueError(f"Unsupported LEAGUE={LEAGUE!r}, expected 'NBA' or 'WNBA'")

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=nba_cards")

_prefix = "nba" if LEAGUE == "NBA" else "wnba"
OUT_CSV = f"data/csv/{_prefix}_team_rosters.csv"


def _current_season() -> str:
    today = datetime.date.today()
    if LEAGUE == "NBA":
        start_year = today.year if today.month >= 10 else today.year - 1
        return f"{start_year}-{(start_year + 1) % 100:02d}"
    return str(today.year)


def _team_id_map() -> dict[str, int]:
    if LEAGUE == "NBA":
        return {t["abbreviation"]: t["id"] for t in nba_static_teams.get_teams()}
    return {t["abbreviation"]: t["id"] for t in nba_static_teams.get_wnba_teams()}


season = _current_season()
league_id_kwargs = {} if LEAGUE == "NBA" else {"league_id_nullable": LeagueID.wnba}

team_ids = _team_id_map()
print(f"Fetching {LEAGUE} rosters for {season} across {len(team_ids)} teams...")

all_rosters = []
for abbrev, team_id in team_ids.items():
    try:
        roster = commonteamroster.CommonTeamRoster(
            team_id=int(team_id),
            season=season,
            **league_id_kwargs,
        ).get_data_frames()[0]
        roster["TEAM_ABBREVIATION"] = abbrev
        roster["SEASON"] = season
        all_rosters.append(roster)
        print(f"  {abbrev}: {len(roster)} players")
        time.sleep(1.5)
    except Exception as e:
        print(f"    Failed {abbrev}: {e}")
        time.sleep(1.5)

if not all_rosters:
    print("No roster data retrieved. Exiting.")
    exit()

rosters_final = pd.concat(all_rosters, ignore_index=True)
rosters_final = rosters_final[[
    "SEASON", "TEAM_ABBREVIATION", "PLAYER_ID", "PLAYER", "NUM", "HOW_ACQUIRED",
]].rename(columns={"PLAYER": "PLAYER_NAME"})
rosters_final["LEAGUE"] = LEAGUE

overrides_path = f"data/seed/roster_overrides_{_prefix}.json"
if os.path.exists(overrides_path):
    with open(overrides_path) as f:
        overrides_seed = json.load(f)
    overrides = overrides_seed["overrides"]
    if overrides:
        print(f"\nApplying {len(overrides)} manual roster override(s) (as of {overrides_seed['as_of']})...")
        override_ids = {o["player_id"] for o in overrides}
        rosters_final = rosters_final[~rosters_final["PLAYER_ID"].isin(override_ids)]
        override_rows = pd.DataFrame([{
            "SEASON": season,
            "TEAM_ABBREVIATION": o["team"],
            "PLAYER_ID": o["player_id"],
            "PLAYER_NAME": o["player_name"],
            "NUM": None,
            "HOW_ACQUIRED": o["how_acquired"],
            "LEAGUE": LEAGUE,
        } for o in overrides])
        rosters_final = pd.concat([rosters_final, override_rows], ignore_index=True)

rosters_final.to_csv(OUT_CSV, index=False)
print(f"\n✓ Saved {len(rosters_final)} roster rows → {OUT_CSV}")

load_team_rosters(rosters_final, DATABASE_URL)
