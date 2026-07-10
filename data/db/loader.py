import psycopg

from rating_lib import normalize_name


def player_id_lookup(database_url: str, league: str) -> dict[str, int]:
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT player_id, player_name FROM player_seasons WHERE league = %(league)s",
                {"league": league},
            )
            rows = cur.fetchall()
    return {normalize_name(player_name): player_id for player_id, player_name in rows}


def load_player_photos(rows: list[tuple[int, bool]], database_url: str) -> None:
    print("\nLoading player_photos into Postgres…")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE player_photos")
            with cur.copy("COPY player_photos (player_id, has_photo) FROM STDIN") as copy:
                for player_id, has_photo in rows:
                    copy.write_row((player_id, has_photo))
        conn.commit()
    print(f"  ✓ Loaded {len(rows):,} player photo flags into Postgres")


def load_team_rosters(rosters_df, database_url: str) -> None:
    print("\nLoading team_rosters into Postgres…")
    leagues = rosters_df["LEAGUE"].unique().tolist() if "LEAGUE" in rosters_df.columns else ["NBA"]
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM team_rosters WHERE league = ANY(%(leagues)s)", {"leagues": leagues})
            with cur.copy(
                "COPY team_rosters (player_id, league, team, season, player_name, "
                "jersey_num, how_acquired) FROM STDIN"
            ) as copy:
                for row in rosters_df.itertuples(index=False):
                    league = getattr(row, "LEAGUE", "NBA")
                    copy.write_row((
                        int(row.PLAYER_ID), league, row.TEAM_ABBREVIATION, row.SEASON,
                        row.PLAYER_NAME, str(row.NUM) if row.NUM else None, row.HOW_ACQUIRED,
                    ))
        conn.commit()
    print(f"  ✓ Loaded {len(rosters_df):,} roster rows into Postgres")


def load_player_salaries(salaries_df, database_url: str) -> None:
    print("\nLoading player_salaries into Postgres…")
    leagues = salaries_df["LEAGUE"].unique().tolist() if "LEAGUE" in salaries_df.columns else ["NBA"]
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM player_salaries WHERE league = ANY(%(leagues)s)", {"leagues": leagues})
            with cur.copy(
                "COPY player_salaries (player_id, league, season, team, salary, source) FROM STDIN"
            ) as copy:
                for row in salaries_df.itertuples(index=False):
                    league = getattr(row, "LEAGUE", "NBA")
                    copy.write_row((
                        int(row.PLAYER_ID), league, row.SEASON, row.TEAM,
                        int(row.SALARY), row.SOURCE,
                    ))
        conn.commit()
    print(f"  ✓ Loaded {len(salaries_df):,} salary rows into Postgres")


def load_team_seasons(teams_df, database_url: str) -> None:
    print("\nLoading team_seasons into Postgres…")
    leagues = teams_df["LEAGUE"].unique().tolist() if "LEAGUE" in teams_df.columns else ["NBA"]
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM team_seasons WHERE league = ANY(%(leagues)s)", {"leagues": leagues})
            with cur.copy(
                "COPY team_seasons (team, season, league, team_name, games_played, wins, losses, "
                "win_pct, off_rating, def_rating, net_rating, pace) FROM STDIN"
            ) as copy:
                for row in teams_df.itertuples(index=False):
                    league = getattr(row, "LEAGUE", "NBA")
                    copy.write_row((
                        row.TEAM_ABBREVIATION, row.SEASON, league, row.TEAM_NAME, int(row.GP),
                        int(row.W), int(row.L), row.W_PCT,
                        row.OFF_RATING, row.DEF_RATING, row.NET_RATING, row.PACE,
                    ))
        conn.commit()
    print(f"  ✓ Loaded {len(teams_df):,} team-seasons into Postgres")


def load_to_postgres(cards: list, database_url: str) -> None:
    print("\nLoading into Postgres…")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE shot_zones, ratings_by_position, player_seasons")

            with cur.copy(
                "COPY player_seasons ("
                "player_id, season, league, player_name, team, age, positions, primary_position, tier, "
                "games_played, scheduled_games, availability_pct, roster_status, "
                "rating_overall, rating_scoring, rating_playmaking, rating_defense, rating_impact, "
                "pg_pts, pg_reb, pg_ast, pg_stl, pg_blk, pg_tov, pg_min, pg_oreb, pg_dreb, "
                "fg_pct, fg3_pct, ft_pct, efg_pct, ts_pct, fg3a_per_game, fga_per_game, pct_uast_fgm, "
                "off_rating, def_rating, net_rating, ast_pct, ast_to, usg_pct, oreb_pct, dreb_pct, "
                "pie, pace, plus_minus, e_tov_pct, clutch_plus_minus, hottest_zone, total_charted_fga"
                ") FROM STDIN"
            ) as copy:
                to_int = lambda v: None if v is None else int(v)
                for c in cards:
                    avail, rt, pg, sc, adv = (
                        c["availability"], c["ratings"], c["per_game"], c["scoring"], c["advanced"],
                    )
                    copy.write_row((
                        c["player_id"], c["season"], c.get("league", "NBA"), c["player_name"], c["team"], to_int(c["age"]),
                        c["positions"], c["primary_position"], c["tier"],
                        avail["games_played"], to_int(avail["scheduled_games"]),
                        avail["availability_pct"], avail["roster_status"],
                        rt["overall"], rt["scoring"], rt["playmaking"], rt["defense"], rt["impact"],
                        pg["pts"], pg["reb"], pg["ast"], pg["stl"], pg["blk"],
                        pg["tov"], pg["min"], pg["oreb"], pg["dreb"],
                        sc["fg_pct"], sc["fg3_pct"], sc["ft_pct"], sc["efg_pct"], sc["ts_pct"],
                        sc["fg3a_per_game"], sc["fga_per_game"], sc["pct_uast_fgm"],
                        adv["off_rating"], adv["def_rating"], adv["net_rating"],
                        adv["ast_pct"], adv["ast_to"], adv["usg_pct"],
                        adv["oreb_pct"], adv["dreb_pct"], adv["pie"], adv["pace"],
                        adv["plus_minus"], adv["e_tov_pct"],
                        c["clutch"]["clutch_plus_minus"], c["hottest_zone"], c["total_charted_fga"],
                    ))

            with cur.copy(
                "COPY shot_zones (player_id, season, zone_slug, attempts, makes, misses, fg_pct, "
                "freq_pct, is_3pt, volume_rating, efficiency_rating, hot_score, is_hot_zone, "
                "insufficient_sample) FROM STDIN"
            ) as copy:
                for c in cards:
                    for slug, z in c["shot_zones"].items():
                        copy.write_row((
                            c["player_id"], c["season"], slug,
                            z["attempts"], z["makes"], z["misses"], z["fg_pct"], z["freq_pct"],
                            z["is_3pt"], z["volume_rating"], z["efficiency_rating"], z["hot_score"],
                            z["is_hot_zone"], z["insufficient_sample"],
                        ))

            with cur.copy(
                "COPY ratings_by_position (player_id, season, position, scoring, playmaking, "
                "defense, impact, overall) FROM STDIN"
            ) as copy:
                for c in cards:
                    for pos, r in c["ratings_by_position"].items():
                        copy.write_row((
                            c["player_id"], c["season"], pos,
                            r["scoring"], r["playmaking"], r["defense"], r["impact"], r["overall"],
                        ))
        conn.commit()
    print(f"  ✓ Loaded {len(cards):,} player-seasons into Postgres")


def load_playoff_seasons_to_postgres(cards: list, database_url: str) -> None:
    print("\nLoading playoff cards into Postgres…")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE playoff_shot_zones, player_playoff_seasons")
            with cur.copy(
                "COPY player_playoff_seasons ("
                "player_id, season, league, player_name, team, age, positions, primary_position, "
                "games_played, "
                "rating_overall, rating_scoring, rating_playmaking, rating_defense, rating_impact, "
                "playoff_badge, "
                "pg_pts, pg_reb, pg_ast, pg_stl, pg_blk, pg_tov, pg_min, pg_oreb, pg_dreb, "
                "fg_pct, fg3_pct, ft_pct, efg_pct, ts_pct, fg3a_per_game, fga_per_game, pct_uast_fgm, "
                "off_rating, def_rating, net_rating, ast_pct, ast_to, usg_pct, oreb_pct, dreb_pct, "
                "pie, pace, plus_minus, e_tov_pct, clutch_plus_minus, hottest_zone, total_charted_fga"
                ") FROM STDIN"
            ) as copy:
                to_int = lambda v: None if v is None else int(v)
                for c in cards:
                    rt, pg, sc, adv = c["ratings"], c["per_game"], c["scoring"], c["advanced"]
                    copy.write_row((
                        c["player_id"], c["season"], c.get("league", "NBA"), c["player_name"], c["team"],
                        to_int(c["age"]), c["positions"], c["primary_position"],
                        c["games_played"],
                        rt["overall"], rt["scoring"], rt["playmaking"], rt["defense"], rt["impact"],
                        c["playoff_badge"],
                        pg["pts"], pg["reb"], pg["ast"], pg["stl"], pg["blk"],
                        pg["tov"], pg["min"], pg["oreb"], pg["dreb"],
                        sc["fg_pct"], sc["fg3_pct"], sc["ft_pct"], sc["efg_pct"], sc["ts_pct"],
                        sc["fg3a_per_game"], sc["fga_per_game"], sc["pct_uast_fgm"],
                        adv["off_rating"], adv["def_rating"], adv["net_rating"],
                        adv["ast_pct"], adv["ast_to"], adv["usg_pct"],
                        adv["oreb_pct"], adv["dreb_pct"], adv["pie"], adv["pace"],
                        adv["plus_minus"], adv["e_tov_pct"],
                        c["clutch"]["clutch_plus_minus"], c["hottest_zone"], c["total_charted_fga"],
                    ))

            with cur.copy(
                "COPY playoff_shot_zones (player_id, season, zone_slug, attempts, makes, misses, fg_pct, "
                "freq_pct, is_3pt, volume_rating, efficiency_rating, hot_score, is_hot_zone, "
                "insufficient_sample) FROM STDIN"
            ) as copy:
                for c in cards:
                    for slug, z in c["shot_zones"].items():
                        copy.write_row((
                            c["player_id"], c["season"], slug,
                            z["attempts"], z["makes"], z["misses"], z["fg_pct"], z["freq_pct"],
                            z["is_3pt"], z["volume_rating"], z["efficiency_rating"], z["hot_score"],
                            z["is_hot_zone"], z["insufficient_sample"],
                        ))
        conn.commit()
    print(f"  ✓ Loaded {len(cards):,} playoff player-seasons into Postgres")
