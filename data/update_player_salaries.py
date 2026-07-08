
import json
import os
import time
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
from nba_api.stats.static import teams as nba_static_teams

from db.loader import load_player_salaries
from rating_lib import normalize_name

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=nba_cards")
OUT_CSV = "data/csv/nba_player_salaries.csv"
OVERRIDES_PATH = "data/seed/salary_overrides_nba.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

BREF_ABBREV = {"PHX": "PHO", "CHA": "CHO", "BKN": "BRK"}


def _current_season_from_csv() -> str:
    players = pd.read_csv("data/csv/nba_player_base_stats.csv", dtype={"SEASON": str})
    return players["SEASON"].max()


def _player_id_lookup() -> dict[str, int]:
    players = pd.read_csv("data/csv/nba_player_base_stats.csv", dtype={"SEASON": str})
    lookup: dict[str, int] = {}
    for _, row in players.drop_duplicates("PLAYER_ID").iterrows():
        lookup[normalize_name(row["PLAYER_NAME"])] = int(row["PLAYER_ID"])
    return lookup


def _current_team_lookup() -> dict[int, str]:
    path = "data/csv/nba_team_rosters.csv"
    if not os.path.exists(path):
        return {}
    rosters = pd.read_csv(path)
    return dict(zip(rosters["PLAYER_ID"], rosters["TEAM_ABBREVIATION"]))


def scrape_bref_salaries(team_abbrev: str) -> pd.DataFrame:
    bref_abbrev = BREF_ABBREV.get(team_abbrev, team_abbrev)
    url = f"https://www.basketball-reference.com/contracts/{bref_abbrev}.html"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "contracts"})
    if table is None:
        raise ValueError(f"Could not find contracts table for {team_abbrev}")

    df = pd.read_html(StringIO(str(table)), header=1)[0]
    df = df[~df["Player"].isin(["Player", "Team Totals"])].copy()

    current_col = df.columns[2]
    df = df[["Player", current_col]].rename(columns={"Player": "PLAYER_NAME", current_col: "SALARY"})
    df["SALARY"] = (
        df["SALARY"].astype(str).str.replace(r"[$,]", "", regex=True).replace("nan", None)
    )
    df = df.dropna(subset=["SALARY"])
    df = df[df["SALARY"].str.strip() != ""]
    df["SALARY"] = df["SALARY"].astype(float).astype(int)
    df["NAME_NORM"] = df["PLAYER_NAME"].apply(normalize_name)
    return df


season = _current_season_from_csv()
player_id_lookup = _player_id_lookup()
current_team_lookup = _current_team_lookup()
team_abbrevs = [t["abbreviation"] for t in nba_static_teams.get_teams()]

print(f"Fetching NBA salaries for {season} across {len(team_abbrevs)} teams...")

all_rows = []
unmatched = []
for abbrev in team_abbrevs:
    try:
        df = scrape_bref_salaries(abbrev)
        for _, row in df.iterrows():
            player_id = player_id_lookup.get(row["NAME_NORM"])
            if player_id is None:
                unmatched.append((abbrev, row["PLAYER_NAME"]))
                continue
            all_rows.append({
                "PLAYER_ID": player_id,
                "TEAM": abbrev,
                "SALARY": row["SALARY"],
            })
        print(f"  {abbrev}: {len(df)} contracts")
        time.sleep(3)
    except Exception as e:
        print(f"    Failed {abbrev}: {e}")
        time.sleep(3)

if unmatched:
    print(f"\n  {len(unmatched)} bref names didn't match a known player_id (rookies/two-way, likely):")
    for abbrev, name in unmatched[:20]:
        print(f"    {abbrev}: {name}")

salaries_final = pd.DataFrame(all_rows)

if not salaries_final.empty:
    dupe_ids = salaries_final[salaries_final.duplicated("PLAYER_ID", keep=False)]["PLAYER_ID"].unique()
    if len(dupe_ids):
        print(f"\nResolving {len(dupe_ids)} player(s) listed on multiple teams' contract pages...")
        keep_rows = []
        for player_id in dupe_ids:
            rows = salaries_final[salaries_final["PLAYER_ID"] == player_id]
            current_team = current_team_lookup.get(player_id)
            match = rows[rows["TEAM"] == current_team]
            keep_rows.append(match.iloc[0] if not match.empty else rows.loc[rows["SALARY"].idxmax()])
        salaries_final = pd.concat([
            salaries_final[~salaries_final["PLAYER_ID"].isin(dupe_ids)],
            pd.DataFrame(keep_rows),
        ], ignore_index=True)
salaries_final["SEASON"] = season
salaries_final["LEAGUE"] = "NBA"
salaries_final["SOURCE"] = "bref"

if os.path.exists(OVERRIDES_PATH):
    with open(OVERRIDES_PATH) as f:
        overrides_seed = json.load(f)
    overrides = overrides_seed["overrides"]
    if overrides:
        print(f"\nApplying {len(overrides)} manual salary override(s) (as of {overrides_seed['as_of']})...")
        override_ids = {o["player_id"] for o in overrides}
        salaries_final = salaries_final[~salaries_final["PLAYER_ID"].isin(override_ids)]
        override_rows = pd.DataFrame([{
            "PLAYER_ID": o["player_id"],
            "TEAM": o["team"],
            "SALARY": o["salary"],
            "SEASON": season,
            "LEAGUE": "NBA",
            "SOURCE": "override",
        } for o in overrides])
        salaries_final = pd.concat([salaries_final, override_rows], ignore_index=True)

salaries_final.to_csv(OUT_CSV, index=False)
print(f"\n✓ Saved {len(salaries_final)} salary rows → {OUT_CSV}")

load_player_salaries(salaries_final, DATABASE_URL)
