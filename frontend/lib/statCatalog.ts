export interface StatDef {
  key: string;
  label: string;
}

export interface StatGroup {
  group: string;
  stats: StatDef[];
}

export const PLAYER_STAT_GROUPS: StatGroup[] = [
  {
    group: "RATINGS",
    stats: [
      { key: "rating_overall", label: "Overall" },
      { key: "rating_scoring", label: "Scoring" },
      { key: "rating_playmaking", label: "Playmaking" },
      { key: "rating_defense", label: "Defense" },
      { key: "rating_impact", label: "Impact" },
    ],
  },
  {
    group: "PER GAME",
    stats: [
      { key: "pg_pts", label: "Points" },
      { key: "pg_reb", label: "Rebounds" },
      { key: "pg_ast", label: "Assists" },
      { key: "pg_stl", label: "Steals" },
      { key: "pg_blk", label: "Blocks" },
      { key: "pg_tov", label: "Turnovers" },
      { key: "pg_min", label: "Minutes" },
      { key: "pg_oreb", label: "Off. Rebounds" },
      { key: "pg_dreb", label: "Def. Rebounds" },
    ],
  },
  {
    group: "SHOOTING",
    stats: [
      { key: "fg_pct", label: "FG%" },
      { key: "fg3_pct", label: "3P%" },
      { key: "ft_pct", label: "FT%" },
      { key: "efg_pct", label: "eFG%" },
      { key: "ts_pct", label: "TS%" },
      { key: "fg3a_per_game", label: "3PA per Game" },
      { key: "fga_per_game", label: "FGA per Game" },
      { key: "pct_uast_fgm", label: "% Unassisted FGM" },
    ],
  },
  {
    group: "ADVANCED",
    stats: [
      { key: "off_rating", label: "Off. Rating" },
      { key: "def_rating", label: "Def. Rating" },
      { key: "net_rating", label: "Net Rating" },
      { key: "ast_pct", label: "Assist %" },
      { key: "ast_to", label: "Assist/TO" },
      { key: "usg_pct", label: "Usage %" },
      { key: "oreb_pct", label: "Off. Reb %" },
      { key: "dreb_pct", label: "Def. Reb %" },
      { key: "pie", label: "PIE" },
      { key: "pace", label: "Pace" },
      { key: "plus_minus", label: "Plus/Minus" },
      { key: "e_tov_pct", label: "Turnover %" },
    ],
  },
  {
    group: "CLUTCH",
    stats: [{ key: "clutch_plus_minus", label: "Clutch +/-" }],
  },
];

export const TEAM_STAT_GROUPS: StatGroup[] = [
  {
    group: "RECORD",
    stats: [
      { key: "wins", label: "Wins" },
      { key: "losses", label: "Losses" },
      { key: "win_pct", label: "Win %" },
      { key: "games_played", label: "Games Played" },
    ],
  },
  {
    group: "RATINGS",
    stats: [
      { key: "off_rating", label: "Off. Rating" },
      { key: "def_rating", label: "Def. Rating" },
      { key: "net_rating", label: "Net Rating" },
      { key: "pace", label: "Pace" },
    ],
  },
];

export function findStatDef(groups: StatGroup[], key: string): StatDef | undefined {
  for (const g of groups) {
    const found = g.stats.find((s) => s.key === key);
    if (found) return found;
  }
  return undefined;
}
