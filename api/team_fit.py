LOOKBACK_SEASONS = 3
_SEASON_WEIGHTS = [0.5, 0.3, 0.2]

CONTENDING = "contending"
RETOOLING = "retooling"
REBUILDING = "rebuilding"

NEED = "need"
NEUTRAL = "neutral"
REDUNDANT = "redundant"

WOULD_ACCEPT = "would_accept"
WOULD_REJECT = "would_reject"
MIXED = "mixed"
UNKNOWN = "unknown"

NEED_UPGRADE_THRESHOLD = 5
REDUNDANT_MIN_DEPTH = 3

PICK_ROUND_WEIGHT = {1: 2, 2: 1}
SWAP_WEIGHT_MULTIPLIER = 0.5
SIGNIFICANT_CAPITAL_DELTA = 2.0

GAINING = "gaining"
LOSING = "losing"
CAPITAL_NEUTRAL = "neutral"


def _percentile(value: float, population: list[float]) -> float:
    if not population:
        return 0.5
    below = sum(1 for v in population if v < value)
    return below / len(population)


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th'][n % 10]}"


def team_timeline(recent_seasons: list[dict], league_season_net_ratings: list[float]) -> dict:
    if not recent_seasons:
        return {"bucket": None, "trend_net_rating": None, "seasons_used": 0,
                "reason": "No team_seasons history on file for this team."}

    weights = _SEASON_WEIGHTS[:len(recent_seasons)]
    total_weight = sum(weights)
    trend = sum(w * s["net_rating"] for w, s in zip(weights, recent_seasons)) / total_weight

    pct = _percentile(recent_seasons[0]["net_rating"], league_season_net_ratings)
    if pct > 0.66:
        bucket = CONTENDING
    elif pct < 0.33:
        bucket = REBUILDING
    else:
        bucket = RETOOLING

    return {
        "bucket": bucket,
        "trend_net_rating": round(trend, 2),
        "seasons_used": len(recent_seasons),
        "reason": (
            f"{bucket.capitalize()} — net rating trend of {trend:+.1f} over the last "
            f"{len(recent_seasons)} season(s) ({_ordinal(round(pct * 100))} percentile league-wide)."
        ),
    }


def position_fit(incoming: list[dict], outgoing_ids: set[int], roster: dict[int, dict]) -> dict:
    if not incoming:
        return {"fit": NEUTRAL, "position": None, "reason": "No players incoming to evaluate."}

    verdicts = []
    reasons = []
    for player in incoming:
        position = player.get("primary_position")
        incoming_rating = player.get("rating_overall")
        if position is None or incoming_rating is None:
            continue

        peers = [
            r for pid, r in roster.items()
            if pid not in outgoing_ids
            and pid != player.get("player_id")
            and r.get("primary_position") == position
            and r.get("rating_overall") is not None
        ]
        count = len(peers)
        avg_rating = sum(r["rating_overall"] for r in peers) / count if count else None
        best_rating = max((r["rating_overall"] for r in peers), default=None)

        if count <= 1 or (best_rating is not None and incoming_rating - best_rating >= NEED_UPGRADE_THRESHOLD):
            verdicts.append(NEED)
            reasons.append(f"{player.get('player_name', 'Player')} addresses a need at {position} "
                            f"({count} rated player(s) there currently).")
        elif count >= REDUNDANT_MIN_DEPTH and avg_rating is not None and incoming_rating < avg_rating:
            verdicts.append(REDUNDANT)
            reasons.append(f"{player.get('player_name', 'Player')} adds redundant depth at {position} "
                            f"({count} rated players already there, avg {avg_rating:.0f}).")
        else:
            verdicts.append(NEUTRAL)
            reasons.append(f"{player.get('player_name', 'Player')} is a neutral fit at {position}.")

    if not verdicts:
        return {"fit": NEUTRAL, "position": None, "reason": "No ratable incoming players to evaluate."}

    if NEED in verdicts and REDUNDANT not in verdicts:
        fit = NEED
    elif REDUNDANT in verdicts and NEED not in verdicts:
        fit = REDUNDANT
    else:
        fit = NEUTRAL

    return {"fit": fit, "position": incoming[0].get("primary_position"), "reason": " ".join(reasons)}


def _pick_weight(pick: dict) -> float:
    weight = PICK_ROUND_WEIGHT.get(pick.get("round"), 0)
    if pick.get("is_swap"):
        weight *= SWAP_WEIGHT_MULTIPLIER
    return weight


def pick_capital(picks_sent: list[dict], picks_received: list[dict]) -> dict:
    sent = sum(_pick_weight(p) for p in picks_sent)
    received = sum(_pick_weight(p) for p in picks_received)
    delta = received - sent

    if delta >= SIGNIFICANT_CAPITAL_DELTA:
        bucket = GAINING
    elif delta <= -SIGNIFICANT_CAPITAL_DELTA:
        bucket = LOSING
    else:
        bucket = CAPITAL_NEUTRAL

    r1_recv = sum(1 for p in picks_received if p.get("round") == 1)
    r2_recv = sum(1 for p in picks_received if p.get("round") == 2)
    r1_sent = sum(1 for p in picks_sent if p.get("round") == 1)
    r2_sent = sum(1 for p in picks_sent if p.get("round") == 2)

    return {
        "bucket": bucket,
        "delta": round(delta, 1),
        "reason": (
            f"Receives {r1_recv} first-rounder(s) and {r2_recv} second-rounder(s); "
            f"sends {r1_sent} first-rounder(s) and {r2_sent} second-rounder(s) "
            f"(net draft capital {delta:+.1f})."
        ),
    }


_VERDICT_ORDER = [WOULD_REJECT, MIXED, WOULD_ACCEPT]

_PICK_ADJUSTMENT = {
    (REBUILDING, GAINING): 1,
    (REBUILDING, LOSING): -1,
    (CONTENDING, LOSING): 1,
    (CONTENDING, GAINING): -1,
}

_PICK_REASON = {
    (REBUILDING, GAINING): "This deal also nets real draft capital during a rebuild, reinforcing the accumulation strategy.",
    (REBUILDING, LOSING): "This deal also spends draft capital while rebuilding, cutting against the accumulation strategy.",
    (CONTENDING, LOSING): "This deal also spends draft capital to win now, normal for a contending timeline.",
    (CONTENDING, GAINING): "This deal also stockpiles draft picks instead of immediate talent, a mismatch for a contending timeline.",
}


_MATRIX = {
    (NEED, CONTENDING): WOULD_ACCEPT,
    (NEED, RETOOLING): WOULD_ACCEPT,
    (NEED, REBUILDING): MIXED,
    (NEUTRAL, CONTENDING): MIXED,
    (NEUTRAL, RETOOLING): MIXED,
    (NEUTRAL, REBUILDING): MIXED,
    (REDUNDANT, CONTENDING): MIXED,
    (REDUNDANT, RETOOLING): MIXED,
    (REDUNDANT, REBUILDING): WOULD_REJECT,
}

_NO_TIMELINE_FALLBACK = {NEED: MIXED, NEUTRAL: UNKNOWN, REDUNDANT: MIXED}


def team_fit_verdict(position: dict, timeline: dict, picks: dict) -> dict:
    pos_fit = position["fit"]
    bucket = timeline["bucket"]

    if bucket is None:
        verdict = _NO_TIMELINE_FALLBACK[pos_fit]
        reason = f"{position['reason']} Timeline unknown — {timeline['reason']}"
    else:
        verdict = _MATRIX[(pos_fit, bucket)]
        reason = f"{timeline['reason']} {position['reason']}"

        adjustment = _PICK_ADJUSTMENT.get((bucket, picks["bucket"]), 0)
        if adjustment:
            new_index = _VERDICT_ORDER.index(verdict) + adjustment
            new_index = max(0, min(len(_VERDICT_ORDER) - 1, new_index))
            verdict = _VERDICT_ORDER[new_index]
            reason = f"{reason} {_PICK_REASON[(bucket, picks['bucket'])]}"

    return {
        "position_fit": pos_fit,
        "timeline_fit": bucket,
        "pick_fit": picks["bucket"],
        "verdict": verdict,
        "reason": reason,
    }
