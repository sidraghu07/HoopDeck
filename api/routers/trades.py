from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel

from api.cba_rules import evaluate_trade_legality, fairness_verdict, unknown_legality
from api.db import pool
from api.lineup_engine import MODELS, assign_minutes, predict, roster_features

router = APIRouter()

TOP_N = 5


class TradeRequest(BaseModel):
    league: str
    team_a: str
    team_b: str
    players_from_a: list[int] = []
    players_from_b: list[int] = []
    picks_from_a: list[int] = []
    picks_from_b: list[int] = []
    season: str | None = None


def _fetch_roster(cur, league: str, team: str, season: str | None) -> dict[int, dict]:
    cur.execute(
        "SELECT tr.player_id, tr.player_name, tr.team, "
        "ps.season, ps.primary_position, ps.tier, "
        "ps.rating_overall, ps.rating_scoring, ps.rating_playmaking, ps.rating_defense, ps.rating_impact "
        "FROM team_rosters tr "
        "LEFT JOIN LATERAL ("
        "  SELECT * FROM player_seasons p "
        "  WHERE p.player_id = tr.player_id AND p.league = %(league)s "
        "  ORDER BY (p.season = COALESCE(%(season)s, tr.season)) DESC, p.season DESC "
        "  LIMIT 1"
        ") ps ON true "
        "WHERE tr.league = %(league)s AND tr.team = %(team)s",
        {"league": league, "team": team, "season": season},
    )
    return {row["player_id"]: row for row in cur.fetchall()}


def _evaluate(league: str, pool_rows: dict[int, dict]) -> dict:
    ratable = [dict(r) for r in pool_rows.values() if r["rating_overall"] is not None]
    if len(ratable) < TOP_N:
        raise HTTPException(400, "Not enough rated players on this roster to evaluate a top-5")

    top5 = sorted(ratable, key=lambda r: -r["rating_overall"])[:TOP_N]
    ranked = assign_minutes(top5)
    features = roster_features(ranked)
    net_rating, win_pct, record = predict(league, features)

    return {
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
                "tier": r["tier"],
                "rating_overall": r["rating_overall"],
                "assumed_minutes": round(r["assumed_minutes"], 1),
            }
            for r in ranked
        ],
    }


def _team_payroll(cur, league: str, team: str) -> int | None:
    cur.execute(
        "SELECT SUM(ps.salary) AS payroll, COUNT(ps.salary) AS n "
        "FROM team_rosters tr JOIN player_salaries ps "
        "ON tr.player_id = ps.player_id AND tr.league = ps.league "
        "WHERE tr.league = %(league)s AND tr.team = %(team)s",
        {"league": league, "team": team},
    )
    row = cur.fetchone()
    if not row or not row["n"]:
        return None
    return int(row["payroll"])


def _player_salaries(cur, league: str, player_ids: list[int]) -> dict[int, int]:
    if not player_ids:
        return {}
    cur.execute(
        "SELECT player_id, salary FROM player_salaries WHERE league = %(league)s AND player_id = ANY(%(ids)s)",
        {"league": league, "ids": player_ids},
    )
    return {r["player_id"]: r["salary"] for r in cur.fetchall()}


def _legality_for_team(cur, league: str, team: str, outgoing_ids: list[int], incoming_ids: list[int]) -> dict:
    if league != "NBA":
        return unknown_legality("CBA legality gate is NBA-only (basketball-reference has no WNBA contracts data).")

    payroll = _team_payroll(cur, league, team)
    if payroll is None:
        return unknown_legality(f"No salary data on file for {team}'s roster.")

    salaries = _player_salaries(cur, league, outgoing_ids + incoming_ids)
    missing = [pid for pid in outgoing_ids + incoming_ids if pid not in salaries]
    if missing:
        return unknown_legality(f"Missing salary data for player_id(s) {missing} involved in this trade.")

    outgoing = sum(salaries[pid] for pid in outgoing_ids)
    incoming = sum(salaries[pid] for pid in incoming_ids)
    return evaluate_trade_legality(payroll, outgoing, incoming)


def _fetch_picks(cur, league: str, pick_ids: list[int], expected_owner: str) -> list[dict]:
    if not pick_ids:
        return []
    cur.execute(
        "SELECT id, draft_year, round, original_team, current_owner, "
        "protection_note, trade_note, is_swap, source_url "
        "FROM draft_picks WHERE league = %(league)s AND id = ANY(%(ids)s)",
        {"league": league, "ids": pick_ids},
    )
    rows = cur.fetchall()
    found_ids = {r["id"] for r in rows}
    missing = set(pick_ids) - found_ids
    if missing:
        raise HTTPException(400, f"Unknown pick id(s): {sorted(missing)}")
    mismatched = [r for r in rows if r["current_owner"] != expected_owner]
    if mismatched:
        raise HTTPException(
            400,
            f"Pick(s) {[r['id'] for r in mismatched]} are not currently owned by {expected_owner!r}",
        )
    return rows


@router.post("/api/trades/simulate")
def simulate_trade(request: TradeRequest):
    league = request.league
    if league not in MODELS:
        raise HTTPException(400, f"Unsupported or unavailable league: {league!r}")

    overlap = set(request.players_from_a) & set(request.players_from_b)
    if overlap:
        raise HTTPException(400, f"Player(s) {sorted(overlap)} listed on both sides of the trade")

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            roster_a = _fetch_roster(cur, league, request.team_a, request.season)
            roster_b = _fetch_roster(cur, league, request.team_b, request.season)

            missing_a = [pid for pid in request.players_from_a if pid not in roster_a]
            if missing_a:
                raise HTTPException(400, f"Player(s) {missing_a} are not on {request.team_a}'s current roster")
            missing_b = [pid for pid in request.players_from_b if pid not in roster_b]
            if missing_b:
                raise HTTPException(400, f"Player(s) {missing_b} are not on {request.team_b}'s current roster")

            picks_from_a = _fetch_picks(cur, league, request.picks_from_a, request.team_a)
            picks_from_b = _fetch_picks(cur, league, request.picks_from_b, request.team_b)

            legality_a = _legality_for_team(
                cur, league, request.team_a, request.players_from_a, request.players_from_b
            )
            legality_b = _legality_for_team(
                cur, league, request.team_b, request.players_from_b, request.players_from_a
            )

    def _ratings(roster: dict[int, dict], player_ids: list[int]) -> list[int]:
        return [roster[pid]["rating_overall"] for pid in player_ids if roster[pid]["rating_overall"] is not None]

    ratings_from_a = _ratings(roster_a, request.players_from_a)
    ratings_from_b = _ratings(roster_b, request.players_from_b)
    fairness_a = fairness_verdict(ratings_from_a, ratings_from_b)
    fairness_b = fairness_verdict(ratings_from_b, ratings_from_a)

    if legality_a["legal"] is None or legality_b["legal"] is None:
        cba_legal = None
    else:
        cba_legal = legality_a["legal"] and legality_b["legal"]

    verdict = {
        "cba_legal": cba_legal,
        "team_a": {**legality_a, "fairness": fairness_a},
        "team_b": {**legality_b, "fairness": fairness_b},
    }

    before_a = _evaluate(league, roster_a)
    before_b = _evaluate(league, roster_b)

    after_a_pool = {pid: row for pid, row in roster_a.items() if pid not in request.players_from_a}
    after_a_pool.update({pid: roster_b[pid] for pid in request.players_from_b})
    after_b_pool = {pid: row for pid, row in roster_b.items() if pid not in request.players_from_b}
    after_b_pool.update({pid: roster_a[pid] for pid in request.players_from_a})

    after_a = _evaluate(league, after_a_pool)
    after_b = _evaluate(league, after_b_pool)

    return {
        "league": league,
        "verdict": verdict,
        "team_a": {"team": request.team_a, "before": before_a, "after": after_a},
        "team_b": {"team": request.team_b, "before": before_b, "after": after_b},
        "picks_exchanged": {"from_a": picks_from_a, "from_b": picks_from_b},
    }
