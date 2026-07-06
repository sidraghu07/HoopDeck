from fastapi import APIRouter
from psycopg.rows import dict_row

from api.db import pool

router = APIRouter()

TIER_RANK_SQL = """
    CASE tier
        WHEN 'Franchise Player' THEN 4
        WHEN 'All-Star' THEN 3
        WHEN 'Starter' THEN 2
        WHEN 'Rotation' THEN 1
        ELSE 0
    END
"""


def _build_filters(tier: str | None, position: str | None, name: str | None):
    clauses: list[str] = []
    params: dict = {}
    if tier:
        clauses.append("tier = %(tier)s")
        params["tier"] = tier
    if position:
        clauses.append("%(position)s = ANY(positions)")
        params["position"] = position
    if name:
        clauses.append("player_name ILIKE %(name)s")
        params["name"] = f"%{name}%"
    return clauses, params


def _season_card(r: dict) -> dict:
    return {
        "player_id": r["player_id"],
        "player_name": r["player_name"],
        "season": r["season"],
        "team": r["team"],
        "primary_position": r["primary_position"],
        "tier": r["tier"],
        "has_photo": r["has_photo"],
        "ratings": {
            "overall": r["rating_overall"],
            "scoring": r["rating_scoring"],
            "playmaking": r["rating_playmaking"],
            "defense": r["rating_defense"],
            "impact": r["rating_impact"],
        },
        "per_game": {
            "pts": r["pg_pts"], "reb": r["pg_reb"], "ast": r["pg_ast"],
            "stl": r["pg_stl"], "blk": r["pg_blk"], "min": r["pg_min"],
        },
    }


def _career_card(r: dict) -> dict:
    return {
        "player_id": r["player_id"],
        "player_name": r["player_name"],
        "career": {
            "bestTier": r["best_tier"],
            "bestOverall": r["best_overall"],
            "seasonsPlayed": r["seasons_played"],
            "teams": r["teams"],
            "primary_position": r["primary_position"],
            "has_photo": r["has_photo"],
            "per_game": {
                "pts": round(r["avg_pts"], 1), "reb": round(r["avg_reb"], 1),
                "ast": round(r["avg_ast"], 1), "stl": round(r["avg_stl"], 1),
                "blk": round(r["avg_blk"], 1), "min": round(r["avg_min"], 1),
            },
            "ratings": {
                "overall": round(r["avg_overall"], 1), "scoring": round(r["avg_scoring"], 1),
                "playmaking": round(r["avg_playmaking"], 1), "defense": round(r["avg_defense"], 1),
                "impact": round(r["avg_impact"], 1),
            },
        },
    }


MAX_PAGE_SIZE = 200

SORT_COLUMNS_SEASON = {
    "overall": "rating_overall",
    "pts": "pg_pts",
    "reb": "pg_reb",
    "ast": "pg_ast",
    "stl": "pg_stl",
    "blk": "pg_blk",
    "min": "pg_min",
}
SORT_COLUMNS_CAREER = {
    "overall": "avg_overall",
    "pts": "avg_pts",
    "reb": "avg_reb",
    "ast": "avg_ast",
    "stl": "avg_stl",
    "blk": "avg_blk",
    "min": "avg_min",
}


@router.get("/api/players")
def get_players(
    season: str | None = None,
    tier: str | None = None,
    position: str | None = None,
    name: str | None = None,
    page: int = 1,
    page_size: int = 60,
    sort: str = "overall",
    dir: str = "desc",
):
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    sort_dir = "ASC" if dir == "asc" else "DESC"

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT DISTINCT season FROM player_seasons ORDER BY season DESC")
            seasons = [r["season"] for r in cur.fetchall()]

            clauses, params = _build_filters(tier, position, name)

            if season and season != "ALL":
                sort_col = SORT_COLUMNS_SEASON.get(sort, SORT_COLUMNS_SEASON["overall"])
                clauses.append("season = %(season)s")
                params["season"] = season
                where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
                cur.execute(
                    f"""
                    SELECT player_seasons.player_id, season, player_name, team, primary_position, tier,
                           rating_overall, rating_scoring, rating_playmaking, rating_defense,
                           rating_impact, pg_pts, pg_reb, pg_ast, pg_stl, pg_blk, pg_min,
                           COALESCE(player_photos.has_photo, true) AS has_photo
                    FROM player_seasons
                    LEFT JOIN player_photos ON player_photos.player_id = player_seasons.player_id
                    {where}
                    ORDER BY {sort_col} {sort_dir}
                    """,
                    params,
                )
                players = [_season_card(r) for r in cur.fetchall()]
                return {"players": players, "meta": {"seasons": seasons, "total": len(players)}}

            sort_col = SORT_COLUMNS_CAREER.get(sort, SORT_COLUMNS_CAREER["overall"])
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            offset = (page - 1) * page_size
            cur.execute(
                f"""
                WITH filtered AS (
                    SELECT player_seasons.*, COALESCE(player_photos.has_photo, true) AS has_photo
                    FROM player_seasons
                    LEFT JOIN player_photos ON player_photos.player_id = player_seasons.player_id
                    {where}
                ),
                agg AS (
                    SELECT
                        player_id,
                        (array_agg(player_name ORDER BY season DESC))[1] AS player_name,
                        (array_agg(primary_position ORDER BY season DESC))[1] AS primary_position,
                        (array_agg(has_photo))[1] AS has_photo,
                        array_agg(DISTINCT team) AS teams,
                        count(*) AS seasons_played,
                        max(rating_overall) AS best_overall,
                        sum(rating_overall * games_played)::float / sum(games_played) AS avg_overall,
                        sum(rating_scoring * games_played)::float / sum(games_played) AS avg_scoring,
                        sum(rating_playmaking * games_played)::float / sum(games_played) AS avg_playmaking,
                        sum(rating_defense * games_played)::float / sum(games_played) AS avg_defense,
                        sum(rating_impact * games_played)::float / sum(games_played) AS avg_impact,
                        sum(pg_pts * games_played)::float / sum(games_played) AS avg_pts,
                        sum(pg_reb * games_played)::float / sum(games_played) AS avg_reb,
                        sum(pg_ast * games_played)::float / sum(games_played) AS avg_ast,
                        sum(pg_stl * games_played)::float / sum(games_played) AS avg_stl,
                        sum(pg_blk * games_played)::float / sum(games_played) AS avg_blk,
                        sum(pg_min * games_played)::float / sum(games_played) AS avg_min
                    FROM filtered
                    GROUP BY player_id
                ),
                best_tier AS (
                    SELECT DISTINCT ON (player_id) player_id, tier AS best_tier
                    FROM filtered
                    ORDER BY player_id, {TIER_RANK_SQL} DESC
                )
                SELECT agg.*, best_tier.best_tier, count(*) OVER () AS total_count
                FROM agg JOIN best_tier USING (player_id)
                ORDER BY {sort_col} {sort_dir}
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                {**params, "limit": page_size, "offset": offset},
            )
            rows = cur.fetchall()
            total = rows[0]["total_count"] if rows else 0
            players = [_career_card(r) for r in rows]
            return {
                "players": players,
                "meta": {
                    "seasons": seasons,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": max(1, -(-total // page_size)),
                },
            }


@router.get("/api/players/{player_id}")
def get_player(player_id: int, season: str | None = None):
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            clauses = ["player_seasons.player_id = %(player_id)s"]
            params: dict = {"player_id": player_id}
            if season:
                clauses.append("season = %(season)s")
                params["season"] = season
            cur.execute(
                f"""
                SELECT player_seasons.*, COALESCE(player_photos.has_photo, true) AS has_photo
                FROM player_seasons
                LEFT JOIN player_photos ON player_photos.player_id = player_seasons.player_id
                WHERE {' AND '.join(clauses)}
                ORDER BY season
                """,
                params,
            )
            season_rows = cur.fetchall()
            if not season_rows:
                return []

            cur.execute(
                "SELECT * FROM shot_zones WHERE player_id = %(player_id)s",
                {"player_id": player_id},
            )
            zone_rows = cur.fetchall()

    zones_by_season: dict = {}
    for z in zone_rows:
        zones_by_season.setdefault(z["season"], {})[z["zone_slug"]] = {
            "attempts": z["attempts"], "makes": z["makes"], "misses": z["misses"],
            "fg_pct": z["fg_pct"], "freq_pct": z["freq_pct"], "is_3pt": z["is_3pt"],
            "volume_rating": z["volume_rating"], "efficiency_rating": z["efficiency_rating"],
            "hot_score": z["hot_score"], "is_hot_zone": z["is_hot_zone"],
            "insufficient_sample": z["insufficient_sample"],
        }

    def _full_season(r: dict) -> dict:
        zones = zones_by_season.get(r["season"], {})
        hottest = max(zones.items(), key=lambda kv: kv[1]["hot_score"])[0] if zones else None
        return {
            "player_id": r["player_id"],
            "player_name": r["player_name"],
            "season": r["season"],
            "team": r["team"],
            "age": r["age"],
            "positions": r["positions"],
            "primary_position": r["primary_position"],
            "tier": r["tier"],
            "has_photo": r["has_photo"],
            "availability": {
                "games_played": r["games_played"],
                "scheduled_games": r["scheduled_games"],
                "availability_pct": r["availability_pct"],
                "roster_status": r["roster_status"],
            },
            "ratings": {
                "overall": r["rating_overall"], "scoring": r["rating_scoring"],
                "playmaking": r["rating_playmaking"], "defense": r["rating_defense"],
                "impact": r["rating_impact"],
            },
            "per_game": {
                "pts": r["pg_pts"], "reb": r["pg_reb"], "ast": r["pg_ast"],
                "stl": r["pg_stl"], "blk": r["pg_blk"], "tov": r["pg_tov"],
                "min": r["pg_min"], "oreb": r["pg_oreb"], "dreb": r["pg_dreb"],
            },
            "scoring": {
                "fg_pct": r["fg_pct"], "fg3_pct": r["fg3_pct"], "ft_pct": r["ft_pct"],
                "efg_pct": r["efg_pct"], "ts_pct": r["ts_pct"],
                "fg3a_per_game": r["fg3a_per_game"], "fga_per_game": r["fga_per_game"],
                "pct_uast_fgm": r["pct_uast_fgm"],
            },
            "advanced": {
                "off_rating": r["off_rating"], "def_rating": r["def_rating"], "net_rating": r["net_rating"],
                "ast_pct": r["ast_pct"], "ast_to": r["ast_to"], "usg_pct": r["usg_pct"],
                "oreb_pct": r["oreb_pct"], "dreb_pct": r["dreb_pct"], "pie": r["pie"],
                "pace": r["pace"], "plus_minus": r["plus_minus"], "e_tov_pct": r["e_tov_pct"],
            },
            "clutch": {"clutch_plus_minus": r["clutch_plus_minus"]},
            "shot_zones": zones,
            "hottest_zone": hottest,
            "total_charted_fga": r["total_charted_fga"],
        }

    return [_full_season(r) for r in season_rows]
