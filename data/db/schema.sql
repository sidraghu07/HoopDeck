CREATE TABLE IF NOT EXISTS player_seasons (
    player_id           INTEGER NOT NULL,
    season              TEXT NOT NULL,
    league              TEXT NOT NULL DEFAULT 'NBA',
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
CREATE INDEX IF NOT EXISTS idx_player_seasons_league_season    ON player_seasons (league, season);

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

CREATE TABLE IF NOT EXISTS player_playoff_seasons (
    player_id           INTEGER NOT NULL,
    season              TEXT NOT NULL,
    league              TEXT NOT NULL DEFAULT 'NBA',
    player_name         TEXT NOT NULL,
    team                TEXT NOT NULL,
    age                 INTEGER,
    positions           TEXT[] NOT NULL,
    primary_position    TEXT NOT NULL,

    games_played        INTEGER NOT NULL,

    rating_overall      INTEGER NOT NULL,
    rating_scoring      INTEGER NOT NULL,
    rating_playmaking   INTEGER NOT NULL,
    rating_defense      INTEGER NOT NULL,
    rating_impact       INTEGER NOT NULL,
    playoff_badge        TEXT,

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
    total_charted_fga  INTEGER NOT NULL DEFAULT 0,

    PRIMARY KEY (player_id, season)
);

ALTER TABLE player_playoff_seasons ADD COLUMN IF NOT EXISTS hottest_zone TEXT;
ALTER TABLE player_playoff_seasons ADD COLUMN IF NOT EXISTS total_charted_fga INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_player_playoff_seasons_season    ON player_playoff_seasons (season);
CREATE INDEX IF NOT EXISTS idx_player_playoff_seasons_player_id ON player_playoff_seasons (player_id);

CREATE TABLE IF NOT EXISTS playoff_shot_zones (
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
    FOREIGN KEY (player_id, season) REFERENCES player_playoff_seasons (player_id, season) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS player_photos (
    player_id  INTEGER PRIMARY KEY,
    has_photo  BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS team_seasons (
    team          TEXT NOT NULL,
    season        TEXT NOT NULL,
    league        TEXT NOT NULL DEFAULT 'NBA',
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

CREATE INDEX IF NOT EXISTS idx_team_seasons_league_season ON team_seasons (league, season);

CREATE TABLE IF NOT EXISTS season_state (
    league       TEXT PRIMARY KEY,
    season       TEXT NOT NULL,
    phase        TEXT NOT NULL,
    fingerprint  INTEGER,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS team_rosters (
    player_id     INTEGER NOT NULL,
    league        TEXT NOT NULL,
    team          TEXT NOT NULL,
    season        TEXT NOT NULL,
    player_name   TEXT NOT NULL,
    jersey_num    TEXT,
    how_acquired  TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (league, player_id)
);

CREATE INDEX IF NOT EXISTS idx_team_rosters_team_season ON team_rosters (league, team, season);

CREATE TABLE IF NOT EXISTS draft_picks (
    id                SERIAL PRIMARY KEY,
    league            TEXT NOT NULL,
    draft_year        INTEGER NOT NULL,
    round             INTEGER NOT NULL,
    original_team     TEXT NOT NULL,
    current_owner     TEXT NOT NULL,
    protection_note   TEXT,
    trade_note        TEXT,
    is_swap           BOOLEAN NOT NULL DEFAULT false,
    source_url        TEXT,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (league, draft_year, round, original_team, is_swap)
);

CREATE INDEX IF NOT EXISTS idx_draft_picks_owner ON draft_picks (league, current_owner);
CREATE INDEX IF NOT EXISTS idx_draft_picks_year  ON draft_picks (league, draft_year);

CREATE TABLE IF NOT EXISTS player_salaries (
    player_id     INTEGER NOT NULL,
    league        TEXT NOT NULL,
    season        TEXT NOT NULL,
    team          TEXT NOT NULL,
    salary        BIGINT NOT NULL,
    source        TEXT NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (league, player_id, season)
);

CREATE INDEX IF NOT EXISTS idx_player_salaries_team ON player_salaries (league, team, season);
