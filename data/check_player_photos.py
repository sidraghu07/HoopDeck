"""
Flags players whose NBA CDN headshot is the generic "no photo available"
placeholder, so the frontend can skip straight to an initials avatar
instead of rendering the placeholder as if it were a real photo.

The placeholder is always served as a byte-identical PNG at
content-length 12430, regardless of player_id, with an HTTP 200 (not a 404),
so a plain image-load failure check on the frontend can't detect it.

Run after build_card_data.py has populated player_seasons.
"""
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import psycopg

from db.loader import load_player_photos

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=nba_cards")
PLACEHOLDER_CONTENT_LENGTH = 12430
CDN_URL = "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
WORKERS = 20


def _has_real_photo(player_id: int) -> bool:
    req = urllib.request.Request(
        CDN_URL.format(player_id=player_id), method="HEAD",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            length = int(resp.headers.get("Content-Length", -1))
            return length != PLACEHOLDER_CONTENT_LENGTH
    except Exception:
        return False


def main() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT player_id FROM player_seasons")
            player_ids = [r[0] for r in cur.fetchall()]

    print(f"Checking CDN photo status for {len(player_ids):,} players…")
    rows: list[tuple[int, bool]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_has_real_photo, pid): pid for pid in player_ids}
        done = 0
        for future in as_completed(futures):
            pid = futures[future]
            rows.append((pid, future.result()))
            done += 1
            if done % 250 == 0:
                print(f"  …{done:,}/{len(player_ids):,}")

    placeholder_count = sum(1 for _, has_photo in rows if not has_photo)
    print(f"  {placeholder_count:,}/{len(rows):,} players have no real photo (placeholder only)")

    load_player_photos(rows, DATABASE_URL)


if __name__ == "__main__":
    main()
