import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import psycopg

from db.loader import load_player_photos

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=nba_cards")

PLACEHOLDER_CONTENT_LENGTH = {"NBA": 12430, "WNBA": 12531}
CDN_URL = {
    "NBA": "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png",
    "WNBA": "https://cdn.wnba.com/headshots/wnba/latest/1040x760/{player_id}.png",
}
WORKERS = 20


def _has_real_photo(player_id: int, league: str) -> bool:
    req = urllib.request.Request(
        CDN_URL[league].format(player_id=player_id), method="HEAD",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            length = int(resp.headers.get("Content-Length", -1))
            return length != PLACEHOLDER_CONTENT_LENGTH[league]
    except Exception:
        return False


def main() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT ON (player_id) player_id, league FROM player_seasons ORDER BY player_id, season DESC")
            players = [(r[0], r[1]) for r in cur.fetchall()]

    print(f"Checking CDN photo status for {len(players):,} players…")
    rows: list[tuple[int, bool]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_has_real_photo, pid, league): pid for pid, league in players}
        done = 0
        for future in as_completed(futures):
            pid = futures[future]
            rows.append((pid, future.result()))
            done += 1
            if done % 250 == 0:
                print(f"  …{done:,}/{len(players):,}")

    placeholder_count = sum(1 for _, has_photo in rows if not has_photo)
    print(f"  {placeholder_count:,}/{len(rows):,} players have no real photo (placeholder only)")

    load_player_photos(rows, DATABASE_URL)


if __name__ == "__main__":
    main()
