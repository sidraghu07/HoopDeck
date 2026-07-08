"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { PlayerSeason, PlayoffPlayerSeason, ShotZone } from "@/lib/types";
import { TIER_STYLE } from "@/lib/tiers";
import styles from "./PlayerDetail.module.css";

const PANELS = ["STATS", "SHOOTING", "ADVANCED", "SHOT ZONES", "AVAILABILITY"] as const;
type PanelName = (typeof PANELS)[number];

interface Props {
  seasons: PlayerSeason[];
  active: PlayerSeason;
  playoffsBySeason: Record<string, PlayoffPlayerSeason>;
}

// Playoffs data is a reduced surface (no shot zones/availability/tier) — this
// adapts it into the same PlayerSeason shape so the header/ribbon/panels
// below can render it with zero special-casing. The SHOT ZONES panel already
// degrades gracefully on an empty zones map; the AVAILABILITY panel already
// falls back to "—" on nulls.
function toDisplaySeason(regular: PlayerSeason, playoff: PlayoffPlayerSeason): PlayerSeason {
  return {
    ...regular,
    team: playoff.team,
    age: playoff.age,
    positions: playoff.positions,
    primary_position: playoff.primary_position,
    ratings: playoff.ratings,
    per_game: playoff.per_game,
    scoring: playoff.scoring,
    advanced: playoff.advanced,
    clutch: playoff.clutch,
    ratings_by_position: {},
    shot_zones: {},
    hottest_zone: "",
    availability: {
      games_played: playoff.games_played,
      scheduled_games: regular.availability.scheduled_games,
      availability_pct: regular.availability.availability_pct,
      roster_status: "Playoffs",
    },
  };
}

export default function PlayerDetail({ seasons, active, playoffsBySeason }: Props) {
  const [panelIdx, setPanelIdx] = useState(0);
  const [imgFailed, setImgFailed] = useState(false);
  const searchParams = useSearchParams();

  const playoffData = playoffsBySeason[active.season];
  const showPlayoffs = searchParams.get("view") === "playoffs" && !!playoffData;
  const displayed = showPlayoffs ? toDisplaySeason(active, playoffData) : active;

  // The Players page's full search state (league/season/name/tier/position/
  // sort/dir/page), carried here by whatever link sent us to this page, so
  // BACK restores that exact view instead of resetting filters. Also carried
  // through the season-tab/playoffs-toggle links below so it survives
  // further navigation within this page.
  const fromQuery = searchParams.get("from");
  const backHref = fromQuery ? `/players?${fromQuery}` : `/players?season=${active.season}`;
  const fromSuffix = fromQuery ? `&from=${encodeURIComponent(fromQuery)}` : "";

  const style = TIER_STYLE[active.tier] ?? TIER_STYLE["Bench"];
  const imgUrl =
    active.league === "WNBA"
      ? `https://cdn.wnba.com/headshots/wnba/latest/1040x760/${active.player_id}.png`
      : `https://cdn.nba.com/headshots/nba/latest/1040x760/${active.player_id}.png`;

  function prev() { setPanelIdx((i) => (i - 1 + PANELS.length) % PANELS.length); }
  function next() { setPanelIdx((i) => (i + 1) % PANELS.length); }

  return (
    <div
      className={styles.page}
      style={{ "--tier-border": style.border, "--tier-glow": style.glow, "--tier-bg": style.bg } as React.CSSProperties}
    >
      <div className={styles.topNav}>
        <Link href={backHref} className={styles.back}>
          ← BACK
        </Link>
        <div className={styles.seasonTabs}>
          {seasons.map((s) => (
            <a
              key={s.season}
              href={`/players/${active.player_id}?season=${s.season}${fromSuffix}`}
              className={`${styles.seasonTab} ${s.season === active.season && !showPlayoffs ? styles.activeTab : ""}`}
            >
              {s.season}
            </a>
          ))}
        </div>
      </div>

      {playoffData && (
        <div className={styles.seasonTabs}>
          <a
            href={`/players/${active.player_id}?season=${active.season}${fromSuffix}`}
            className={`${styles.seasonTab} ${!showPlayoffs ? styles.activeTab : ""}`}
          >
            REGULAR SEASON
          </a>
          <a
            href={`/players/${active.player_id}?season=${active.season}&view=playoffs${fromSuffix}`}
            className={`${styles.seasonTab} ${showPlayoffs ? styles.activeTab : ""}`}
          >
            PLAYOFFS
          </a>
        </div>
      )}

      <div className={styles.card}>

        <div className={styles.cardHeader}>
          <span className={styles.tierBadge}>
            {showPlayoffs ? (playoffData?.playoff_badge ?? "PLAYOFFS") : style.label}
          </span>
          <span className={styles.cardSeason}>{active.season}</span>
        </div>

        <div className={styles.portrait}>
          {active.has_photo && !imgFailed ? (
            <Image
              src={imgUrl}
              alt={active.player_name}
              fill
              sizes="440px"
              className={styles.playerImg}
              onError={() => setImgFailed(true)}
              unoptimized
            />
          ) : (
            <span className={styles.initials}>
              {active.player_name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
            </span>
          )}
          <div className={styles.ovrBadge}>
            <span className={styles.ovrNum}>{displayed.ratings.overall}</span>
            <span className={styles.ovrLbl}>OVR</span>
          </div>
        </div>

        <div className={styles.namePlate}>
          <div className={styles.playerName}>{active.player_name}</div>
          <div className={styles.playerSub}>{displayed.primary_position} · {displayed.team}</div>
        </div>

        <div className={styles.slideshow}>
          <button className={styles.arrow} onClick={prev} aria-label="Previous panel">◄</button>

          <div className={styles.panel}>
            <div className={styles.panelTitle}>{PANELS[panelIdx]}</div>
            <PanelContent name={PANELS[panelIdx]} player={displayed} />
          </div>

          <button className={styles.arrow} onClick={next} aria-label="Next panel">►</button>
        </div>

        <div className={styles.dots}>
          {PANELS.map((_, i) => (
            <button
              key={i}
              className={`${styles.dot} ${i === panelIdx ? styles.activeDot : ""}`}
              onClick={() => setPanelIdx(i)}
              aria-label={PANELS[i]}
            />
          ))}
        </div>

        <div className={styles.ribbon}>
          <RibbonBit label="SCR" value={displayed.ratings.scoring} />
          <RibbonBit label="PLY" value={displayed.ratings.playmaking} />
          <RibbonBit label="DEF" value={displayed.ratings.defense} />
          <RibbonBit label="IMP" value={displayed.ratings.impact} />
        </div>
      </div>
    </div>
  );
}

function PanelContent({ name, player }: { name: PanelName; player: PlayerSeason }) {
  const pg  = player.per_game;
  const sc  = player.scoring;
  const adv = player.advanced ?? {};
  const av  = player.availability;
  const zones = player.shot_zones ?? {};

  switch (name) {
    case "STATS":
      return (
        <div className={styles.statGrid}>
          <StatCell label="PTS" value={pg.pts} />
          <StatCell label="REB" value={pg.reb} />
          <StatCell label="AST" value={pg.ast} />
          <StatCell label="STL" value={pg.stl} />
          <StatCell label="BLK" value={pg.blk} />
          <StatCell label="TOV" value={pg.tov} />
          <StatCell label="MIN" value={pg.min} />
          <StatCell label="OREB" value={pg.oreb} />
        </div>
      );

    case "SHOOTING":
      return (
        <div className={styles.statList}>
          <StatRow label="FG%"   value={fmtPct(sc?.fg_pct)} />
          <StatRow label="3P%"   value={fmtPct(sc?.fg3_pct)} />
          <StatRow label="FT%"   value={fmtPct(sc?.ft_pct)} />
          <StatRow label="eFG%"  value={fmtPct(sc?.efg_pct)} />
          <StatRow label="TS%"   value={fmtPct(sc?.ts_pct)} />
          <StatRow label="FGA/G" value={fmtNum(sc?.fga_per_game)} />
          <StatRow label="3PA/G" value={fmtNum(sc?.fg3a_per_game)} />
          <StatRow label="UAST%" value={fmtPct(sc?.pct_uast_fgm)} />
        </div>
      );

    case "ADVANCED": {
      const keys = ["off_rating","def_rating","net_rating","pie","usg_pct","ast_pct","ast_to","oreb_pct","dreb_pct","pace","e_tov_pct"];
      return (
        <div className={styles.statList}>
          {keys.map((k) => adv[k] != null && (
            <StatRow key={k} label={k.replace(/_/g," ").toUpperCase()} value={fmtNum(adv[k])} />
          ))}
          {player.clutch?.clutch_plus_minus != null && (
            <StatRow label="CLUTCH +/-" value={fmtNum(player.clutch.clutch_plus_minus)} />
          )}
        </div>
      );
    }

    case "SHOT ZONES":
      return <MiniCourtChart zones={zones} hottestZone={player.hottest_zone ?? ""} />;

    case "AVAILABILITY":
      return (
        <div className={styles.statList}>
          <StatRow label="GAMES PLAYED" value={av?.games_played ?? "—"} />
          <StatRow label="SCHEDULED"    value={av?.scheduled_games ?? "—"} />
          <StatRow label="AVAIL%"       value={fmtPct(av?.availability_pct)} />
          <StatRow label="STATUS"       value={av?.roster_status ?? "ACTIVE"} />
        </div>
      );
  }
}

const ZONE_MAP = [
  { key: "restricted",      label: "RA",    cx: 170, cy: 30  },
  { key: "paint",           label: "PAINT", cx: 170, cy: 75  },
  { key: "mid",             label: "MID",   cx: 170, cy: 140 },
  { key: "left corner 3",   label: "LC3",   cx: 14,  cy: 58  },
  { key: "right corner 3",  label: "RC3",   cx: 326, cy: 58  },
  { key: "left wing 3",     label: "LW3",   cx: 55,  cy: 150 },
  { key: "right wing 3",    label: "RW3",   cx: 285, cy: 150 },
  { key: "above the break", label: "ATB",   cx: 170, cy: 205 },
  { key: "left",            label: "LMR",   cx: 95,  cy: 115 },
  { key: "right",           label: "RMR",   cx: 245, cy: 115 },
];

const ZONE_LEGEND = [
  { label: "HOT ZONE",        color: "#fbbf24" },
  { label: "HIGH VOL · EFF",  color: "#4ade80" },
  { label: "LOW VOL · EFF",   color: "#38bdf8" },
  { label: "HIGH VOL · INEFF", color: "#fb923c" },
  { label: "LOW VOL · INEFF", color: "#dc2626" },
  { label: "SMALL SAMPLE",    color: "#6b7280" },
] as const;

function zoneColor(zone: ShotZone, isHottest: boolean) {
  if (isHottest) return "#fbbf24";
  if (zone.insufficient_sample) return "#6b7280";
  const highVolume = (zone.volume_rating ?? 0) >= 50;
  const highEff = (zone.efficiency_rating ?? 0) >= 50;
  if (highVolume && highEff) return "#4ade80";
  if (!highVolume && highEff) return "#38bdf8";
  if (highVolume && !highEff) return "#fb923c";
  return "#dc2626";
}

function MiniCourtChart({ zones, hottestZone }: { zones: Record<string, ShotZone>; hottestZone: string }) {
  return (
    <div className={styles.courtWrap}>
      <svg viewBox="0 0 340 230" className={styles.courtSvg} xmlns="http://www.w3.org/2000/svg">
        <rect x="0" y="0" width="340" height="230" fill="var(--bg-inset)" />
        <rect x="132" y="0" width="76" height="120" fill="none" stroke="var(--border-muted)" strokeWidth="1.5" />
        <circle cx="170" cy="12" r="5" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" />
        <line x1="145" y1="0" x2="195" y2="0" stroke="var(--text-muted)" strokeWidth="1.5" />
        <path d="M 147 12 A 23 23 0 0 1 193 12" fill="none" stroke="var(--border-muted)" strokeWidth="1.5" />
        <path d="M 132 120 A 38 38 0 0 0 208 120" fill="none" stroke="var(--border-muted)" strokeWidth="1.5" />
        <path d="M 26 0 L 26 90 A 165 165 0 0 0 314 90 L 314 0" fill="none" stroke="var(--border-muted)" strokeWidth="1.5" />

        {Object.entries(zones).map(([name, zone]) => {
          if (!zone) return null;
          const lower = name.toLowerCase().replace(/_/g, " ");
          const coord = ZONE_MAP.find((z) => lower.includes(z.key));
          if (!coord) return null;
          const isHottest = name === hottestZone;
          const color = zoneColor(zone, isHottest);
          const r = Math.max(12, Math.min(22, 12 + (zone.freq_pct ?? 0) * 100));
          return (
            <g key={name}>
              <circle cx={coord.cx} cy={coord.cy} r={r} fill={color} opacity={0.22} />
              {isHottest && (
                <circle cx={coord.cx} cy={coord.cy} r={r + 3} fill="none" stroke={color} strokeWidth="1.5" opacity={0.7} strokeDasharray="4 2" />
              )}
              <text x={coord.cx} y={coord.cy - 3} textAnchor="middle" fontSize="9" fill={color} fontFamily="VT323, monospace">
                {zone.fg_pct != null ? (zone.fg_pct * 100).toFixed(0) + "%" : "—"}
              </text>
              <text x={coord.cx} y={coord.cy + 9} textAnchor="middle" fontSize="7" fill={color} opacity={0.7} fontFamily="VT323, monospace">
                {coord.label}
              </text>
            </g>
          );
        })}
      </svg>
      <div className={styles.zoneLegend}>
        {ZONE_LEGEND.map((l) => (
          <span key={l.label} className={styles.legendBit}>
            <span className={styles.legendDot} style={{ background: l.color }} />
            {l.label}
          </span>
        ))}
      </div>
      {hottestZone && (
        <div className={styles.hotZone}>🔥 {hottestZone.toUpperCase()}</div>
      )}
    </div>
  );
}

function StatCell({ label, value }: { label: string; value: number | string }) {
  return (
    <div className={styles.statCell}>
      <span className={styles.statCellValue}>{value}</span>
      <span className={styles.statCellLabel}>{label}</span>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={styles.statRow}>
      <span className={styles.statRowLabel}>{label}</span>
      <span className={styles.statRowValue}>{value ?? "—"}</span>
    </div>
  );
}

function RibbonBit({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.ribbonBit}>
      <span className={styles.ribbonLabel}>{label}</span>
      <span className={styles.ribbonValue}>{value}</span>
    </div>
  );
}

function fmtPct(v: number | undefined | null): string {
  if (v == null || isNaN(v)) return "—";
  return (v * 100).toFixed(1) + "%";
}

function fmtNum(v: number | undefined | null): string {
  if (v == null || isNaN(v)) return "—";
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}
