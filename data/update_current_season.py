import datetime
import os
import subprocess
import sys

import psycopg

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=nba_cards")

REGULAR_SEASON = "REGULAR_SEASON"
PLAYOFFS = "PLAYOFFS"
OFFSEASON = "OFFSEASON"

PHASE_MONTHS = {
    "NBA":  {REGULAR_SEASON: {10, 11, 12, 1, 2, 3}, PLAYOFFS: {4, 5, 6}},
    "WNBA": {REGULAR_SEASON: {5, 6, 7, 8}, PLAYOFFS: {9, 10}},
}


def current_nba_season(today: datetime.date) -> str:
    start_year = today.year if today.month >= 10 else today.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def current_wnba_season(today: datetime.date) -> str:
    return str(today.year)


def season_phase(league: str, today: datetime.date) -> str:
    months = PHASE_MONTHS[league]
    if today.month in months[REGULAR_SEASON]:
        return REGULAR_SEASON
    if today.month in months[PLAYOFFS]:
        return PLAYOFFS
    return OFFSEASON


def run(script: str, league: str, season: str, season_type: str = "Regular Season") -> None:
    print(f"\n=== {script} (LEAGUE={league}, SEASON_TYPE={season_type}, SEASONS_OVERRIDE={season}) ===", flush=True)
    env = {**os.environ, "LEAGUE": league, "SEASONS_OVERRIDE": season, "SEASON_TYPE": season_type}
    subprocess.run(
        [sys.executable, os.path.join("data", script)],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )


def _team_gp_fingerprint(league: str, season: str) -> int | None:
    from nba_api.stats.endpoints import leaguedashteamstats
    from nba_api.stats.library.parameters import LeagueID

    kwargs = {} if league == "NBA" else {"league_id_nullable": LeagueID.wnba}
    try:
        df = leaguedashteamstats.LeagueDashTeamStats(
            season=season, measure_type_detailed_defense="Advanced", **kwargs,
        ).get_data_frames()[0]
        return int(df["GP"].sum())
    except Exception as e:
        print(f"  [warn] fingerprint fetch failed for {league} {season}: {e}")
        return None


def _load_state() -> dict:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT league, season, phase, fingerprint FROM season_state")
            return {
                league: {"season": season, "phase": phase, "fingerprint": fingerprint}
                for league, season, phase, fingerprint in cur.fetchall()
            }


def _save_state(state: dict) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for league, entry in state.items():
                cur.execute(
                    """
                    INSERT INTO season_state (league, season, phase, fingerprint, updated_at)
                    VALUES (%(league)s, %(season)s, %(phase)s, %(fingerprint)s, now())
                    ON CONFLICT (league) DO UPDATE SET
                        season = EXCLUDED.season,
                        phase = EXCLUDED.phase,
                        fingerprint = EXCLUDED.fingerprint,
                        updated_at = now()
                    """,
                    {"league": league, **entry},
                )
        conn.commit()


def main() -> None:
    today = datetime.date.today()
    seasons = {"NBA": current_nba_season(today), "WNBA": current_wnba_season(today)}
    phases = {league: season_phase(league, today) for league in seasons}
    print(f"Phases today ({today.isoformat()}): {phases}  seasons: {seasons}")

    state = _load_state()
    fetched_anything = False

    for league, season in seasons.items():
        phase = phases[league]

        if phase == OFFSEASON:
            fingerprint = _team_gp_fingerprint(league, season)
            prev = state.get(league, {}).get("fingerprint")
            if fingerprint is not None and fingerprint == prev:
                print(f"\n{league}: offseason, no change detected (GP fingerprint={fingerprint}) — skipping.")
                continue
            state[league] = {"season": season, "phase": phase, "fingerprint": fingerprint}
            run("generate_player_dataset.py", league, season, "Regular Season")
            run("generate_team_dataset.py", league, season, "Regular Season")
            run("generate_shot_dataset.py", league, season, "Regular Season")
            run("generate_player_dataset.py", league, season, "Playoffs")
            run("generate_team_dataset.py", league, season, "Playoffs")
            run("generate_shot_dataset.py", league, season, "Playoffs")
            fetched_anything = True

        elif phase == REGULAR_SEASON:
            run("generate_player_dataset.py", league, season, "Regular Season")
            run("generate_team_dataset.py", league, season, "Regular Season")
            run("generate_shot_dataset.py", league, season, "Regular Season")
            fetched_anything = True

        elif phase == PLAYOFFS:
            run("generate_player_dataset.py", league, season, "Regular Season")
            run("generate_team_dataset.py", league, season, "Regular Season")
            run("generate_shot_dataset.py", league, season, "Regular Season")
            run("generate_player_dataset.py", league, season, "Playoffs")
            run("generate_team_dataset.py", league, season, "Playoffs")
            run("generate_shot_dataset.py", league, season, "Playoffs")
            fetched_anything = True

    _save_state(state)

    if not fetched_anything:
        print("\nNothing fetched — skipping build_card_data.py/check_player_photos.py.")
        return

    print("\n=== build_card_data.py (rebuild ratings/tiers, reload Postgres) ===", flush=True)
    subprocess.run([sys.executable, os.path.join("data", "build_card_data.py")], cwd=REPO_ROOT, check=True)

    print("\n=== check_player_photos.py (pick up any new call-ups/rookies) ===", flush=True)
    subprocess.run([sys.executable, os.path.join("data", "check_player_photos.py")], cwd=REPO_ROOT, check=True)

    print("\n✓ Daily current-season refresh complete.")


if __name__ == "__main__":
    main()
