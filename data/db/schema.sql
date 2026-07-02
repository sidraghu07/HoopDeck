CREATE TABLE IF NOT EXISTS player_seasons (
    player_id           INTEGER NOT NULL,
    season              TEXT NOT NULL,
    player_name         TEXT NOT NULL,
    team                TEXT NOT NULL,
    age                 INTEGER,
    positions           TEXT[] NOT NULL,
    primary_position    TEXT NOT NULL,
    tier                TEXT NOT NULL,

    games_played        INTEGER NOT NULL,
    scheduled_games     INTEGER,
    availability_pct    REAL,
    roster_status       TEXT,

    rating_overall      INTEGER NOT NULL,
    rating_scoring      INTEGER NOT NULL,
    rating_playmaking   INTEGER NOT NULL,
    rating_defense      INTEGER NOT NULL,
    rating_impact       INTEGER NOT NULL,

    pg_pts   REAL NOT NULL,
    pg_reb   REAL NOT NULL,
    pg_ast   REAL NOT NULL,
    pg_stl   REAL NOT NULL,
    pg_blk   REAL NOT NULL,
    pg_tov   REAL NOT NULL,
    pg_min   REAL NOT NULL,
    pg_oreb  REAL NOT NULL,
    pg_dreb  REAL NOT NULL,

    fg_pct         REAL,
    fg3_pct        REAL,
    ft_pct         REAL,
    efg_pct        REAL,
    ts_pct         REAL,
    fg3a_per_game  REAL,
    fga_per_game   REAL,
    pct_uast_fgm   REAL,

    off_rating   REAL,
    def_rating   REAL,
    net_rating   REAL,
    ast_pct      REAL,
    ast_to       REAL,
    usg_pct      REAL,
    oreb_pct     REAL,
    dreb_pct     REAL,
    pie          REAL,
    pace         REAL,
    plus_minus   REAL,
    e_tov_pct    REAL,

    clutch_plus_minus  REAL,
    hottest_zone       TEXT,
    total_charted_fga  INTEGER NOT NULL,

    PRIMARY KEY (player_id, season)
);

CREATE INDEX IF NOT EXISTS idx_player_seasons_season           ON player_seasons (season);
CREATE INDEX IF NOT EXISTS idx_player_seasons_tier             ON player_seasons (tier);
CREATE INDEX IF NOT EXISTS idx_player_seasons_primary_position ON player_seasons (primary_position);
CREATE INDEX IF NOT EXISTS idx_player_seasons_player_id        ON player_seasons (player_id);

CREATE TABLE IF NOT EXISTS shot_zones (
    player_id            INTEGER NOT NULL,
    season                TEXT NOT NULL,
    zone_slug             TEXT NOT NULL,
    attempts              INTEGER NOT NULL,
    makes                 INTEGER NOT NULL,
    misses                INTEGER NOT NULL,
    fg_pct                REAL,
    freq_pct              REAL NOT NULL,
    is_3pt                BOOLEAN NOT NULL,
    volume_rating         INTEGER NOT NULL,
    efficiency_rating     INTEGER NOT NULL,
    hot_score             INTEGER NOT NULL,
    is_hot_zone           BOOLEAN NOT NULL,
    insufficient_sample   BOOLEAN NOT NULL,

    PRIMARY KEY (player_id, season, zone_slug),
    FOREIGN KEY (player_id, season) REFERENCES player_seasons (player_id, season) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ratings_by_position (
    player_id    INTEGER NOT NULL,
    season       TEXT NOT NULL,
    position     TEXT NOT NULL,
    scoring      INTEGER NOT NULL,
    playmaking   INTEGER NOT NULL,
    defense      INTEGER NOT NULL,
    impact       INTEGER NOT NULL,
    overall      INTEGER NOT NULL,

    PRIMARY KEY (player_id, season, position),
    FOREIGN KEY (player_id, season) REFERENCES player_seasons (player_id, season) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_seasons (
    team          TEXT NOT NULL,
    season        TEXT NOT NULL,
    team_name     TEXT NOT NULL,
    games_played  INTEGER NOT NULL,
    wins          INTEGER NOT NULL,
    losses        INTEGER NOT NULL,
    win_pct       REAL NOT NULL,
    off_rating    REAL NOT NULL,
    def_rating    REAL NOT NULL,
    net_rating    REAL NOT NULL,
    pace          REAL NOT NULL,

    PRIMARY KEY (team, season)
);
