"use client";

import { TradeFairness, TradeLegality, TradeResult, TradeSideResult, TradeVerdict } from "@/lib/types";
import styles from "./TradeResultModal.module.css";

const FAIRNESS_LABEL: Record<TradeFairness["verdict"], string> = {
  favorable: "Favorable",
  fair: "Fair",
  unfavorable: "Lopsided",
};

function FairnessBadge({ fairness }: { fairness: TradeFairness }) {
  const cls =
    fairness.verdict === "favorable"
      ? styles.fairnessGood
      : fairness.verdict === "unfavorable"
        ? styles.fairnessBad
        : styles.fairnessNeutral;
  return (
    <span className={`${styles.fairnessBadge} ${cls}`}>
      {FAIRNESS_LABEL[fairness.verdict]} ({fairness.diff > 0 ? "+" : ""}
      {fairness.diff})
    </span>
  );
}

function SideCard({
  team,
  before,
  after,
  legality,
}: {
  team: string;
  before: TradeSideResult;
  after: TradeSideResult;
  legality: TradeLegality;
}) {
  const winDelta = after.predicted_win_pct - before.predicted_win_pct;
  const netDelta = after.predicted_net_rating - before.predicted_net_rating;
  const deltaClass = netDelta > 0 ? styles.deltaUp : netDelta < 0 ? styles.deltaDown : styles.deltaFlat;

  return (
    <div className={styles.sideCard}>
      <div className={styles.sideHeader}>
        <div className={styles.sideTeam}>{team}</div>
        <FairnessBadge fairness={legality.fairness} />
      </div>
      <div className={styles.sideRow}>
        <div className={styles.sideCol}>
          <span className={styles.sideLabel}>BEFORE</span>
          <span className={styles.sideRecord}>{before.predicted_record}</span>
          <span className={styles.sideSub}>{(before.predicted_win_pct * 100).toFixed(1)}% WIN</span>
        </div>
        <div className={styles.arrow}>→</div>
        <div className={styles.sideCol}>
          <span className={styles.sideLabel}>AFTER</span>
          <span className={styles.sideRecord}>{after.predicted_record}</span>
          <span className={styles.sideSub}>{(after.predicted_win_pct * 100).toFixed(1)}% WIN</span>
        </div>
      </div>
      <div className={`${styles.deltaLine} ${deltaClass}`}>
        NET RTG {netDelta > 0 ? "+" : ""}
        {netDelta.toFixed(1)} &nbsp;·&nbsp; WIN% {winDelta > 0 ? "+" : ""}
        {(winDelta * 100).toFixed(1)}%
      </div>
      <div className={styles.sectionLabel}>TOP-5 AFTER TRADE</div>
      <div className={styles.rosterTable}>
        {after.roster.map((r) => (
          <div key={r.player_id} className={styles.rosterRow}>
            <span className={styles.rosterPos}>{r.primary_position}</span>
            <span className={styles.rosterName}>{r.player_name}</span>
            <span className={styles.rosterTeam}>{r.team}</span>
            <span className={styles.rosterOvr}>{r.rating_overall}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function VerdictBanner({ verdict, teamA, teamB }: { verdict: TradeVerdict; teamA: string; teamB: string }) {
  const bannerClass =
    verdict.cba_legal === null ? styles.bannerNeutral : verdict.cba_legal ? styles.bannerLegal : styles.bannerIllegal;
  const headline =
    verdict.cba_legal === null
      ? "CBA legality not evaluated for this league"
      : verdict.cba_legal
        ? "Trade is CBA-legal for both teams"
        : "Trade would be rejected — CBA violation";

  return (
    <div className={`${styles.verdictBanner} ${bannerClass}`}>
      <div className={styles.verdictHeadline}>{headline}</div>
      <div className={styles.verdictReasons}>
        <div>
          <strong>{teamA}:</strong> {verdict.team_a.reason}
        </div>
        <div>
          <strong>{teamB}:</strong> {verdict.team_b.reason}
        </div>
      </div>
    </div>
  );
}

export default function TradeResultModal({ result, onClose }: { result: TradeResult; onClose: () => void }) {
  const { from_a, from_b } = result.picks_exchanged;

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span>TRADE IMPACT</span>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <VerdictBanner verdict={result.verdict} teamA={result.team_a.team} teamB={result.team_b.team} />

        <div className={styles.note}>
          Impact modeled on each team&apos;s top-5 talent (auto-selected by rating), not full 15-man depth.
        </div>

        <div className={styles.sidesGrid}>
          <SideCard
            team={result.team_a.team}
            before={result.team_a.before}
            after={result.team_a.after}
            legality={result.verdict.team_a}
          />
          <SideCard
            team={result.team_b.team}
            before={result.team_b.before}
            after={result.team_b.after}
            legality={result.verdict.team_b}
          />
        </div>

        {(from_a.length > 0 || from_b.length > 0) && (
          <>
            <div className={styles.sectionLabel}>DRAFT PICKS EXCHANGED</div>
            <div className={styles.picksGrid}>
              <div>
                <div className={styles.picksTeamLabel}>{result.team_a.team} SENDS</div>
                {from_a.length === 0 && <div className={styles.picksNone}>No picks</div>}
                {from_a.map((p) => (
                  <div key={p.id} className={styles.pickRow}>
                    {p.draft_year} R{p.round} {p.is_swap ? "(swap)" : ""} — orig. {p.original_team}
                    {p.protection_note ? ` · ${p.protection_note}` : ""}
                  </div>
                ))}
              </div>
              <div>
                <div className={styles.picksTeamLabel}>{result.team_b.team} SENDS</div>
                {from_b.length === 0 && <div className={styles.picksNone}>No picks</div>}
                {from_b.map((p) => (
                  <div key={p.id} className={styles.pickRow}>
                    {p.draft_year} R{p.round} {p.is_swap ? "(swap)" : ""} — orig. {p.original_team}
                    {p.protection_note ? ` · ${p.protection_note}` : ""}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
