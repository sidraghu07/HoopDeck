import json
import os

from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel

from api.db import pool

router = APIRouter()

MODEL_PATHS = {
    "NBA": os.environ.get("LINEUP_MODEL_PATH_NBA", "data/output/lineup_model_nba.json"),
    "WNBA": os.environ.get("LINEUP_MODEL_PATH_WNBA", "data/output/lineup_model_wnba.json"),
}
MODELS: dict = {}
for _league, _path in MODEL_PATHS.items():
    if os.path.exists(_path):
        with open(_path) as f:
            MODELS[_league] = json.load(f)


class LineupPlayer(BaseModel):
    player_id: int
    season: str
    position: str | None = None


class LineupRequest(BaseModel):
    league: str
    players: list[LineupPlayer]


MAX_MINUTES = 48.0
RATING_FLOOR = 25

# Games in a full season, used to render the predicted W-L record. WNBA seasons
# have historically ranged 28-44 games; 44 (the 2025 season length) is used as
# the current-era default rather than an all-time-average figure.
SEASON_GAME_COUNT = {"NBA": 82, "WNBA": 44}

# Position ladders + out-of-position penalty tables, per league. NBA's 5-way
# taxonomy allows up to 4 steps of separation; WNBA's 3-way G/F/C taxonomy
# only allows 2, and that single "distance 2" (G<->C) is always the most
# extreme mismatch possible in that system, so it's penalized close to NBA's
# harshest (distance-4) value rather than a naive truncation of the NBA table.
POSITION_ORDER = {
    "NBA": ["PG", "SG", "SF", "PF", "C"],
    "WNBA": ["G", "F", "C"],
}
OUT_OF_POSITION_PENALTY = {
    "NBA": {1: 4, 2: 9, 3: 15, 4: 22},
    "WNBA": {1: 6, 2: 20},
}


def _position_distance(position_order: list[str], natural_positions: list[str], target: str) -> int:
    if target not in position_order:
        return 0
    natural_idx = [position_order.index(p) for p in natural_positions if p in position_order]
    if not natural_idx:
        return 0
    target_idx = position_order.index(target)
    return min(abs(target_idx - i) for i in natural_idx)


def _apply_out_of_position_penalty(row: dict, target: str, league: str) -> int:
    """Docks ratings when a player is slotted away from their natural position(s).

    Direction matters: a guard pushed up towards the frontcourt gets hit
    hardest on defense/impact (post-ups, rebounding), while a big pushed down
    towards the backcourt gets hit hardest on playmaking/defense (ballhandling,
    quickness).
    """
    position_order = POSITION_ORDER[league]
    penalty_table = OUT_OF_POSITION_PENALTY[league]
    natural_idx = [position_order.index(p) for p in row["positions"] if p in position_order]
    distance = _position_distance(position_order, row["positions"], target)
    if distance == 0 or not natural_idx:
        return 0

    penalty = penalty_table.get(distance, max(penalty_table.values()))
    target_idx = position_order.index(target)
    playing_up = target_idx > max(natural_idx)
    playing_down = target_idx < min(natural_idx)

    row["rating_scoring"] = max(RATING_FLOOR, row["rating_scoring"] - round(penalty * 0.6))
    if playing_up:
        row["rating_playmaking"] = max(RATING_FLOOR, row["rating_playmaking"] - round(penalty * 0.6))
        row["rating_defense"] = max(RATING_FLOOR, row["rating_defense"] - round(penalty * 1.3))
        row["rating_impact"] = max(RATING_FLOOR, row["rating_impact"] - round(penalty * 1.1))
    elif playing_down:
        row["rating_playmaking"] = max(RATING_FLOOR, row["rating_playmaking"] - round(penalty * 1.3))
        row["rating_defense"] = max(RATING_FLOOR, row["rating_defense"] - round(penalty * 1.0))
        row["rating_impact"] = max(RATING_FLOOR, row["rating_impact"] - round(penalty * 0.8))
    row["rating_overall"] = max(RATING_FLOOR, row["rating_overall"] - penalty)
    return penalty


def _assign_minutes(rows: list[dict]) -> list[dict]:
    ranked = sorted(rows, key=lambda r: -r["rating_overall"])
    raw = [max(1.0, 36.0 - 1.8 * i) for i in range(len(ranked))]
    total_raw = sum(raw)
    minutes = [m / total_raw * 240.0 for m in raw]

    for _ in range(len(minutes)):
        capped = [m > MAX_MINUTES for m in minutes]
        overflow = sum(m - MAX_MINUTES for m in minutes if m > MAX_MINUTES)
        if overflow <= 1e-9:
            break
        for i, over in enumerate(capped):
            if over:
                minutes[i] = MAX_MINUTES
        uncapped_idx = [i for i, c in enumerate(capped) if not c]
        if not uncapped_idx:
            break
        uncapped_total = sum(minutes[i] for i in uncapped_idx)
        for i in uncapped_idx:
            minutes[i] += overflow * (minutes[i] / uncapped_total)

    for r, m in zip(ranked, minutes):
        r["assumed_minutes"] = min(m, MAX_MINUTES)
    return ranked


def _weighted_avg(rows: list[dict], key: str) -> float:
    total_w = sum(r["assumed_minutes"] for r in rows)
    return sum(r[key] * r["assumed_minutes"] for r in rows) / total_w


def _roster_features(ranked: list[dict]) -> dict:
    bench = ranked[2:]
    bench_overall = (
        _weighted_avg(bench, "rating_overall")
        if bench
        else _weighted_avg(ranked, "rating_overall")
    )
    return {
        "avg_scoring": _weighted_avg(ranked, "rating_scoring"),
        "avg_playmaking": _weighted_avg(ranked, "rating_playmaking"),
        "avg_defense": _weighted_avg(ranked, "rating_defense"),
        "avg_impact": _weighted_avg(ranked, "rating_impact"),
        "avg_overall": _weighted_avg(ranked, "rating_overall"),
        "star_power": max(r["rating_overall"] for r in ranked),
        "bench_overall": bench_overall,
    }


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
                        row["out_of_position_penalty"] = _apply_out_of_position_penalty(
                            row, p.position, league
                        )

                rows.append(row)

    ranked = _assign_minutes(rows)
    features = _roster_features(ranked)

    model = MODELS[league]
    stage_a = model["stage_a"]
    x = [features[f] for f in stage_a["features"]]
    net_rating = sum(c * v for c, v in zip(stage_a["coef"], x)) + stage_a["intercept"]

    stage_b = model["stage_b"]
    win_pct = stage_b["coef"] * net_rating + stage_b["intercept"]
    win_pct = max(0.0, min(1.0, win_pct))
    season_games = SEASON_GAME_COUNT[league]
    wins = round(win_pct * season_games)

    return {
        "league": league,
        "predicted_net_rating": round(net_rating, 2),
        "predicted_win_pct": round(win_pct, 4),
        "predicted_record": f"{wins}-{season_games - wins}",
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
