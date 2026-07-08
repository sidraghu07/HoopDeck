"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CareerCard, PlayerSeasonCard, Tier } from "@/lib/types";
import { TIER_STYLE } from "@/lib/tiers";
import SearchBar from "./SearchBar";
import PlayerCard from "./PlayerCard";
import styles from "./PlayersExplorer.module.css";

const ALL_TIERS: Tier[] = ["Franchise Player", "All-Star", "Starter", "Rotation", "Bench"];
const LEAGUES = ["NBA", "WNBA"];

const SORT_FIELDS = ["overall", "pts", "reb", "ast", "stl", "blk", "min"];
const SORT_LABELS: Record<string, string> = {
  overall: "OVR", pts: "PTS", reb: "REB", ast: "AST", stl: "STL", blk: "BLK", min: "MIN",
};
const SORT_DIRS = ["desc", "asc"];
const SORT_DIR_LABELS: Record<string, string> = { desc: "HIGH → LOW", asc: "LOW → HIGH" };

interface Props {
  seasonCards: PlayerSeasonCard[];
  careerCards: CareerCard[];
  cardCount: number;
  isAllSeasons: boolean;
  league: string;
  season: string;
  name: string;
  tier: string;
  position: string;
  seasons: string[];
  positions: string[];
  page: number;
  totalPages: number;
  sort: string;
  dir: string;
}

export default function PlayersExplorer({
  seasonCards,
  careerCards,
  cardCount,
  isAllSeasons,
  league,
  season,
  name,
  tier,
  position,
  seasons,
  positions,
  page,
  totalPages,
  sort,
  dir,
}: Props) {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 600px)");
    setIsMobile(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  function pageUrl(target: number) {
    const params = new URLSearchParams();
    params.set("league", league);
    params.set("season", season);
    if (name) params.set("name", name);
    if (tier) params.set("tier", tier);
    if (position) params.set("position", position);
    if (sort !== "overall") params.set("sort", sort);
    if (dir !== "desc") params.set("dir", dir);
    if (target > 1) params.set("page", String(target));
    return `/players?${params.toString()}`;
  }

  // Full current search state, carried through to the player detail page so
  // its BACK link can restore this exact view instead of resetting filters.
  function currentQuery(): string {
    const params = new URLSearchParams();
    params.set("league", league);
    params.set("season", season);
    if (name) params.set("name", name);
    if (tier) params.set("tier", tier);
    if (position) params.set("position", position);
    if (sort !== "overall") params.set("sort", sort);
    if (dir !== "desc") params.set("dir", dir);
    if (page > 1) params.set("page", String(page));
    return params.toString();
  }

  return (
    <>
      <div className={styles.page}>
        <form method="GET" action="/players" className={styles.controls}>
          <SearchBar defaultValue={name} />
          <div className={styles.filterRow}>
            <label className={styles.selectWrap}>
              <span className={styles.selectLabel}>LEAGUE</span>
              <select
                className={styles.select}
                name="league"
                defaultValue={league}
                onChange={(e) => {
                  // Season/position lists are league-scoped — drop every
                  // other filter and let the server pick a fresh default
                  // season for the newly selected league.
                  window.location.href = `/players?league=${e.target.value}`;
                }}
              >
                {LEAGUES.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </label>
            <FilterSelect label="SEASON"   name="season"   value={season}   options={seasons} emptyLabel={undefined} allLabel="ALL SEASONS" />
            <FilterSelect
              label="TIER"
              name="tier"
              value={tier}
              options={ALL_TIERS}
              emptyLabel="ALL TIERS"
              labelFor={(t) => TIER_STYLE[t as Tier]?.label ?? t}
            />
            <FilterSelect label="POS"      name="position" value={position} options={positions} emptyLabel="ALL POS" />
            <FilterSelect
              label="SORT"
              name="sort"
              value={sort}
              options={SORT_FIELDS}
              emptyLabel={undefined}
              labelFor={(s) => SORT_LABELS[s] ?? s}
            />
            <FilterSelect
              label="DIR"
              name="dir"
              value={dir}
              options={SORT_DIRS}
              emptyLabel={undefined}
              labelFor={(d) => SORT_DIR_LABELS[d] ?? d}
            />
          </div>
        </form>

        <div className={styles.count}>
          {cardCount} CARD{cardCount === 1 ? "" : "S"} FOUND
        </div>

        <div className={styles.grid}>
          {isAllSeasons
            ? careerCards.map((g) => (
                <div key={g.player_id} className={styles.cardWrap}>
                  <PlayerCard
                    mode="career"
                    data={g.career}
                    player_name={g.player_name}
                    player_id={g.player_id}
                    league={g.league}
                    onClick={() => { window.location.href = `/players/${g.player_id}?from=${encodeURIComponent(currentQuery())}`; }}
                    scale={isMobile ? 0.65 : undefined}
                  />
                </div>
              ))
            : seasonCards.map((p) => (
                <div key={`${p.player_id}-${p.season}`} className={styles.cardWrap}>
                  <PlayerCard
                    mode="season"
                    data={p}
                    onClick={() => { window.location.href = `/players/${p.player_id}?season=${p.season}&from=${encodeURIComponent(currentQuery())}`; }}
                    scale={isMobile ? 0.65 : undefined}
                  />
                </div>
              ))}
        </div>

        {cardCount === 0 && (
          <div className={styles.empty}>NO RESULTS. ADJUST YOUR SEARCH.</div>
        )}

        {isAllSeasons && totalPages > 1 && (
          <div className={styles.pagination}>
            <Link
              href={pageUrl(page - 1)}
              className={`${styles.pageBtn} ${page <= 1 ? styles.pageBtnDisabled : ""}`}
              aria-disabled={page <= 1}
            >
              ◄ PREV
            </Link>
            <span className={styles.pageInfo}>PAGE {page} / {totalPages}</span>
            <Link
              href={pageUrl(page + 1)}
              className={`${styles.pageBtn} ${page >= totalPages ? styles.pageBtnDisabled : ""}`}
              aria-disabled={page >= totalPages}
            >
              NEXT ►
            </Link>
          </div>
        )}
      </div>
    </>
  );
}

function FilterSelect({
  label,
  name,
  value,
  options,
  emptyLabel,
  allLabel,
  labelFor,
}: {
  label: string;
  name: string;
  value: string;
  options: string[];
  emptyLabel?: string;
  allLabel?: string;
  labelFor?: (option: string) => string;
}) {
  return (
    <label className={styles.selectWrap}>
      <span className={styles.selectLabel}>{label}</span>
      <select
        className={styles.select}
        name={name}
        defaultValue={value}
        onChange={(e) => e.currentTarget.form?.submit()}
      >
        {emptyLabel && <option value="">{emptyLabel}</option>}
        {options.map((o) => (
          <option key={o} value={o}>
            {allLabel && o === "ALL" ? allLabel : (labelFor ? labelFor(o) : o)}
          </option>
        ))}
      </select>
    </label>
  );
}
