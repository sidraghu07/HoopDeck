"use client";

import Image from "next/image";
import { useState } from "react";
import { CareerSummary, PlayerSeasonCard } from "@/lib/types";
import { TIER_STYLE } from "@/lib/tiers";
import styles from "./PlayerCard.module.css";

type SeasonCardProps = {
  mode: "season";
  data: PlayerSeasonCard;
};

type CareerCardProps = {
  mode: "career";
  data: CareerSummary;
  player_name: string;
  player_id: number;
};

export type PlayerCardProps = SeasonCardProps | CareerCardProps;

export default function PlayerCard(
  props: PlayerCardProps & {
    onClick?: () => void;
    draggable?: boolean;
    onDragStart?: (e: React.DragEvent) => void;
    scale?: number;
  }
) {
  const tier = props.mode === "season" ? props.data.tier : props.data.bestTier;
  const style = TIER_STYLE[tier];

  const name = props.mode === "season" ? props.data.player_name : props.player_name;
  const playerId = props.mode === "season" ? props.data.player_id : props.player_id;
  const hasPhoto = props.data.has_photo;
  const overall = props.mode === "season" ? props.data.ratings.overall : props.data.bestOverall;
  const position = props.mode === "season" ? props.data.primary_position : props.data.primary_position;
  const team = props.mode === "season" ? props.data.team : props.data.teams.join(" / ");
  const tag = props.mode === "season" ? props.data.season : `${props.data.seasonsPlayed} SEASONS`;

  const stats = props.data.per_game;

  const isLegendary = tier === "Franchise Player";

  return (
    <div
      className={`${styles.card} ${isLegendary ? styles.legendary : ""} ${props.onClick ? styles.clickable : ""}`}
      onClick={props.onClick}
      draggable={props.draggable}
      onDragStart={props.onDragStart}
      style={
        {
          "--tier-border": style.border,
          "--tier-glow": style.glow,
          "--tier-bg": style.bg,
          ...(props.scale
            ? { transform: `scale(${props.scale})`, transformOrigin: "top left" }
            : {}),
        } as React.CSSProperties
      }
    >
      <div className={styles.frame}>
        <div className={styles.banner}>
          <span className={styles.tierLabel}>{style.label}</span>
          <span className={styles.editionTag}>{tag}</span>
        </div>

        <PlayerPortrait name={name} playerId={playerId} overall={overall} hasPhoto={hasPhoto} />

        <div className={styles.namePlate}>
          <div className={styles.name} title={name}>
            {name}
          </div>
          <div className={styles.subline}>
            {position} · {team}
          </div>
        </div>

        <div className={styles.statGrid}>
          <Stat label="PTS" value={stats.pts} />
          <Stat label="REB" value={stats.reb} />
          <Stat label="AST" value={stats.ast} />
          <Stat label="STL" value={stats.stl} />
          <Stat label="BLK" value={stats.blk} />
          <Stat label="MIN" value={stats.min} />
        </div>

        <div className={styles.ribbon}>
          <RibbonBit
            label="SCR"
            value={props.mode === "season" ? props.data.ratings.scoring : props.data.ratings.scoring}
          />
          <RibbonBit
            label="PLY"
            value={props.mode === "season" ? props.data.ratings.playmaking : props.data.ratings.playmaking}
          />
          <RibbonBit
            label="DEF"
            value={props.mode === "season" ? props.data.ratings.defense : props.data.ratings.defense}
          />
          <RibbonBit
            label="IMP"
            value={props.mode === "season" ? props.data.ratings.impact : props.data.ratings.impact}
          />
        </div>
      </div>
    </div>
  );
}

function PlayerPortrait({
  name,
  playerId,
  overall,
  hasPhoto,
}: {
  name: string;
  playerId: number;
  overall: number;
  hasPhoto: boolean;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("");

  const imgUrl = `https://cdn.nba.com/headshots/nba/latest/1040x760/${playerId}.png`;

  return (
    <div className={styles.portrait}>
      {hasPhoto && !imgFailed ? (
        <Image
          src={imgUrl}
          alt={name}
          fill
          sizes="220px"
          className={styles.playerImg}
          onError={() => setImgFailed(true)}
          unoptimized
          draggable={false}
        />
      ) : (
        <span className={styles.initials}>{initials}</span>
      )}
      <div className={styles.overallBadge}>
        <span className={styles.overallNum}>{overall}</span>
        <span className={styles.overallLbl}>OVR</span>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.statCell}>
      <span className={styles.statValue}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
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
