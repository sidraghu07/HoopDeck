
SALARY_CAP = 154_647_000
TAX_LINE = 187_895_000
FIRST_APRON = 195_945_000
SECOND_APRON = 207_824_000

BELOW_CAP = "below_cap"
UNDER_FIRST_APRON = "under_first_apron"
UNDER_SECOND_APRON = "under_second_apron"
OVER_SECOND_APRON = "over_second_apron"

_TIER_LABELS = {
    BELOW_CAP: "below the salary cap",
    UNDER_FIRST_APRON: "over the cap, under the first apron",
    UNDER_SECOND_APRON: "over the first apron",
    OVER_SECOND_APRON: "over the second apron",
}


def matching_tier(payroll: int) -> str:
    if payroll < SALARY_CAP:
        return BELOW_CAP
    if payroll < FIRST_APRON:
        return UNDER_FIRST_APRON
    if payroll < SECOND_APRON:
        return UNDER_SECOND_APRON
    return OVER_SECOND_APRON


def max_incoming_salary(tier: str, outgoing: int, cap_room: int = 0) -> float:
    if tier == BELOW_CAP:
        return cap_room + outgoing
    if tier == UNDER_FIRST_APRON:
        if outgoing <= 7_250_000:
            return outgoing * 2 + 250_000
        if outgoing <= 29_000_000:
            return outgoing + 7_500_000
        return outgoing * 1.25 + 250_000
    if tier == UNDER_SECOND_APRON:
        return outgoing * 1.10
    return float(outgoing)


def evaluate_trade_legality(payroll: int, outgoing: int, incoming: int) -> dict:
    tier = matching_tier(payroll)
    cap_room = max(0, SALARY_CAP - payroll) if tier == BELOW_CAP else 0
    limit = max_incoming_salary(tier, outgoing, cap_room)
    legal = incoming <= limit
    tier_label = _TIER_LABELS[tier]

    if legal:
        reason = f"{tier_label.capitalize()} — incoming salary (${incoming:,}) is within the ${limit:,.0f} matching limit."
    elif tier == OVER_SECOND_APRON:
        reason = (
            f"Over the second apron — hard restriction: cannot take back more salary "
            f"(${incoming:,}) than sent out (${outgoing:,}), no matching cushion allowed."
        )
    else:
        reason = f"{tier_label.capitalize()} — incoming salary (${incoming:,}) exceeds the ${limit:,.0f} matching limit."

    return {"tier": tier, "legal": legal, "outgoing": outgoing, "incoming": incoming,
             "limit": round(limit), "reason": reason}


def unknown_legality(reason: str = "Insufficient salary data to evaluate cap legality") -> dict:
    return {"tier": "unknown", "legal": None, "outgoing": None, "incoming": None, "limit": None, "reason": reason}


def fairness_verdict(overall_out: list[int], overall_in: list[int], threshold: int = 5) -> dict:
    avg_sent = sum(overall_out) / len(overall_out) if overall_out else 0.0
    avg_received = sum(overall_in) / len(overall_in) if overall_in else 0.0
    diff = avg_received - avg_sent

    if diff > threshold:
        verdict = "favorable"
    elif diff < -threshold:
        verdict = "unfavorable"
    else:
        verdict = "fair"

    return {
        "avg_sent": round(avg_sent, 1),
        "avg_received": round(avg_received, 1),
        "diff": round(diff, 1),
        "verdict": verdict,
    }
