from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

from api.db import pool

router = APIRouter()

PLAYER_STAT_COLUMNS = """
    player_id, player_name, season, team, primary_position, tier,
    rating_overall, rating_scoring, rating_playmaking, rating_defense, rating_impact,
    pg_pts, pg_reb, pg_ast, pg_stl, pg_blk, pg_tov, pg_min, pg_oreb, pg_dreb,
    fg_pct, fg3_pct, ft_pct, efg_pct, ts_pct, fg3a_per_game, fga_per_game, pct_uast_fgm,
    off_rating, def_rating, net_rating, ast_pct, ast_to, usg_pct, oreb_pct, dreb_pct,
    pie, pace, plus_minus, e_tov_pct, clutch_plus_minus
"""

TEAM_STAT_COLUMNS = """
    team, season, team_name, games_played, wins, losses, win_pct,
    off_rating, def_rating, net_rating, pace
"""


@router.get("/api/stats/players")
def get_player_stats(season: str | None = None, seasons: str | None = None):
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if seasons:
                season_list = [s.strip() for s in seasons.split(",") if s.strip()]
                cur.execute(
                    f"SELECT {PLAYER_STAT_COLUMNS} FROM player_seasons "
                    "WHERE season = ANY(%(seasons)s)",
                    {"seasons": season_list},
                )
                return cur.fetchall()

            if not season:
                raise HTTPException(400, "season or seasons is required")
            cur.execute(
                f"SELECT {PLAYER_STAT_COLUMNS} FROM player_seasons WHERE season = %(season)s",
                {"season": season},
            )
            return cur.fetchall()


@router.get("/api/stats/teams")
def get_team_stats(season: str | None = None, seasons: str | None = None, teams: str | None = None):
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if teams:
                team_list = [t.strip() for t in teams.split(",") if t.strip()]
                cur.execute(
                    f"SELECT {TEAM_STAT_COLUMNS} FROM team_seasons "
                    "WHERE team = ANY(%(teams)s) ORDER BY team, season",
                    {"teams": team_list},
                )
                return cur.fetchall()

            if seasons:
                season_list = [s.strip() for s in seasons.split(",") if s.strip()]
                cur.execute(
                    f"SELECT {TEAM_STAT_COLUMNS} FROM team_seasons "
                    "WHERE season = ANY(%(seasons)s)",
                    {"seasons": season_list},
                )
                return cur.fetchall()

            if season:
                cur.execute(
                    f"SELECT {TEAM_STAT_COLUMNS} FROM team_seasons WHERE season = %(season)s",
                    {"season": season},
                )
                return cur.fetchall()

            cur.execute(
                "SELECT DISTINCT ON (team) team, team_name "
                "FROM team_seasons ORDER BY team, season DESC"
            )
            return cur.fetchall()
