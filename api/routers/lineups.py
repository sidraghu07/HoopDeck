from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel

from api.db import pool
from api.lineup_engine import (
    MODELS,
    apply_out_of_position_penalty,
    assign_minutes,
    predict,
    roster_features,
)

router = APIRouter()


class LineupPlayer(BaseModel):
    player_id: int
    season: str
    position: str | None = None


class LineupRequest(BaseModel):
    league: str
    players: list[LineupPlayer]


@router.post("/api/lineups/simulate")
def simulate_lineup(request: LineupRequest):
    if not (5 <= len(request.players) <= 15):
        raise HTTPException(400, "Roster must have between 5 and 15 players")

    league = request.league
    if league not in MODELS:
        raise HTTPException(400, f"Unsupported or unavailable league: {league!r}")

    rows = []
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            for p in request.players:
                cur.execute(
                    "SELECT player_id, player_name, season, league, team, positions, primary_position, tier, "
                    "rating_overall, rating_scoring, rating_playmaking, rating_defense, rating_impact "
                    "FROM player_seasons WHERE player_id = %(pid)s AND season = %(season)s",
                    {"pid": p.player_id, "season": p.season},
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(
                        404, f"No data for player_id={p.player_id} season={p.season}"
                    )
                if row["league"] != league:
                    raise HTTPException(
                        400,
                        f"{row['player_name']} ({row['season']}) is a {row['league']} player, "
                        f"but this lineup is {league} — leagues cannot be mixed",
                    )

                row["assigned_position"] = None
                row["out_of_position_penalty"] = 0
                if p.position:
                    cur.execute(
                        "SELECT scoring, playmaking, defense, impact, overall "
                        "FROM ratings_by_position "
                        "WHERE player_id = %(pid)s AND season = %(season)s AND position = %(pos)s",
                        {"pid": p.player_id, "season": p.season, "pos": p.position},
                    )
                    pos_row = cur.fetchone()
                    row["assigned_position"] = p.position
                    if pos_row is not None:
                        row["rating_scoring"] = pos_row["scoring"]
                        row["rating_playmaking"] = pos_row["playmaking"]
                        row["rating_defense"] = pos_row["defense"]
                        row["rating_impact"] = pos_row["impact"]
                        row["rating_overall"] = pos_row["overall"]
                    else:
                        row["out_of_position_penalty"] = apply_out_of_position_penalty(
                            row, p.position, league
                        )

                rows.append(row)

    ranked = assign_minutes(rows)
    features = roster_features(ranked)
    net_rating, win_pct, record = predict(league, features)

    return {
        "league": league,
        "predicted_net_rating": round(net_rating, 2),
        "predicted_win_pct": round(win_pct, 4),
        "predicted_record": record,
        "roster_features": {k: round(v, 1) for k, v in features.items()},
        "roster": [
            {
                "player_id": r["player_id"],
                "player_name": r["player_name"],
                "season": r["season"],
                "team": r["team"],
                "primary_position": r["primary_position"],
                "assigned_position": r["assigned_position"],
                "tier": r["tier"],
                "rating_overall": r["rating_overall"],
                "out_of_position_penalty": r["out_of_position_penalty"],
                "assumed_minutes": round(r["assumed_minutes"], 1),
            }
            for r in ranked
        ],
    }
