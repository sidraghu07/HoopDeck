"use client";

import { useEffect, useState } from "react";
import { getCurrentTeams, getTeamPicks, getTeamRoster, simulateTrade } from "@/lib/api";
import { DraftPick, TeamListItem, TeamRosterEntry, TradeResult } from "@/lib/types";
import TradeResultModal from "./TradeResultModal";
import styles from "./TradeSimulator.module.css";

const LEAGUES = ["NBA", "WNBA"] as const;

type SideState = {
  team: string;
  roster: TeamRosterEntry[];
  picks: DraftPick[];
  outgoingPlayers: Set<number>;
  outgoingPicks: Set<number>;
  loading: boolean;
};

const EMPTY_SIDE: SideState = {
  team: "",
  roster: [],
  picks: [],
  outgoingPlayers: new Set(),
  outgoingPicks: new Set(),
  loading: false,
};

function Side({
  label,
  side,
  teams,
  onTeamChange,
  onTogglePlayer,
  onTogglePick,
}: {
  label: string;
  side: SideState;
  teams: TeamListItem[];
  onTeamChange: (team: string) => void;
  onTogglePlayer: (playerId: number) => void;
  onTogglePick: (pickId: number) => void;
}) {
  return (
    <div className={styles.sidePanel}>
      <div className={styles.sideLabel}>{label}</div>
      <select
        className={styles.select}
        value={side.team}
        onChange={(e) => onTeamChange(e.target.value)}
      >
        <option value="">Select team…</option>
        {teams.map((t) => (
          <option key={t.team} value={t.team}>
            {t.team_name}
          </option>
        ))}
      </select>

      {side.loading && <div className={styles.hint}>Loading roster…</div>}

      {!side.loading && side.team && (
        <>
          <div className={styles.sectionLabel}>ROSTER — click to send</div>
          <div className={styles.rosterList}>
            {side.roster.map((p) => (
              <button
                key={p.player_id}
                type="button"
                className={`${styles.rosterItem} ${side.outgoingPlayers.has(p.player_id) ? styles.rosterItemOut : ""}`}
                onClick={() => onTogglePlayer(p.player_id)}
              >
                <span className={styles.rosterItemName}>{p.player_name}</span>
                <span className={styles.rosterItemMeta}>
                  {p.primary_position ?? "—"} · {p.rating_overall ?? "—"}
                  {p.is_fallback_season ? ` (${p.season})` : ""}
                </span>
              </button>
            ))}
          </div>

          <div className={styles.sectionLabel}>DRAFT PICKS — click to send</div>
          <div className={styles.rosterList}>
            {side.picks.length === 0 && <div className={styles.hint}>No tracked picks</div>}
            {side.picks.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`${styles.rosterItem} ${side.outgoingPicks.has(p.id) ? styles.rosterItemOut : ""}`}
                onClick={() => onTogglePick(p.id)}
                title={p.protection_note ?? undefined}
              >
                <span className={styles.rosterItemName}>
                  {p.draft_year} Round {p.round} {p.is_swap ? "(swap)" : ""}
                </span>
                <span className={styles.rosterItemMeta}>orig. {p.original_team}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function TradeSimulator() {
  const [league, setLeague] = useState<string>("NBA");
  const [teams, setTeams] = useState<TeamListItem[]>([]);
  const [sideA, setSideA] = useState<SideState>(EMPTY_SIDE);
  const [sideB, setSideB] = useState<SideState>(EMPTY_SIDE);
  const [result, setResult] = useState<TradeResult | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [simLoading, setSimLoading] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  useEffect(() => {
    getCurrentTeams(league)
      .then((data: TeamListItem[]) =>
        setTeams([...data].sort((a, b) => (a.team_name ?? a.team).localeCompare(b.team_name ?? b.team)))
      )
      .catch(() => setTeams([]));
  }, [league]);

  function switchLeague(next: string) {
    if (next === league) return;
    setLeague(next);
    setSideA(EMPTY_SIDE);
    setSideB(EMPTY_SIDE);
    setResult(null);
    setShowResult(false);
    setSimError(null);
  }

  function loadSide(team: string, setSide: (s: SideState) => void) {
    setSide({ ...EMPTY_SIDE, team, loading: true });
    Promise.all([getTeamRoster(league, team), getTeamPicks(league, team)])
      .then(([roster, picks]: [TeamRosterEntry[], DraftPick[]]) => {
        setSide({
          team,
          roster: [...roster].sort((a, b) => (b.rating_overall ?? 0) - (a.rating_overall ?? 0)),
          picks,
          outgoingPlayers: new Set(),
          outgoingPicks: new Set(),
          loading: false,
        });
      })
      .catch(() => setSide({ ...EMPTY_SIDE, team }));
    setResult(null);
    setShowResult(false);
    setSimError(null);
  }

  function toggleSet<T>(set: Set<T>, value: T): Set<T> {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  }

  const canSimulate =
    sideA.team &&
    sideB.team &&
    sideA.team !== sideB.team &&
    (sideA.outgoingPlayers.size > 0 || sideB.outgoingPlayers.size > 0);

  function runSimulation() {
    setSimLoading(true);
    setSimError(null);
    simulateTrade({
      league,
      team_a: sideA.team,
      team_b: sideB.team,
      players_from_a: [...sideA.outgoingPlayers],
      players_from_b: [...sideB.outgoingPlayers],
      picks_from_a: [...sideA.outgoingPicks],
      picks_from_b: [...sideB.outgoingPicks],
    })
      .then((data: TradeResult) => {
        setResult(data);
        setShowResult(true);
      })
      .catch((err: Error) => setSimError(err.message))
      .finally(() => setSimLoading(false));
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.topBar}>
        <div className={styles.leagueToggle}>
          {LEAGUES.map((l) => (
            <button
              key={l}
              type="button"
              className={`${styles.leagueBtn} ${league === l ? styles.leagueBtnActive : ""}`}
              onClick={() => switchLeague(l)}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.sidesGrid}>
        <Side
          label="TEAM A"
          side={sideA}
          teams={teams}
          onTeamChange={(team) => loadSide(team, setSideA)}
          onTogglePlayer={(id) => setSideA({ ...sideA, outgoingPlayers: toggleSet(sideA.outgoingPlayers, id) })}
          onTogglePick={(id) => setSideA({ ...sideA, outgoingPicks: toggleSet(sideA.outgoingPicks, id) })}
        />
        <Side
          label="TEAM B"
          side={sideB}
          teams={teams}
          onTeamChange={(team) => loadSide(team, setSideB)}
          onTogglePlayer={(id) => setSideB({ ...sideB, outgoingPlayers: toggleSet(sideB.outgoingPlayers, id) })}
          onTogglePick={(id) => setSideB({ ...sideB, outgoingPicks: toggleSet(sideB.outgoingPicks, id) })}
        />
      </div>

      <button type="button" className={styles.simulateBtn} disabled={!canSimulate || simLoading} onClick={runSimulation}>
        {simLoading ? "SIMULATING…" : "SIMULATE TRADE"}
      </button>
      {simError && <div className={styles.error}>{simError}</div>}
      {result && !showResult && (
        <button type="button" className={styles.viewResultBtn} onClick={() => setShowResult(true)}>
          VIEW LAST RESULT
        </button>
      )}

      {showResult && result && <TradeResultModal result={result} onClose={() => setShowResult(false)} />}
    </div>
  );
}
