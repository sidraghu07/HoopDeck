from fastapi import APIRouter
from psycopg.rows import dict_row

from api.db import pool

router = APIRouter()


@router.get("/api/teams/{league}")
def get_current_teams(league: str):
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT DISTINCT tr.team, COALESCE(ts.team_name, tr.team) AS team_name "
                "FROM team_rosters tr "
                "LEFT JOIN LATERAL ("
                "  SELECT team_name FROM team_seasons s "
                "  WHERE s.team = tr.team AND s.league = tr.league "
                "  ORDER BY s.season DESC LIMIT 1"
                ") ts ON true "
                "WHERE tr.league = %(league)s "
                "ORDER BY tr.team",
                {"league": league},
            )
            return cur.fetchall()


@router.get("/api/teams/{league}/{team}/roster")
def get_team_roster(league: str, team: str, season: str | None = None):
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT tr.player_id, tr.player_name, tr.team, tr.jersey_num, tr.how_acquired, "
                "tr.season AS roster_season, "
                "ps.season, ps.primary_position, ps.tier, ps.rating_overall, "
                "(ps.season IS NOT NULL AND ps.season != COALESCE(%(season)s, tr.season)) AS is_fallback_season "
                "FROM team_rosters tr "
                "LEFT JOIN LATERAL ("
                "  SELECT * FROM player_seasons p "
                "  WHERE p.player_id = tr.player_id AND p.league = %(league)s "
                "  ORDER BY (p.season = COALESCE(%(season)s, tr.season)) DESC, p.season DESC "
                "  LIMIT 1"
                ") ps ON true "
                "WHERE tr.league = %(league)s AND tr.team = %(team)s "
                "ORDER BY ps.rating_overall DESC NULLS LAST",
                {"league": league, "team": team, "season": season},
            )
            return cur.fetchall()


@router.get("/api/teams/{league}/{team}/picks")
def get_team_picks(league: str, team: str):
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, draft_year, round, original_team, current_owner, "
                "protection_note, trade_note, is_swap, source_url "
                "FROM draft_picks WHERE league = %(league)s AND current_owner = %(team)s "
                "ORDER BY draft_year, round",
                {"league": league, "team": team},
            )
            return cur.fetchall()
