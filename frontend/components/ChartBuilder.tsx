"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  ComposedChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import {
  getPlayers,
  getPlayer,
  getPlayerStatsBySeason,
  getPlayerStatsBySeasons,
  getTeamStatsBySeason,
  getTeamStatsBySeasons,
  getTeamStats,
  getTeamList,
} from "@/lib/api";
import { CareerCard, PlayerSeason, PlayerSeasonCard, PlayerStatRow, TeamStatRow, TeamListItem } from "@/lib/types";
import { PLAYER_STAT_GROUPS, TEAM_STAT_GROUPS, StatGroup, findStatDef } from "@/lib/statCatalog";
import PlayerCard from "./PlayerCard";
import styles from "./ChartBuilder.module.css";

type EntityType = "players" | "teams";
type Mode = "trend" | "ranking" | "correlation";
type StatRow = PlayerStatRow | TeamStatRow;

const COLORS = ["#e8b339", "#a99bc4", "#6b9bd1", "#d16b9b", "#6bd1a0", "#d19b6b"];
const MAX_TREND_ENTITIES = COLORS.length;

function nbaSeasonList(): string[] {
  const seasons: string[] = [];
  for (let y = 2025; y >= 1996; y--) {
    seasons.push(`${y}-${String((y + 1) % 100).padStart(2, "0")}`);
  }
  return seasons;
}

function wnbaSeasonList(): string[] {
  const seasons: string[] = [];
  for (let y = 2025; y >= 1997; y--) {
    seasons.push(String(y));
  }
  return seasons;
}

const SEASONS_BY_LEAGUE: Record<string, string[]> = {
  NBA: nbaSeasonList(),
  WNBA: wnbaSeasonList(),
};

function seasonsInRange(seasons: string[], from: string, to: string): string[] {
  const i1 = seasons.indexOf(from);
  const i2 = seasons.indexOf(to);
  if (i1 === -1 || i2 === -1) return [from];
  const [lo, hi] = i1 < i2 ? [i1, i2] : [i2, i1];
  return seasons.slice(lo, hi + 1);
}

const QUADRANT_COLORS = {
  topRight: "#6bd1a0",
  topLeft: "#a99bc4",
  bottomRight: "#d19b6b",
  bottomLeft: "#d16b6b",
};

function quadrantColor(x: number, y: number, meanX: number, meanY: number): string {
  if (x >= meanX && y >= meanY) return QUADRANT_COLORS.topRight;
  if (x < meanX && y >= meanY) return QUADRANT_COLORS.topLeft;
  if (x >= meanX && y < meanY) return QUADRANT_COLORS.bottomRight;
  return QUADRANT_COLORS.bottomLeft;
}

function extractPlayerSeasonStat(season: PlayerSeason, key: string): number | null {
  const map: Record<string, number | undefined> = {
    rating_overall: season.ratings.overall,
    rating_scoring: season.ratings.scoring,
    rating_playmaking: season.ratings.playmaking,
    rating_defense: season.ratings.defense,
    rating_impact: season.ratings.impact,
    pg_pts: season.per_game.pts,
    pg_reb: season.per_game.reb,
    pg_ast: season.per_game.ast,
    pg_stl: season.per_game.stl,
    pg_blk: season.per_game.blk,
    pg_tov: season.per_game.tov,
    pg_min: season.per_game.min,
    pg_oreb: season.per_game.oreb,
    pg_dreb: season.per_game.dreb,
    fg_pct: season.scoring.fg_pct,
    fg3_pct: season.scoring.fg3_pct,
    ft_pct: season.scoring.ft_pct,
    efg_pct: season.scoring.efg_pct,
    ts_pct: season.scoring.ts_pct,
    fg3a_per_game: season.scoring.fg3a_per_game,
    fga_per_game: season.scoring.fga_per_game,
    pct_uast_fgm: season.scoring.pct_uast_fgm,
    off_rating: season.advanced.off_rating,
    def_rating: season.advanced.def_rating,
    net_rating: season.advanced.net_rating,
    ast_pct: season.advanced.ast_pct,
    ast_to: season.advanced.ast_to,
    usg_pct: season.advanced.usg_pct,
    oreb_pct: season.advanced.oreb_pct,
    dreb_pct: season.advanced.dreb_pct,
    pie: season.advanced.pie,
    pace: season.advanced.pace,
    plus_minus: season.advanced.plus_minus,
    e_tov_pct: season.advanced.e_tov_pct,
    clutch_plus_minus: season.clutch.clutch_plus_minus,
  };
  return map[key] ?? null;
}

function formatNum(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}

function paddedDomain(values: number[]): [number, number] | undefined {
  if (values.length === 0) return undefined;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.08 || Math.abs(max) * 0.1 || 1;
  return [min - pad, max + pad];
}

function linearRegression(points: { x: number; y: number }[]): { slope: number; intercept: number; r2: number } | null {
  const n = points.length;
  if (n < 2) return null;

  const sumX = points.reduce((s, p) => s + p.x, 0);
  const sumY = points.reduce((s, p) => s + p.y, 0);
  const sumXY = points.reduce((s, p) => s + p.x * p.y, 0);
  const sumXX = points.reduce((s, p) => s + p.x * p.x, 0);
  const denom = n * sumXX - sumX * sumX;
  if (denom === 0) return null;

  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;

  const meanY = sumY / n;
  let ssRes = 0;
  let ssTot = 0;
  points.forEach((p) => {
    const predicted = slope * p.x + intercept;
    ssRes += (p.y - predicted) ** 2;
    ssTot += (p.y - meanY) ** 2;
  });
  const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot;

  return { slope, intercept, r2 };
}

interface ScatterDotProps {
  cx?: number;
  cy?: number;
  payload?: { x: number; y: number; name: string; season: string; row: StatRow };
}

interface TrendDotProps {
  cx?: number;
  cy?: number;
  payload?: Record<string, string | number>;
}

function flatRowToSeasonCard(row: PlayerStatRow): PlayerSeasonCard {
  return {
    player_id: row.player_id,
    player_name: row.player_name,
    season: row.season,
    league: row.league,
    team: row.team,
    primary_position: row.primary_position,
    tier: row.tier,
    has_photo: true,
    ratings: {
      overall: row.rating_overall as number,
      scoring: row.rating_scoring as number,
      playmaking: row.rating_playmaking as number,
      defense: row.rating_defense as number,
      impact: row.rating_impact as number,
    },
    per_game: {
      pts: row.pg_pts as number,
      reb: row.pg_reb as number,
      ast: row.pg_ast as number,
      stl: row.pg_stl as number,
      blk: row.pg_blk as number,
      min: row.pg_min as number,
    },
  };
}

interface TrendEntity {
  id: string;
  label: string;
  kind: "player" | "team";
  playerHistory?: PlayerSeason[];
  teamHistory?: TeamStatRow[];
}

export default function ChartBuilder() {
  const [league, setLeague] = useState<"NBA" | "WNBA">("NBA");
  const [entityType, setEntityType] = useState<EntityType>("players");
  const [mode, setMode] = useState<Mode>("trend");

  const seasons = SEASONS_BY_LEAGUE[league];
  const statGroups: StatGroup[] = entityType === "players" ? PLAYER_STAT_GROUPS : TEAM_STAT_GROUPS;
  const defaultStatKey = statGroups[0].stats[0].key;
  const defaultSecondStatKey = statGroups[0].stats[1]?.key ?? defaultStatKey;

  const [trendQuery, setTrendQuery] = useState("");
  const [trendSearchResults, setTrendSearchResults] = useState<CareerCard[]>([]);
  const [teamList, setTeamList] = useState<TeamListItem[]>([]);
  const [trendEntities, setTrendEntities] = useState<TrendEntity[]>([]);
  const [trendStat, setTrendStat] = useState(defaultStatKey);
  const [trendLoading, setTrendLoading] = useState(false);

  const [rankingSeason, setRankingSeason] = useState(seasons[0]);
  const [rankingStat, setRankingStat] = useState(defaultStatKey);
  const [rankingTopN, setRankingTopN] = useState(10);
  const [rankingDirection, setRankingDirection] = useState<"desc" | "asc">("desc");
  const [rankingRows, setRankingRows] = useState<StatRow[]>([]);
  const [rankingLoading, setRankingLoading] = useState(false);

  const [corrSeasonFrom, setCorrSeasonFrom] = useState(seasons[0]);
  const [corrSeasonTo, setCorrSeasonTo] = useState(seasons[0]);
  const [corrXStat, setCorrXStat] = useState(defaultStatKey);
  const [corrYStat, setCorrYStat] = useState(defaultSecondStatKey);
  const [corrRows, setCorrRows] = useState<StatRow[]>([]);
  const [corrLoading, setCorrLoading] = useState(false);
  const [showQuadrants, setShowQuadrants] = useState(false);
  const [showTrendLine, setShowTrendLine] = useState(true);
  const [corrHighlightQuery, setCorrHighlightQuery] = useState("");
  const [trendHighlightQuery, setTrendHighlightQuery] = useState("");
  const [previewCard, setPreviewCard] = useState<{ data: PlayerSeasonCard; x: number; y: number } | null>(null);

  const router = useRouter();

  const corrSeasonRange = useMemo(
    () => seasonsInRange(seasons, corrSeasonFrom, corrSeasonTo),
    [seasons, corrSeasonFrom, corrSeasonTo]
  );

  const [resetForEntityType, setResetForEntityType] = useState(entityType);
  const [resetForLeague, setResetForLeague] = useState(league);
  if (entityType !== resetForEntityType || league !== resetForLeague) {
    setResetForEntityType(entityType);
    setResetForLeague(league);
    setTrendEntities([]);
    setTrendQuery("");
    setTrendSearchResults([]);
    setTeamList([]);
    setTrendStat(statGroups[0].stats[0].key);
    setRankingStat(statGroups[0].stats[0].key);
    setRankingSeason(seasons[0]);
    setCorrSeasonFrom(seasons[0]);
    setCorrSeasonTo(seasons[0]);
    setCorrXStat(statGroups[0].stats[0].key);
    setCorrYStat(statGroups[0].stats[1]?.key ?? statGroups[0].stats[0].key);
    setRankingRows([]);
    setCorrRows([]);
    setCorrHighlightQuery("");
    setTrendHighlightQuery("");
    setPreviewCard(null);
  }

  useEffect(() => {
    if (entityType === "teams" && mode === "trend" && teamList.length === 0) {
      getTeamList(league)
        .then(setTeamList)
        .catch(() => setTeamList([]));
    }
  }, [entityType, mode, teamList.length, league]);

  useEffect(() => {
    if (entityType !== "players" || mode !== "trend") return;
    if (trendQuery.trim().length < 2) {
      return;
    }
    let cancelled = false;
    const timeout = setTimeout(() => {
      getPlayers({ season: "ALL", league, name: trendQuery, page: 1 })
        .then((data) => {
          if (!cancelled) setTrendSearchResults(data?.players ?? []);
        })
        .catch(() => {
          if (!cancelled) setTrendSearchResults([]);
        });
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [trendQuery, entityType, mode, league]);

  useEffect(() => {
    if (mode !== "ranking") return;
    setRankingLoading(true);
    const fetcher =
      entityType === "players"
        ? getPlayerStatsBySeason(rankingSeason, league)
        : getTeamStatsBySeason(rankingSeason, league);
    fetcher
      .then((rows) => setRankingRows(rows ?? []))
      .catch(() => setRankingRows([]))
      .finally(() => setRankingLoading(false));
  }, [mode, entityType, rankingSeason, league]);

  useEffect(() => {
    if (mode !== "correlation") return;
    setCorrLoading(true);
    const fetcher =
      entityType === "players"
        ? getPlayerStatsBySeasons(corrSeasonRange, league)
        : getTeamStatsBySeasons(corrSeasonRange, league);
    fetcher
      .then((rows) => setCorrRows(rows ?? []))
      .catch(() => setCorrRows([]))
      .finally(() => setCorrLoading(false));
  }, [mode, entityType, corrSeasonRange, league]);

  function addPlayerTrendEntity(c: CareerCard) {
    if (trendEntities.length >= MAX_TREND_ENTITIES) return;
    if (trendEntities.some((e) => e.id === String(c.player_id))) return;
    setTrendLoading(true);
    getPlayer(c.player_id)
      .then((seasons: PlayerSeason[]) => {
        setTrendEntities((prev) => [
          ...prev,
          { id: String(c.player_id), label: c.player_name, kind: "player", playerHistory: seasons },
        ]);
        setTrendQuery("");
        setTrendSearchResults([]);
      })
      .finally(() => setTrendLoading(false));
  }

  function addTeamTrendEntity(item: TeamListItem) {
    if (trendEntities.length >= MAX_TREND_ENTITIES) return;
    if (trendEntities.some((e) => e.id === item.team)) return;
    setTrendLoading(true);
    getTeamStats([item.team], league)
      .then((rows: TeamStatRow[]) => {
        setTrendEntities((prev) => [
          ...prev,
          { id: item.team, label: item.team_name, kind: "team", teamHistory: rows },
        ]);
      })
      .finally(() => setTrendLoading(false));
  }

  function removeTrendEntity(id: string) {
    setTrendEntities((prev) => prev.filter((e) => e.id !== id));
  }

  const trendChartData = useMemo(() => {
    const seasonSet = new Set<string>();
    const perEntity = new Map<string, Map<string, number>>();

    trendEntities.forEach((e) => {
      const m = new Map<string, number>();
      if (e.kind === "player" && e.playerHistory) {
        e.playerHistory.forEach((s) => {
          const v = extractPlayerSeasonStat(s, trendStat);
          if (v !== null) {
            m.set(s.season, v);
            seasonSet.add(s.season);
          }
        });
      } else if (e.kind === "team" && e.teamHistory) {
        e.teamHistory.forEach((row) => {
          const v = row[trendStat];
          if (typeof v === "number") {
            m.set(row.season, v);
            seasonSet.add(row.season);
          }
        });
      }
      perEntity.set(e.id, m);
    });

    const seasons = Array.from(seasonSet).sort();
    return seasons.map((season) => {
      const row: Record<string, string | number> = { season };
      trendEntities.forEach((e) => {
        const v = perEntity.get(e.id)?.get(season);
        if (v !== undefined) row[e.label] = v;
      });
      return row;
    });
  }, [trendEntities, trendStat]);

  const visibleTrendResults = trendQuery.trim().length < 2 ? [] : trendSearchResults;

  const trendYDomain = useMemo(() => {
    const values: number[] = [];
    trendChartData.forEach((row) => {
      trendEntities.forEach((e) => {
        const v = row[e.label];
        if (typeof v === "number") values.push(v);
      });
    });
    return paddedDomain(values);
  }, [trendChartData, trendEntities]);

  const rankingChartData = useMemo(() => {
    const rows = rankingRows.filter((r) => typeof r[rankingStat] === "number");
    rows.sort((a, b) => {
      const av = a[rankingStat] as number;
      const bv = b[rankingStat] as number;
      return rankingDirection === "desc" ? bv - av : av - bv;
    });
    return rows.slice(0, rankingTopN).map((r) => ({
      name: entityType === "players" ? (r as PlayerStatRow).player_name : (r as TeamStatRow).team_name,
      value: r[rankingStat] as number,
    }));
  }, [rankingRows, rankingStat, rankingDirection, rankingTopN, entityType]);

  const corrChartData = useMemo(() => {
    return corrRows
      .filter((r) => typeof r[corrXStat] === "number" && typeof r[corrYStat] === "number")
      .map((r) => ({
        name: entityType === "players" ? (r as PlayerStatRow).player_name : (r as TeamStatRow).team_name,
        season: r.season,
        x: r[corrXStat] as number,
        y: r[corrYStat] as number,
        row: r,
      }));
  }, [corrRows, corrXStat, corrYStat, entityType]);

  const corrRegression = useMemo(() => linearRegression(corrChartData), [corrChartData]);

  const corrMeans = useMemo(() => {
    if (corrChartData.length === 0) return null;
    const meanX = corrChartData.reduce((s, p) => s + p.x, 0) / corrChartData.length;
    const meanY = corrChartData.reduce((s, p) => s + p.y, 0) / corrChartData.length;
    return { meanX, meanY };
  }, [corrChartData]);

  const corrTrendLine = useMemo(() => {
    if (!corrRegression || corrChartData.length === 0) return [];
    const xs = corrChartData.map((p) => p.x);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    return [
      { x: minX, y: corrRegression.slope * minX + corrRegression.intercept },
      { x: maxX, y: corrRegression.slope * maxX + corrRegression.intercept },
    ];
  }, [corrRegression, corrChartData]);

  const corrXDomain = useMemo(
    () => paddedDomain(corrChartData.map((p) => p.x)),
    [corrChartData]
  );
  const corrYDomain = useMemo(
    () => paddedDomain(corrChartData.map((p) => p.y)),
    [corrChartData]
  );

  const trendStatLabel = findStatDef(statGroups, trendStat)?.label ?? trendStat;
  const rankingStatLabel = findStatDef(statGroups, rankingStat)?.label ?? rankingStat;
  const corrXLabel = findStatDef(statGroups, corrXStat)?.label ?? corrXStat;
  const corrYLabel = findStatDef(statGroups, corrYStat)?.label ?? corrYStat;

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        <ToggleGroup
          value={league}
          options={[
            { value: "NBA", label: "NBA" },
            { value: "WNBA", label: "WNBA" },
          ]}
          onChange={(v) => setLeague(v as "NBA" | "WNBA")}
        />
        <ToggleGroup
          value={entityType}
          options={[
            { value: "players", label: "PLAYERS" },
            { value: "teams", label: "TEAMS" },
          ]}
          onChange={(v) => setEntityType(v as EntityType)}
        />
        <ToggleGroup
          value={mode}
          options={[
            { value: "trend", label: "TREND" },
            { value: "ranking", label: "RANKING" },
            { value: "correlation", label: "CORRELATION" },
          ]}
          onChange={(v) => {
            setMode(v as Mode);
            setPreviewCard(null);
          }}
        />
      </div>

      {mode === "trend" && (
        <div className={styles.controls}>
          <div className={styles.controlsRow}>
            <StatSelect label="STAT" value={trendStat} onChange={setTrendStat} groups={statGroups} />
            {entityType === "players" && (
              <input
                className={styles.highlightInput}
                value={trendHighlightQuery}
                onChange={(e) => setTrendHighlightQuery(e.target.value)}
                placeholder="HIGHLIGHT A PLAYER..."
                spellCheck={false}
                autoComplete="off"
              />
            )}
            {trendLoading && <span className={styles.hint}>LOADING...</span>}
          </div>

          <div className={styles.entityChips}>
            {trendEntities.map((e, i) => (
              <div key={e.id} className={styles.chip} style={{ borderColor: COLORS[i % COLORS.length] }}>
                <span className={styles.chipDot} style={{ background: COLORS[i % COLORS.length] }} />
                <span>{e.label}</span>
                <button
                  type="button"
                  className={styles.chipRemove}
                  onClick={() => removeTrendEntity(e.id)}
                  aria-label={`Remove ${e.label}`}
                >
                  ✕
                </button>
              </div>
            ))}
            {trendEntities.length >= MAX_TREND_ENTITIES && (
              <span className={styles.hint}>MAX {MAX_TREND_ENTITIES} REACHED</span>
            )}
          </div>

          {entityType === "players" ? (
            <>
              <input
                className={styles.input}
                value={trendQuery}
                onChange={(e) => setTrendQuery(e.target.value)}
                placeholder="SEARCH A PLAYER TO ADD..."
                spellCheck={false}
                autoComplete="off"
              />
              {visibleTrendResults.length > 0 && (
                <div className={styles.resultsList}>
                  {visibleTrendResults.map((c) => (
                    <button
                      key={c.player_id}
                      type="button"
                      className={styles.resultRow}
                      onClick={() => addPlayerTrendEntity(c)}
                    >
                      <span>{c.player_name}</span>
                      <span className={styles.resultMeta}>{c.career.primary_position}</span>
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : (
            <select
              className={styles.select}
              value=""
              onChange={(e) => {
                const item = teamList.find((t) => t.team === e.target.value);
                if (item) addTeamTrendEntity(item);
              }}
            >
              <option value="">ADD A TEAM...</option>
              {teamList.map((t) => (
                <option key={t.team} value={t.team}>
                  {t.team_name} ({t.team})
                </option>
              ))}
            </select>
          )}

          <div className={styles.chartBox}>
            {trendChartData.length === 0 ? (
              <div className={styles.emptyChart}>ADD ONE OR MORE {entityType.toUpperCase()} TO SEE A TREND</div>
            ) : (
              <ResponsiveContainer width="100%" height={440}>
                <LineChart data={trendChartData}>
                  <CartesianGrid stroke="var(--border-muted)" strokeDasharray="3 3" />
                  <XAxis dataKey="season" tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
                  <YAxis
                    domain={trendYDomain ?? ["auto", "auto"]}
                    tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                    label={{
                      value: trendStatLabel,
                      angle: -90,
                      position: "insideLeft",
                      fill: "var(--text-muted)",
                    }}
                  />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "var(--text-primary)" }} />
                  <Legend wrapperStyle={{ fontSize: 13, color: "var(--text-primary)" }} />
                  {trendEntities.map((e, i) => {
                    const query = trendHighlightQuery.trim().toLowerCase();
                    const isHighlighted =
                      entityType === "players" && query.length > 0 && e.label.toLowerCase().includes(query);
                    const isDimmed = entityType === "players" && query.length > 0 && !isHighlighted;
                    return (
                      <Line
                        key={e.id}
                        type="monotone"
                        dataKey={e.label}
                        stroke={COLORS[i % COLORS.length]}
                        strokeWidth={isHighlighted ? 4 : 2}
                        strokeOpacity={isDimmed ? 0.25 : 1}
                        isAnimationActive={false}
                        dot={(dotProps: TrendDotProps) => {
                          const { cx, cy, payload } = dotProps;
                          if (cx === undefined || cy === undefined || !payload) {
                            return <circle r={0} />;
                          }
                          const isClickable = entityType === "players" && e.kind === "player";
                          return (
                            <circle
                              key={`${e.id}-${payload.season}`}
                              cx={cx}
                              cy={cy}
                              r={isHighlighted ? 5 : 3}
                              fill={COLORS[i % COLORS.length]}
                              opacity={isDimmed ? 0.25 : 1}
                              style={{ cursor: isClickable ? "pointer" : "default" }}
                              onClick={
                                isClickable
                                  ? () => {
                                      const season = e.playerHistory?.find((s) => s.season === payload.season);
                                      if (season) setPreviewCard({ data: season, x: cx, y: cy });
                                    }
                                  : undefined
                              }
                              onDoubleClick={isClickable ? () => setPreviewCard(null) : undefined}
                            />
                          );
                        }}
                        connectNulls
                      />
                    );
                  })}
                </LineChart>
              </ResponsiveContainer>
            )}
            {previewCard && (
              <PlayerPreviewPopup
                card={previewCard}
                onClose={() => setPreviewCard(null)}
                onNavigate={() =>
                  router.push(`/players/${previewCard.data.player_id}?season=${previewCard.data.season}`)
                }
              />
            )}
          </div>
        </div>
      )}

      {mode === "ranking" && (
        <div className={styles.controls}>
          <div className={styles.controlsRow}>
            <SeasonSelect value={rankingSeason} onChange={setRankingSeason} seasons={seasons} />
            <StatSelect label="STAT" value={rankingStat} onChange={setRankingStat} groups={statGroups} />
            <label className={styles.selectWrap}>
              <span className={styles.selectLabel}>TOP</span>
              <input
                type="number"
                min={1}
                max={30}
                value={rankingTopN}
                onChange={(e) => setRankingTopN(Math.max(1, Math.min(30, Number(e.target.value) || 1)))}
                className={styles.numberInput}
              />
            </label>
            <ToggleGroup
              value={rankingDirection}
              options={[
                { value: "desc", label: "HIGH → LOW" },
                { value: "asc", label: "LOW → HIGH" },
              ]}
              onChange={(v) => setRankingDirection(v as "desc" | "asc")}
            />
            {rankingLoading && <span className={styles.hint}>LOADING...</span>}
          </div>

          <div className={styles.chartBox}>
            {rankingChartData.length === 0 ? (
              <div className={styles.emptyChart}>NO DATA FOR THIS SELECTION</div>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(300, rankingChartData.length * 36)}>
                <BarChart data={rankingChartData} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid stroke="var(--border-muted)" strokeDasharray="3 3" />
                  <XAxis type="number" tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={140}
                    tick={{ fill: "var(--text-primary)", fontSize: 12 }}
                  />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "var(--text-primary)" }} />
                  <Bar dataKey="value" name={rankingStatLabel} fill="var(--accent)" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}

      {mode === "correlation" && (
        <div className={styles.controls}>
          <div className={styles.controlsRow}>
            <SeasonSelect label="FROM" value={corrSeasonFrom} onChange={setCorrSeasonFrom} seasons={seasons} />
            <SeasonSelect label="TO" value={corrSeasonTo} onChange={setCorrSeasonTo} seasons={seasons} />
            <StatSelect label="X AXIS" value={corrXStat} onChange={setCorrXStat} groups={statGroups} />
            <StatSelect label="Y AXIS" value={corrYStat} onChange={setCorrYStat} groups={statGroups} />
            {entityType === "players" && (
              <input
                className={styles.highlightInput}
                value={corrHighlightQuery}
                onChange={(e) => setCorrHighlightQuery(e.target.value)}
                placeholder="HIGHLIGHT A PLAYER..."
                spellCheck={false}
                autoComplete="off"
              />
            )}
            <button
              type="button"
              className={`${styles.toggleBtn} ${styles.standaloneToggle} ${showTrendLine ? styles.toggleBtnActive : ""}`}
              onClick={() => setShowTrendLine((v) => !v)}
            >
              TREND LINE
            </button>
            <button
              type="button"
              className={`${styles.toggleBtn} ${styles.standaloneToggle} ${showQuadrants ? styles.toggleBtnActive : ""}`}
              onClick={() => setShowQuadrants((v) => !v)}
            >
              QUADRANTS
            </button>
            {corrLoading && <span className={styles.hint}>LOADING...</span>}
            {corrRegression && <span className={styles.hint}>R² = {corrRegression.r2.toFixed(3)}</span>}
          </div>

          <div className={styles.chartBox}>
            {corrChartData.length === 0 ? (
              <div className={styles.emptyChart}>NO DATA FOR THIS SELECTION</div>
            ) : (
              <ResponsiveContainer width="100%" height={440}>
                <ComposedChart>
                  <CartesianGrid stroke="var(--border-muted)" strokeDasharray="3 3" />
                  <XAxis
                    type="number"
                    dataKey="x"
                    name={corrXLabel}
                    domain={corrXDomain ?? ["auto", "auto"]}
                    tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                    label={{ value: corrXLabel, position: "insideBottom", offset: -5, fill: "var(--text-muted)" }}
                  />
                  <YAxis
                    type="number"
                    dataKey="y"
                    name={corrYLabel}
                    domain={corrYDomain ?? ["auto", "auto"]}
                    tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                    label={{ value: corrYLabel, angle: -90, position: "insideLeft", fill: "var(--text-muted)" }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const entry = payload.find((p) => p.payload && "name" in (p.payload as object));
                      if (!entry) return null;
                      const p = entry.payload as { name: string; season: string; x: number; y: number };
                      return (
                        <div style={tooltipStyle}>
                          <div>
                            {p.name}
                            {corrSeasonRange.length > 1 ? ` (${p.season})` : ""}
                          </div>
                          <div>
                            {corrXLabel}: {formatNum(p.x)}
                          </div>
                          <div>
                            {corrYLabel}: {formatNum(p.y)}
                          </div>
                        </div>
                      );
                    }}
                  />
                  {showQuadrants && corrMeans && (
                    <>
                      <ReferenceLine
                        x={corrMeans.meanX}
                        stroke="var(--border-strong)"
                        strokeDasharray="4 4"
                        label={{ value: "MEAN", fill: "var(--text-muted)", fontSize: 11, position: "top" }}
                      />
                      <ReferenceLine
                        y={corrMeans.meanY}
                        stroke="var(--border-strong)"
                        strokeDasharray="4 4"
                        label={{ value: "MEAN", fill: "var(--text-muted)", fontSize: 11, position: "right" }}
                      />
                    </>
                  )}
                  <Scatter
                    data={corrChartData}
                    dataKey="y"
                    isAnimationActive={false}
                    shape={(props: ScatterDotProps) => {
                      const { cx, cy, payload } = props;
                      if (cx === undefined || cy === undefined || !payload) return <circle r={0} />;
                      const isPlayers = entityType === "players";
                      const query = corrHighlightQuery.trim().toLowerCase();
                      const isHighlighted = isPlayers && query.length > 0 && payload.name.toLowerCase().includes(query);
                      const isDimmed = isPlayers && query.length > 0 && !isHighlighted;
                      const fill =
                        showQuadrants && corrMeans
                          ? quadrantColor(payload.x, payload.y, corrMeans.meanX, corrMeans.meanY)
                          : "var(--accent)";
                      return (
                        <circle
                          cx={cx}
                          cy={cy}
                          r={isHighlighted ? 7 : 4}
                          fill={isHighlighted ? "var(--accent-bright)" : fill}
                          opacity={isDimmed ? 0.25 : 1}
                          stroke={isHighlighted ? "var(--text-primary)" : "none"}
                          strokeWidth={isHighlighted ? 2 : 0}
                          style={{ cursor: isPlayers ? "pointer" : "default" }}
                          onClick={
                            isPlayers
                              ? () =>
                                  setPreviewCard({
                                    data: flatRowToSeasonCard(payload.row as PlayerStatRow),
                                    x: cx,
                                    y: cy,
                                  })
                              : undefined
                          }
                          onDoubleClick={isPlayers ? () => setPreviewCard(null) : undefined}
                        />
                      );
                    }}
                  />
                  {showTrendLine && (
                    <Line
                      data={corrTrendLine}
                      dataKey="y"
                      stroke="var(--text-primary)"
                      strokeWidth={2}
                      strokeDasharray="6 4"
                      dot={false}
                      activeDot={false}
                      legendType="none"
                      isAnimationActive={false}
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            )}
            {previewCard && (
              <PlayerPreviewPopup
                card={previewCard}
                onClose={() => setPreviewCard(null)}
                onNavigate={() =>
                  router.push(`/players/${previewCard.data.player_id}?season=${previewCard.data.season}`)
                }
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const tooltipStyle: React.CSSProperties = {
  background: "var(--bg-surface)",
  border: "1px solid var(--border-muted)",
  color: "var(--text-primary)",
  fontFamily: "VT323, monospace",
  fontSize: 15,
  padding: 8,
};

function PlayerPreviewPopup({
  card,
  onClose,
  onNavigate,
}: {
  card: { data: PlayerSeasonCard; x: number; y: number };
  onClose: () => void;
  onNavigate: () => void;
}) {
  return (
    <div className={styles.previewPopup} style={{ left: card.x + 12, top: card.y - 178 }}>
      <button type="button" className={styles.previewClose} onClick={onClose} aria-label="Close preview">
        ✕
      </button>
      <div className={styles.previewCardWrap} onClick={onNavigate}>
        <PlayerCard mode="season" data={card.data} scale={0.55} />
      </div>
    </div>
  );
}

function ToggleGroup({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <div className={styles.toggleGroup}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className={`${styles.toggleBtn} ${value === o.value ? styles.toggleBtnActive : ""}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function StatSelect({
  label,
  value,
  onChange,
  groups,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  groups: StatGroup[];
}) {
  return (
    <label className={styles.selectWrap}>
      <span className={styles.selectLabel}>{label}</span>
      <select className={styles.select} value={value} onChange={(e) => onChange(e.target.value)}>
        {groups.map((g) => (
          <optgroup key={g.group} label={g.group}>
            {g.stats.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}

function SeasonSelect({
  label = "SEASON",
  value,
  onChange,
  seasons,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  seasons: string[];
}) {
  return (
    <label className={styles.selectWrap}>
      <span className={styles.selectLabel}>{label}</span>
      <select className={styles.select} value={value} onChange={(e) => onChange(e.target.value)}>
        {seasons.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </label>
  );
}
