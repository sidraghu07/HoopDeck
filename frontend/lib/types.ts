export type Tier = "Franchise Player" | "All-Star" | "Starter" | "Rotation" | "Bench";
export type League = "NBA" | "WNBA";

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
  league: League;
  team: string;
  age: number;
  positions: string[];
  primary_position: string;
  tier: Tier;
  has_photo: boolean;
  availability: {
    games_played: number;
    scheduled_games: number | null;
    availability_pct: number | null;
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

export interface PlayoffPlayerSeason {
  player_id: number;
  player_name: string;
  season: string;
  league: League;
  team: string;
  age: number;
  positions: string[];
  primary_position: string;
  playoff_badge: string | null;
  games_played: number;
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
  hottest_zone: string | null;
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
  league: League;
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
  league: League;
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
  out_of_position_penalty: number;
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
  league: League;
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
  league: League;
  team: string;
  primary_position: string;
  tier: Tier;
  [stat: string]: string | number | Tier;
}

export interface TeamStatRow {
  team: string;
  season: string;
  league: League;
  team_name: string;
  [stat: string]: string | number;
}

export interface TeamListItem {
  team: string;
  team_name: string;
  league: League;
}

export interface TeamRosterEntry {
  player_id: number;
  player_name: string;
  team: string;
  jersey_num: string | null;
  how_acquired: string | null;
  roster_season: string;
  season: string | null;
  primary_position: string | null;
  tier: Tier | null;
  rating_overall: number | null;
  is_fallback_season: boolean;
}

export interface DraftPick {
  id: number;
  draft_year: number;
  round: number;
  original_team: string;
  current_owner: string;
  protection_note: string | null;
  trade_note: string | null;
  is_swap: boolean;
  source_url: string | null;
}

export interface TradeProposal {
  league: League;
  team_a: string;
  team_b: string;
  players_from_a: number[];
  players_from_b: number[];
  picks_from_a?: number[];
  picks_from_b?: number[];
  season?: string;
}

export interface TradeSideEntry {
  player_id: number;
  player_name: string;
  season: string;
  team: string;
  primary_position: string;
  tier: Tier;
  rating_overall: number;
  assumed_minutes: number;
}

export interface TradeSideResult {
  predicted_net_rating: number;
  predicted_win_pct: number;
  predicted_record: string;
  roster_features: LineupRosterFeatures;
  roster: TradeSideEntry[];
}

export interface TradeFairness {
  avg_sent: number;
  avg_received: number;
  diff: number;
  verdict: "favorable" | "fair" | "unfavorable";
}

export interface TradeLegality {
  tier: "below_cap" | "under_first_apron" | "under_second_apron" | "over_second_apron" | "unknown";
  legal: boolean | null;
  outgoing: number | null;
  incoming: number | null;
  limit: number | null;
  reason: string;
  fairness: TradeFairness;
}

export interface TradeVerdict {
  cba_legal: boolean | null;
  team_a: TradeLegality;
  team_b: TradeLegality;
}

export interface TradeResult {
  league: League;
  verdict: TradeVerdict;
  team_a: { team: string; before: TradeSideResult; after: TradeSideResult };
  team_b: { team: string; before: TradeSideResult; after: TradeSideResult };
  picks_exchanged: { from_a: DraftPick[]; from_b: DraftPick[] };
}
