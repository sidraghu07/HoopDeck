import unicodedata

import pandas as pd
import numpy as np

MIN_GP = 10
MIN_GP_BY_LEAGUE = {"NBA": 10, "WNBA": 5}
MIN_MPG = 5.0

PLAYOFF_MIN_GP = 1


def normalize_name(name: str) -> str:
    name = str(name).strip()
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = name.replace(".", "").replace(",", "").replace("'", "")
    for suffix in [" jr", " sr", " iii", " ii", " iv"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return " ".join(name.split())


def parse_positions(pos_str):
    if pd.isna(pos_str) or not str(pos_str).strip():
        return ["Unknown"]
    return [p.strip() for p in str(pos_str).split("-") if p.strip()]


def safe(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        return round(float(val), 4)
    return val


def percentile_rating(series: pd.Series, value, low_is_good=False,
                       floor=40, ceiling=99) -> int:
    if pd.isna(value):
        return floor
    arr = series.dropna().values
    if len(arr) == 0:
        return floor
    idx = np.searchsorted(np.sort(arr), value, side="right")
    p = idx / len(arr)
    if low_is_good:
        p = 1.0 - p
    return int(round(floor + p * (ceiling - floor)))


RATING_COLS = {
    "ts_pct":           "TS_PCT",
    "efg_pct":          "EFG_PCT",
    "fg3_pct":          "FG3_PCT",
    "ft_pct":           "FT_PCT",
    "pts":              "PTS",
    "usg_pct":          "USG_PCT",
    "pct_uast_fgm":     "PCT_UAST_FGM",
    "ast_pct":          "AST_PCT",
    "ast_to":           "AST_TO",
    "tov_pct":          "E_TOV_PCT",
    "off_rating":       "OFF_RATING",
    "def_rating":       "DEF_RATING",
    "dreb_pct":         "DREB_PCT",
    "stl":              "STL",
    "blk":              "BLK",
    "net_rating":       "NET_RATING",
    "pie":              "PIE",
    "plus_minus":       "PLUS_MINUS",
    "w_pct":            "W_PCT",
    "clutch_pm":        "CLUTCH_PLUS_MINUS",
    "availability_pct": "AVAILABILITY_PCT",
}


def build_pool(df: pd.DataFrame) -> dict:
    return {
        k: df[col]
        for k, col in RATING_COLS.items()
        if col in df.columns
    }


def _pr(pool: dict, key: str, value, low_is_good=False) -> int:
    if key not in pool or pd.isna(value):
        return 40
    return percentile_rating(pool[key], value, low_is_good=low_is_good)


def safe_per36_pm(row) -> float:
    min_played = max(row.get("MIN", 1), 1)
    return (row["PLUS_MINUS"] / min_played) * 36


def compute_subscores(row, pool: dict, position_list: list | None = None) -> dict:
    primary_pos = position_list[0] if position_list else "Unknown"

    scoring = int(round(
        0.16 * _pr(pool, "ts_pct",       row["TS_PCT"])       +
        0.09 * _pr(pool, "efg_pct",      row["EFG_PCT"])      +
        0.07 * _pr(pool, "fg3_pct",      row["FG3_PCT"])      +
        0.44 * _pr(pool, "pts",          row["PTS"])           +
        0.14 * _pr(pool, "usg_pct",      row["USG_PCT"])      +
        0.10 * _pr(pool, "pct_uast_fgm", row.get("PCT_UAST_FGM", np.nan))
    ))

    if primary_pos in ("SG", "SF"):
        play_weights = (0.45, 0.12, 0.18, 0.25)
    else:
        play_weights = (0.45, 0.22, 0.18, 0.15)

    playmaking = int(round(
        play_weights[0] * _pr(pool, "ast_pct",    row["AST_PCT"])                     +
        play_weights[1] * _pr(pool, "ast_to",     row["AST_TO"])                      +
        play_weights[2] * _pr(pool, "tov_pct",    row["E_TOV_PCT"], low_is_good=True) +
        play_weights[3] * _pr(pool, "off_rating", row["OFF_RATING"])
    ))

    defense = int(round(
        0.40 * _pr(pool, "def_rating", row["DEF_RATING"], low_is_good=True)       +
        0.25 * _pr(pool, "dreb_pct",   row["DREB_PCT"])                           +
        0.22 * _pr(pool, "stl",        row["STL"])                                 +
        0.13 * _pr(pool, "blk",        row["BLK"])
    ))

    plus_minus_adj = safe_per36_pm(row)
    impact = int(round(
        0.38 * _pr(pool, "pie",        row["PIE"])                                 +
        0.25 * _pr(pool, "usg_pct",    row["USG_PCT"])                             +
        0.17 * _pr(pool, "ts_pct",     row["TS_PCT"])                              +
        0.10 * _pr(pool, "net_rating", row["NET_RATING"])                          +
        0.06 * _pr(pool, "clutch_pm",  row.get("CLUTCH_PLUS_MINUS", np.nan))      +
        0.04 * _pr(pool, "plus_minus", plus_minus_adj)
    ))

    availability = _pr(pool, "availability_pct", row["AVAILABILITY_PCT"])

    return {
        "scoring": scoring,
        "playmaking": playmaking,
        "defense": defense,
        "impact": impact,
        "availability": availability,
    }
