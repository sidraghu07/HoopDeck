
import os

import pandas as pd
import psycopg
import requests
from psycopg.rows import dict_row

from rating_lib import normalize_name

LEAGUE = os.environ.get("LEAGUE", "NBA")
if LEAGUE not in ("NBA", "WNBA"):
    raise ValueError(f"Unsupported LEAGUE={LEAGUE!r}, expected 'NBA' or 'WNBA'")

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=nba_cards")
ESPN_SPORT = "nba" if LEAGUE == "NBA" else "wnba"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

ESPN_ABBREV = {
    "NBA": {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH", "WAS": "WSH"},
    "WNBA": {"GSV": "GS", "LVA": "LV", "LAS": "LA", "NYL": "NY", "PDX": "POR", "WAS": "WSH"},
}[LEAGUE]

TEAMS = {
    "NBA": [
        "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
        "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
        "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
    ],
    "WNBA": [
        "ATL", "CHI", "CON", "DAL", "GSV", "IND", "LAS", "LVA", "MIN", "NYL",
        "PDX", "PHX", "SEA", "TOR", "WAS",
    ],
}[LEAGUE]


def fetch_espn_roster(team_abbrev: str) -> list[str]:
    espn_abbrev = ESPN_ABBREV.get(team_abbrev, team_abbrev).lower()
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/{ESPN_SPORT}/teams/{espn_abbrev}/roster"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [a["fullName"] for a in data.get("athletes", [])]


def our_current_rosters() -> pd.DataFrame:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT player_id, player_name, team FROM team_rosters WHERE league = %(league)s", {"league": LEAGUE})
            return pd.DataFrame(cur.fetchall())


print(f"Fetching ESPN {LEAGUE} rosters for {len(TEAMS)} teams...")
espn_team_by_name: dict[str, str] = {}
for team in TEAMS:
    try:
        for name in fetch_espn_roster(team):
            espn_team_by_name[normalize_name(name)] = team
    except Exception as e:
        print(f"  Failed to fetch ESPN roster for {team}: {e}")

print(f"  {len(espn_team_by_name)} players resolved across ESPN rosters.\n")

ours = our_current_rosters()
discrepancies = []
not_found = []

for _, row in ours.iterrows():
    name_norm = normalize_name(row["player_name"])
    espn_team = espn_team_by_name.get(name_norm)
    if espn_team is None:
        not_found.append(row["player_name"])
        continue
    if espn_team != row["team"]:
        discrepancies.append({
            "player_id": row["player_id"],
            "player_name": row["player_name"],
            "our_team": row["team"],
            "espn_team": espn_team,
        })

if discrepancies:
    print(f"⚠ {len(discrepancies)} discrepancy(ies) found — our data vs ESPN's roster:\n")
    for d in discrepancies:
        print(f"  {d['player_name']} (player_id={d['player_id']}): "
              f"we have {d['our_team']}, ESPN has {d['espn_team']}")
    print(
        f"\nThese need research to resolve, not an automatic fix — confirm the real "
        f"trade, then add an entry to data/seed/roster_overrides_{LEAGUE.lower()}.json."
    )
else:
    print("✓ No discrepancies — our roster data matches ESPN's for every resolvable player.")

if not_found:
    print(f"\n({len(not_found)} of our players weren't found on any ESPN roster — "
          f"likely retired/two-way/name-format mismatches, not necessarily stale.)")
