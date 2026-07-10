import datetime
import json
import os
import time
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
from nba_api.stats.static import teams as nba_static_teams

from db.loader import load_team_rosters, player_id_lookup
from rating_lib import normalize_name

LEAGUE = os.environ.get("LEAGUE", "NBA")
if LEAGUE not in ("NBA", "WNBA"):
    raise ValueError(f"Unsupported LEAGUE={LEAGUE!r}, expected 'NBA' or 'WNBA'")

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=nba_cards")

_prefix = "nba" if LEAGUE == "NBA" else "wnba"
OUT_CSV = f"data/csv/{_prefix}_team_rosters.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# stats.nba.com blocks requests from GitHub Actions' runner IPs (every team times out
# in CI, works fine locally), so rosters are scraped from basketball-reference instead,
# same as data/update_player_salaries.py.
BREF_ABBREV = {"PHX": "PHO", "CHA": "CHO", "BKN": "BRK"}


def _current_season() -> str:
    today = datetime.date.today()
    if LEAGUE == "NBA":
        start_year = today.year if today.month >= 10 else today.year - 1
        return f"{start_year}-{(start_year + 1) % 100:02d}"
    return str(today.year)


def _bref_year(season: str) -> int:
    return int(season.split("-")[0]) + 1 if LEAGUE == "NBA" else int(season)


def _team_abbrevs() -> list[str]:
    if LEAGUE == "NBA":
        return [t["abbreviation"] for t in nba_static_teams.get_teams()]
    return [t["abbreviation"] for t in nba_static_teams.get_wnba_teams()]


def scrape_bref_roster(team_abbrev: str, year: int) -> pd.DataFrame:
    bref_abbrev = BREF_ABBREV.get(team_abbrev, team_abbrev)
    path = "teams" if LEAGUE == "NBA" else "wnba/teams"
    url = f"https://www.basketball-reference.com/{path}/{bref_abbrev}/{year}.html"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "roster"})
    if table is None:
        raise ValueError(f"Could not find roster table for {team_abbrev}")

    df = pd.read_html(StringIO(str(table)))[0]
    df = df[["No.", "Player"]].rename(columns={"No.": "NUM", "Player": "PLAYER_NAME"})
    df["PLAYER_NAME"] = df["PLAYER_NAME"].str.replace(r"\s*\([^)]*\)\s*$", "", regex=True).str.strip()
    df["NAME_NORM"] = df["PLAYER_NAME"].apply(normalize_name)
    return df


season = _current_season()
year = _bref_year(season)
team_abbrevs = _team_abbrevs()
name_lookup = player_id_lookup(DATABASE_URL, LEAGUE)

print(f"Fetching {LEAGUE} rosters for {season} across {len(team_abbrevs)} teams...")

all_rows = []
unmatched = []
for abbrev in team_abbrevs:
    try:
        df = scrape_bref_roster(abbrev, year)
        for _, row in df.iterrows():
            player_id = name_lookup.get(row["NAME_NORM"])
            if player_id is None:
                unmatched.append((abbrev, row["PLAYER_NAME"]))
                continue
            all_rows.append({
                "TEAM_ABBREVIATION": abbrev,
                "PLAYER_ID": player_id,
                "PLAYER_NAME": row["PLAYER_NAME"],
                "NUM": row["NUM"],
            })
        print(f"  {abbrev}: {len(df)} players")
        time.sleep(3)
    except Exception as e:
        print(f"    Failed {abbrev}: {e}")
        time.sleep(3)

if unmatched:
    print(f"\n  {len(unmatched)} bref names didn't match a known player_id (rookies/new signees, likely):")
    for abbrev, name in unmatched[:20]:
        print(f"    {abbrev}: {name}")

if not all_rows:
    print("No roster data retrieved. Exiting.")
    exit()

rosters_final = pd.DataFrame(all_rows)

dupe_ids = rosters_final[rosters_final.duplicated("PLAYER_ID", keep=False)]["PLAYER_ID"].unique()
if len(dupe_ids):
    print(
        f"\n  {len(dupe_ids)} player(s) listed on multiple teams' bref pages "
        "(bref hasn't reconciled a recent trade/signing yet) — keeping the last-seen team; "
        f"add a data/seed/roster_overrides_{_prefix}.json entry to correct any of these:"
    )
    for pid in dupe_ids:
        rows = rosters_final[rosters_final["PLAYER_ID"] == pid]
        print(f"    {rows.iloc[0]['PLAYER_NAME']}: {', '.join(rows['TEAM_ABBREVIATION'])}")
    rosters_final = rosters_final.drop_duplicates("PLAYER_ID", keep="last")

rosters_final["SEASON"] = season
rosters_final["LEAGUE"] = LEAGUE
# basketball-reference's roster table doesn't carry acquisition history the way
# stats.nba.com's commonteamroster did; left null unless a roster override supplies one.
rosters_final["HOW_ACQUIRED"] = None

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

os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
rosters_final.to_csv(OUT_CSV, index=False)
print(f"\n✓ Saved {len(rosters_final)} roster rows → {OUT_CSV}")

load_team_rosters(rosters_final, DATABASE_URL)
