
import json
import os

MODEL_PATHS = {
    "NBA": os.environ.get("LINEUP_MODEL_PATH_NBA", "data/output/lineup_model_nba.json"),
    "WNBA": os.environ.get("LINEUP_MODEL_PATH_WNBA", "data/output/lineup_model_wnba.json"),
}
MODELS: dict = {}
for _league, _path in MODEL_PATHS.items():
    if os.path.exists(_path):
        with open(_path) as f:
            MODELS[_league] = json.load(f)


MAX_MINUTES = 48.0
RATING_FLOOR = 25

SEASON_GAME_COUNT = {"NBA": 82, "WNBA": 44}

POSITION_ORDER = {
    "NBA": ["PG", "SG", "SF", "PF", "C"],
    "WNBA": ["G", "F", "C"],
}
OUT_OF_POSITION_PENALTY = {
    "NBA": {1: 4, 2: 9, 3: 15, 4: 22},
    "WNBA": {1: 6, 2: 20},
}


def position_distance(position_order: list[str], natural_positions: list[str], target: str) -> int:
    if target not in position_order:
        return 0
    natural_idx = [position_order.index(p) for p in natural_positions if p in position_order]
    if not natural_idx:
        return 0
    target_idx = position_order.index(target)
    return min(abs(target_idx - i) for i in natural_idx)


def apply_out_of_position_penalty(row: dict, target: str, league: str) -> int:
    position_order = POSITION_ORDER[league]
    penalty_table = OUT_OF_POSITION_PENALTY[league]
    natural_idx = [position_order.index(p) for p in row["positions"] if p in position_order]
    distance = position_distance(position_order, row["positions"], target)
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


def assign_minutes(rows: list[dict]) -> list[dict]:
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


def roster_features(ranked: list[dict]) -> dict:
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


def predict(league: str, features: dict) -> tuple[float, float, str]:
    model = MODELS[league]
    stage_a = model["stage_a"]
    x = [features[f] for f in stage_a["features"]]
    net_rating = sum(c * v for c, v in zip(stage_a["coef"], x)) + stage_a["intercept"]

    stage_b = model["stage_b"]
    win_pct = stage_b["coef"] * net_rating + stage_b["intercept"]
    win_pct = max(0.0, min(1.0, win_pct))
    season_games = SEASON_GAME_COUNT[league]
    wins = round(win_pct * season_games)

    return net_rating, win_pct, f"{wins}-{season_games - wins}"
