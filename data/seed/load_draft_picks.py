import argparse
import json
import os

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=nba_cards")

parser = argparse.ArgumentParser()
parser.add_argument("--league", required=True, choices=["NBA", "WNBA"])
args = parser.parse_args()

seed_path = f"data/seed/draft_picks_{args.league.lower()}.json"
with open(seed_path) as f:
    seed = json.load(f)

print(f"Loading {args.league} draft picks (seed as-of {seed['as_of']})...")
picks = seed["picks"]

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM draft_picks WHERE league = %(league)s", {"league": args.league})
        with cur.copy(
            "COPY draft_picks (league, draft_year, round, original_team, current_owner, "
            "protection_note, trade_note, is_swap, source_url) FROM STDIN"
        ) as copy:
            for p in picks:
                copy.write_row((
                    p["league"], p["draft_year"], p["round"], p["original_team"], p["current_owner"],
                    p["protection_note"], p["trade_note"], p["is_swap"], p["source_url"],
                ))
    conn.commit()

print(f"  ✓ Loaded {len(picks)} draft-pick rows for {args.league}")
