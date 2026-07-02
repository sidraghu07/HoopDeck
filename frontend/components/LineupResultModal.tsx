"use client";

import { LineupResult } from "@/lib/types";
import styles from "./LineupResultModal.module.css";

const FEATURE_LABELS: { key: keyof LineupResult["roster_features"]; label: string }[] = [
  { key: "avg_overall", label: "OVERALL" },
  { key: "avg_scoring", label: "SCORING" },
  { key: "avg_playmaking", label: "PLAYMAKING" },
  { key: "avg_defense", label: "DEFENSE" },
  { key: "avg_impact", label: "IMPACT" },
  { key: "star_power", label: "STAR POWER" },
  { key: "bench_overall", label: "BENCH DEPTH" },
];

export default function LineupResultModal({
  result,
  onClose,
}: {
  result: LineupResult;
  onClose: () => void;
}) {
  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span>LINEUP PROJECTION</span>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className={styles.hero}>
          <div className={styles.record}>{result.predicted_record}</div>
          <div className={styles.heroStats}>
            <span>WIN% {(result.predicted_win_pct * 100).toFixed(1)}%</span>
            <span>
              NET RTG {result.predicted_net_rating > 0 ? "+" : ""}
              {result.predicted_net_rating.toFixed(1)}
            </span>
          </div>
        </div>

        <div className={styles.sectionLabel}>ROSTER COMPOSITE RATINGS</div>
        <div className={styles.featureGrid}>
          {FEATURE_LABELS.map(({ key, label }) => (
            <div key={key} className={styles.featureCell}>
              <span className={styles.featureValue}>{result.roster_features[key].toFixed(1)}</span>
              <span className={styles.featureLabel}>{label}</span>
            </div>
          ))}
        </div>

        <div className={styles.sectionLabel}>FULL ROSTER BREAKDOWN</div>
        <div className={styles.rosterTable}>
          <div className={styles.rosterHeaderRow}>
            <span>POS</span>
            <span>PLAYER</span>
            <span>SEASON</span>
            <span>OVR</span>
            <span>MIN</span>
          </div>
          {result.roster.map((r) => (
            <div key={`${r.player_id}-${r.season}`} className={styles.rosterRow}>
              <span className={styles.rosterPos}>{r.assigned_position ?? r.primary_position}</span>
              <span className={styles.rosterName}>{r.player_name}</span>
              <span className={styles.rosterSeason}>
                {r.season} · {r.team}
              </span>
              <span className={styles.rosterOvr}>{r.rating_overall}</span>
              <span className={styles.rosterMin}>{r.assumed_minutes}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
