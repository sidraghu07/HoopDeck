export type Tier = "Franchise Player" | "All-Star" | "Starter" | "Rotation" | "Bench";

export interface ShotZone {
  attempts: number;
  makes: number;
  misses: number;
  fg_pct: number | null;
  freq_pct: number;
  is_3pt: boolean;
  volume_rating: number;
  efficiency_rating: number;
  hot_score: number;
  is_hot_zone: boolean;
  insufficient_sample: boolean;
}

export interface PlayerSeason {
  player_id: number;
  player_name: string;
  season: string;
  team: string;
  age: number;
  positions: string[];
  primary_position: string;
  tier: Tier;
  has_photo: boolean;
  availability: {
    games_played: number;
    scheduled_games: number;
    availability_pct: number;
    roster_status: string | null;
  };
  ratings: {
    overall: number;
    scoring: number;
    playmaking: number;
    defense: number;
    impact: number;
  };
  ratings_by_position?: Record<string, Record<string, number>>;
  per_game: {
    pts: number;
    reb: number;
    ast: number;
    stl: number;
    blk: number;
    tov: number;
    min: number;
    oreb: number;
    dreb: number;
  };
  scoring: {
    fg_pct: number;
    fg3_pct: number;
    ft_pct: number;
    efg_pct: number;
    ts_pct: number;
    fg3a_per_game: number;
    fga_per_game: number;
    pct_uast_fgm: number;
  };
  advanced: Record<string, number>;
  clutch: { clutch_plus_minus: number };
  shot_zones: Record<string, ShotZone>;
  hottest_zone: string;
  total_charted_fga: number;
}

export interface PlayersResponse {
  meta: Record<string, unknown>;
  players: PlayerSeason[];
}

export interface PlayerSeasonCard {
  player_id: number;
  player_name: string;
  season: string;
  team: string;
  primary_position: string;
  tier: Tier;
  has_photo: boolean;
  ratings: {
    overall: number;
    scoring: number;
    playmaking: number;
    defense: number;
    impact: number;
  };
  per_game: {
    pts: number;
    reb: number;
    ast: number;
    stl: number;
    blk: number;
    min: number;
  };
}

export interface CareerCard {
  player_id: number;
  player_name: string;
  career: CareerSummary;
}

export interface CareerSummary {
  bestTier: Tier;
  bestOverall: number;
  seasonsPlayed: number;
  teams: string[];
  primary_position: string;
  has_photo: boolean;
  per_game: {
    pts: number;
    reb: number;
    ast: number;
    stl: number;
    blk: number;
    min: number;
  };
  ratings: {
    overall: number;
    scoring: number;
    playmaking: number;
    defense: number;
    impact: number;
  };
}

export interface LineupPlayerInput {
  player_id: number;
  season: string;
  position?: string;
}

export interface LineupRosterEntry {
  player_id: number;
  player_name: string;
  season: string;
  team: string;
  primary_position: string;
  assigned_position: string | null;
  tier: Tier;
  rating_overall: number;
  assumed_minutes: number;
}

export interface LineupRosterFeatures {
  avg_scoring: number;
  avg_playmaking: number;
  avg_defense: number;
  avg_impact: number;
  avg_overall: number;
  star_power: number;
  bench_overall: number;
}

export interface LineupResult {
  predicted_net_rating: number;
  predicted_win_pct: number;
  predicted_record: string;
  roster_features: LineupRosterFeatures;
  roster: LineupRosterEntry[];
}

export interface PlayerStatRow {
  player_id: number;
  player_name: string;
  season: string;
  team: string;
  primary_position: string;
  tier: Tier;
  [stat: string]: string | number | Tier;
}

export interface TeamStatRow {
  team: string;
  season: string;
  team_name: string;
  [stat: string]: string | number;
}

export interface TeamListItem {
  team: string;
  team_name: string;
}
