import json
import os

from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel

from api.db import pool

router = APIRouter()

MODEL_PATH = os.environ.get("LINEUP_MODEL_PATH", "data/output/lineup_model.json")
with open(MODEL_PATH) as f:
    MODEL = json.load(f)


class LineupPlayer(BaseModel):
    player_id: int
    season: str
    position: str | None = None


class LineupRequest(BaseModel):
    players: list[LineupPlayer]


MAX_MINUTES = 48.0


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

    rows = []
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            for p in request.players:
                cur.execute(
                    "SELECT player_id, player_name, season, team, primary_position, tier, "
                    "rating_overall, rating_scoring, rating_playmaking, rating_defense, rating_impact "
                    "FROM player_seasons WHERE player_id = %(pid)s AND season = %(season)s",
                    {"pid": p.player_id, "season": p.season},
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(
                        404, f"No data for player_id={p.player_id} season={p.season}"
                    )

                row["assigned_position"] = None
                if p.position:
                    cur.execute(
                        "SELECT scoring, playmaking, defense, impact, overall "
                        "FROM ratings_by_position "
                        "WHERE player_id = %(pid)s AND season = %(season)s AND position = %(pos)s",
                        {"pid": p.player_id, "season": p.season, "pos": p.position},
                    )
                    pos_row = cur.fetchone()
                    if pos_row is not None:
                        row["rating_scoring"] = pos_row["scoring"]
                        row["rating_playmaking"] = pos_row["playmaking"]
                        row["rating_defense"] = pos_row["defense"]
                        row["rating_impact"] = pos_row["impact"]
                        row["rating_overall"] = pos_row["overall"]
                        row["assigned_position"] = p.position

                rows.append(row)

    ranked = _assign_minutes(rows)
    features = _roster_features(ranked)

    stage_a = MODEL["stage_a"]
    x = [features[f] for f in stage_a["features"]]
    net_rating = sum(c * v for c, v in zip(stage_a["coef"], x)) + stage_a["intercept"]

    stage_b = MODEL["stage_b"]
    win_pct = stage_b["coef"] * net_rating + stage_b["intercept"]
    win_pct = max(0.0, min(1.0, win_pct))
    wins = round(win_pct * 82)

    return {
        "predicted_net_rating": round(net_rating, 2),
        "predicted_win_pct": round(win_pct, 4),
        "predicted_record": f"{wins}-{82 - wins}",
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
                "assumed_minutes": round(r["assumed_minutes"], 1),
            }
            for r in ranked
        ],
    }
