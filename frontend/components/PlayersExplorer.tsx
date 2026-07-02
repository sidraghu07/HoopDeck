"use client";

import Link from "next/link";
import { CareerCard, PlayerSeasonCard, Tier } from "@/lib/types";
import { TIER_STYLE } from "@/lib/tiers";
import SearchBar from "./SearchBar";
import PlayerCard from "./PlayerCard";
import styles from "./PlayersExplorer.module.css";

const ALL_TIERS: Tier[] = ["Franchise Player", "All-Star", "Starter", "Rotation", "Bench"];

interface Props {
  seasonCards: PlayerSeasonCard[];
  careerCards: CareerCard[];
  cardCount: number;
  isAllSeasons: boolean;
  season: string;
  name: string;
  tier: string;
  position: string;
  seasons: string[];
  positions: string[];
  page: number;
  totalPages: number;
}

export default function PlayersExplorer({
  seasonCards,
  careerCards,
  cardCount,
  isAllSeasons,
  season,
  name,
  tier,
  position,
  seasons,
  positions,
  page,
  totalPages,
}: Props) {
  function pageUrl(target: number) {
    const params = new URLSearchParams();
    params.set("season", season);
    if (name) params.set("name", name);
    if (tier) params.set("tier", tier);
    if (position) params.set("position", position);
    if (target > 1) params.set("page", String(target));
    return `/players?${params.toString()}`;
  }

  return (
    <>
      <div className={styles.page}>
        <form method="GET" action="/players" className={styles.controls}>
          <SearchBar defaultValue={name} />
          <div className={styles.filterRow}>
            <PixelSelect label="SEASON"   name="season"   value={season}   options={seasons} emptyLabel={undefined} allLabel="ALL SEASONS" />
            <PixelSelect
              label="TIER"
              name="tier"
              value={tier}
              options={ALL_TIERS}
              emptyLabel="ALL TIERS"
              labelFor={(t) => TIER_STYLE[t as Tier]?.label ?? t}
            />
            <PixelSelect label="POS"      name="position" value={position} options={positions} emptyLabel="ALL POS" />
          </div>
        </form>

        <div className={styles.count}>
          {cardCount} CARD{cardCount === 1 ? "" : "S"} FOUND
        </div>

        <div className={styles.grid}>
          {isAllSeasons
            ? careerCards.map((g) => (
                <PlayerCard
                  key={g.player_id}
                  mode="career"
                  data={g.career}
                  player_name={g.player_name}
                  player_id={g.player_id}
                  onClick={() => { window.location.href = `/players/${g.player_id}`; }}
                />
              ))
            : seasonCards.map((p) => (
                <PlayerCard
                  key={`${p.player_id}-${p.season}`}
                  mode="season"
                  data={p}
                  onClick={() => { window.location.href = `/players/${p.player_id}?season=${p.season}`; }}
                />
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

function PixelSelect({
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
