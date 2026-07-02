import psycopg


def load_team_seasons(teams_df, database_url: str) -> None:
    print("\nLoading team_seasons into Postgres…")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE team_seasons")
            with cur.copy(
                "COPY team_seasons (team, season, team_name, games_played, wins, losses, "
                "win_pct, off_rating, def_rating, net_rating, pace) FROM STDIN"
            ) as copy:
                for row in teams_df.itertuples(index=False):
                    copy.write_row((
                        row.TEAM_ABBREVIATION, row.SEASON, row.TEAM_NAME, int(row.GP),
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
                "player_id, season, player_name, team, age, positions, primary_position, tier, "
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
                        c["player_id"], c["season"], c["player_name"], c["team"], to_int(c["age"]),
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
