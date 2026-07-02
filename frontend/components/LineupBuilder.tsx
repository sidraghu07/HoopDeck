"use client";

import { useEffect, useState } from "react";
import { getPlayer, getPlayers, simulateLineup } from "@/lib/api";
import { CareerCard, LineupResult, PlayerSeason } from "@/lib/types";
import PlayerCard from "./PlayerCard";
import LineupResultModal from "./LineupResultModal";
import styles from "./LineupBuilder.module.css";

type DragPayload =
  | { kind: "new"; entry: PlayerSeason }
  | { kind: "slot"; index: number }
  | { kind: "search"; player_id: number; player_name: string };

const STARTER_LABELS = ["PG", "SG", "SF", "PF", "C"];
const BENCH_COUNT = 10;
const TOTAL_SLOTS = STARTER_LABELS.length + BENCH_COUNT;

function slotLabel(index: number): string {
  return index < STARTER_LABELS.length ? STARTER_LABELS[index] : `BENCH ${index - STARTER_LABELS.length + 1}`;
}

function slotPosition(index: number): string | undefined {
  return index < STARTER_LABELS.length ? STARTER_LABELS[index] : undefined;
}

export default function LineupBuilder() {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<CareerCard[]>([]);
  const [searching, setSearching] = useState(false);
  const [activePlayer, setActivePlayer] = useState<{ id: number; name: string; seasons: PlayerSeason[] } | null>(null);
  const [loadingSeasons, setLoadingSeasons] = useState(false);
  const [slots, setSlots] = useState<(PlayerSeason | null)[]>(Array(TOTAL_SLOTS).fill(null));
  const [dragOverSlot, setDragOverSlot] = useState<number | null>(null);
  const [result, setResult] = useState<LineupResult | null>(null);
  const [showResultModal, setShowResultModal] = useState(false);
  const [simLoading, setSimLoading] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  useEffect(() => {
    if (query.trim().length < 2) {
      return;
    }
    let cancelled = false;
    setSearching(true);
    const timeout = setTimeout(() => {
      getPlayers({ season: "ALL", name: query, page: 1 })
        .then((data) => { if (!cancelled) setSearchResults(data?.players ?? []); })
        .catch(() => { if (!cancelled) setSearchResults([]); })
        .finally(() => { if (!cancelled) setSearching(false); });
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [query]);

  function pickPlayer(playerId: number, name: string) {
    setLoadingSeasons(true);
    setActivePlayer({ id: playerId, name, seasons: [] });
    getPlayer(playerId)
      .then((seasons: PlayerSeason[]) => {
        setActivePlayer({
          id: playerId,
          name,
          seasons: [...seasons].sort((a, b) => b.season.localeCompare(a.season)),
        });
      })
      .finally(() => setLoadingSeasons(false));
  }

  function isPlaced(playerId: number, season: string): boolean {
    return slots.some((s) => s !== null && s.player_id === playerId && s.season === season);
  }

  function placeInSlot(index: number, entry: PlayerSeason) {
    setSlots((prev) => {
      const cleared = prev.map((s) => (s && s.player_id === entry.player_id && s.season === entry.season ? null : s));
      const next = [...cleared];
      next[index] = entry;
      return next;
    });
    setResult(null);
  }

  function bestSlotFor(position: string): number {
    const starterIdx = STARTER_LABELS.indexOf(position);
    if (starterIdx !== -1 && slots[starterIdx] === null) return starterIdx;
    const benchIdx = slots.findIndex((s, i) => s === null && i >= STARTER_LABELS.length);
    if (benchIdx !== -1) return benchIdx;
    return slots.findIndex((s) => s === null);
  }

  function addToFirstEmpty(entry: PlayerSeason) {
    if (isPlaced(entry.player_id, entry.season)) return;
    const idx = bestSlotFor(entry.primary_position);
    if (idx === -1) return;
    placeInSlot(idx, entry);
    setActivePlayer(null);
    setQuery("");
    setSearchResults([]);
  }

  function removeSlot(index: number) {
    setSlots((prev) => {
      const next = [...prev];
      next[index] = null;
      return next;
    });
    setResult(null);
  }

  function swapSlots(a: number, b: number) {
    if (a === b) return;
    setSlots((prev) => {
      const next = [...prev];
      [next[a], next[b]] = [next[b], next[a]];
      return next;
    });
    setResult(null);
  }

  function setWholeCardDragImage(e: React.DragEvent) {
    const wrap = (e.currentTarget as HTMLElement).parentElement;
    if (wrap) {
      e.dataTransfer.setDragImage(wrap, wrap.offsetWidth / 2, wrap.offsetHeight / 2);
    }
  }

  function onCardDragStart(e: React.DragEvent, s: PlayerSeason) {
    const payload: DragPayload = { kind: "new", entry: s };
    e.dataTransfer.setData("application/json", JSON.stringify(payload));
    e.dataTransfer.effectAllowed = "copy";
    setWholeCardDragImage(e);
  }

  function onSearchCardDragStart(e: React.DragEvent, c: CareerCard) {
    const payload: DragPayload = { kind: "search", player_id: c.player_id, player_name: c.player_name };
    e.dataTransfer.setData("application/json", JSON.stringify(payload));
    e.dataTransfer.effectAllowed = "copy";
    setWholeCardDragImage(e);
  }

  function peakSeason(seasons: PlayerSeason[]): PlayerSeason {
    return seasons.reduce((best, s) => (s.ratings.overall > best.ratings.overall ? s : best));
  }

  function onSlotDragStart(e: React.DragEvent, index: number) {
    const payload: DragPayload = { kind: "slot", index };
    e.dataTransfer.setData("application/json", JSON.stringify(payload));
    e.dataTransfer.effectAllowed = "move";
    setWholeCardDragImage(e);
  }

  function onSlotDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.dataTransfer.dropEffect = e.dataTransfer.effectAllowed === "move" ? "move" : "copy";
  }

  function onSlotDrop(e: React.DragEvent, index: number) {
    e.preventDefault();
    setDragOverSlot(null);
    const raw = e.dataTransfer.getData("application/json");
    if (!raw) return;
    const payload = JSON.parse(raw) as DragPayload;
    if (payload.kind === "new") {
      if (isPlaced(payload.entry.player_id, payload.entry.season)) return;
      placeInSlot(index, payload.entry);
      setActivePlayer(null);
      setQuery("");
      setSearchResults([]);
    } else if (payload.kind === "slot") {
      swapSlots(payload.index, index);
    } else {
      getPlayer(payload.player_id)
        .then((seasons: PlayerSeason[]) => {
          if (!seasons.length) return;
          const s = peakSeason(seasons);
          if (isPlaced(s.player_id, s.season)) return;
          placeInSlot(index, s);
          setQuery("");
          setSearchResults([]);
        })
        .catch((err) => console.error("Failed to resolve dragged player", err));
    }
  }

  function simulate() {
    const payload = slots
      .map((entry, i) =>
        entry
          ? { player_id: entry.player_id, season: entry.season, position: slotPosition(i) }
          : null
      )
      .filter((p): p is { player_id: number; season: string; position: string | undefined } => p !== null);

    setSimLoading(true);
    setSimError(null);
    setResult(null);
    simulateLineup(payload)
      .then((r) => {
        setResult(r);
        setShowResultModal(true);
      })
      .catch((e) => setSimError(e instanceof Error ? e.message : "Simulation failed"))
      .finally(() => setSimLoading(false));
  }

  const filledCount = slots.filter((s) => s !== null).length;
  const canSimulate = filledCount >= 5 && !simLoading;
  const visibleResults = query.trim().length < 2 ? [] : searchResults;

  return (
    <div className={styles.wrap}>
      <div className={styles.searchPanel}>
        <div className={styles.searchBox}>
          <span className={styles.prompt}>&gt;</span>
          <input
            className={styles.input}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActivePlayer(null);
            }}
            placeholder="SEARCH ANY PLAYER, ANY ERA..."
            spellCheck={false}
            autoComplete="off"
          />
        </div>

        {searching && <div className={styles.hint}>SEARCHING...</div>}

        {!activePlayer && visibleResults.length > 0 && (
          <>
            <div className={styles.hint}>DRAG A CARD ONTO A SLOT, OR CLICK TO PICK A SPECIFIC SEASON</div>
            <div className={styles.seasonGrid}>
              {visibleResults.map((c) => (
                <div key={c.player_id} className={styles.miniCardWrap}>
                  <PlayerCard
                    mode="career"
                    data={c.career}
                    player_name={c.player_name}
                    player_id={c.player_id}
                    scale={0.55}
                    draggable
                    onDragStart={(e) => onSearchCardDragStart(e, c)}
                    onClick={() => pickPlayer(c.player_id, c.player_name)}
                  />
                </div>
              ))}
            </div>
          </>
        )}

        {activePlayer && (
          <div className={styles.seasonPicker}>
            <div className={styles.seasonPickerHeader}>
              <span>{activePlayer.name} — PICK A SEASON</span>
              <button type="button" className={styles.closeBtn} onClick={() => setActivePlayer(null)}>✕</button>
            </div>
            {loadingSeasons ? (
              <div className={styles.hint}>LOADING SEASONS...</div>
            ) : (
              <>
                <div className={styles.hint}>DRAG A CARD ONTO A SLOT, OR CLICK TO FILL THE NEXT OPEN ONE</div>
                <div className={styles.seasonGrid}>
                  {activePlayer.seasons.map((s) => {
                    const placed = isPlaced(s.player_id, s.season);
                    return (
                      <div
                        key={s.season}
                        className={`${styles.miniCardWrap} ${placed ? styles.miniCardPlaced : ""}`}
                      >
                        <PlayerCard
                          mode="season"
                          data={s}
                          scale={0.55}
                          draggable={!placed}
                          onDragStart={(e) => onCardDragStart(e, s)}
                          onClick={placed ? undefined : () => addToFirstEmpty(s)}
                        />
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      <div className={styles.rosterPanel}>
        <div className={styles.rosterHeader}>
          ROSTER ({filledCount}/15)
          {filledCount < 5 && <span className={styles.needMore}> — NEED AT LEAST 5</span>}
        </div>

        <div className={styles.starterRow}>
          {slots.slice(0, STARTER_LABELS.length).map((entry, i) => (
            <Slot
              key={i}
              index={i}
              label={slotLabel(i)}
              entry={entry}
              isDragOver={dragOverSlot === i}
              onDragStart={onSlotDragStart}
              onDragOver={onSlotDragOver}
              onDragEnter={() => setDragOverSlot(i)}
              onDragLeave={() => setDragOverSlot((prev) => (prev === i ? null : prev))}
              onDrop={onSlotDrop}
              onRemove={removeSlot}
            />
          ))}
        </div>

        <div className={styles.benchLabel}>BENCH</div>
        <div className={styles.benchGrid}>
          {slots.slice(STARTER_LABELS.length).map((entry, i) => {
            const index = STARTER_LABELS.length + i;
            return (
              <Slot
                key={index}
                index={index}
                label={slotLabel(index)}
                entry={entry}
                isDragOver={dragOverSlot === index}
                onDragStart={onSlotDragStart}
                onDragOver={onSlotDragOver}
                onDragEnter={() => setDragOverSlot(index)}
                onDragLeave={() => setDragOverSlot((prev) => (prev === index ? null : prev))}
                onDrop={onSlotDrop}
                onRemove={removeSlot}
              />
            );
          })}
        </div>

        <button type="button" className={styles.simulateBtn} onClick={simulate} disabled={!canSimulate}>
          {simLoading ? "SIMULATING..." : "SIMULATE SEASON"}
        </button>

        {simError && <div className={styles.error}>{simError}</div>}

        {result && !showResultModal && (
          <button
            type="button"
            className={styles.viewResultBtn}
            onClick={() => setShowResultModal(true)}
          >
            VIEW PROJECTION — {result.predicted_record}
          </button>
        )}
      </div>

      {result && showResultModal && (
        <LineupResultModal result={result} onClose={() => setShowResultModal(false)} />
      )}
    </div>
  );
}

function Slot({
  index,
  label,
  entry,
  isDragOver,
  onDragStart,
  onDragOver,
  onDragEnter,
  onDragLeave,
  onDrop,
  onRemove,
}: {
  index: number;
  label: string;
  entry: PlayerSeason | null;
  isDragOver: boolean;
  onDragStart: (e: React.DragEvent, index: number) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDragEnter: () => void;
  onDragLeave: () => void;
  onDrop: (e: React.DragEvent, index: number) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <div
      className={`${styles.slot} ${entry ? styles.slotFilled : styles.slotEmpty} ${isDragOver ? styles.slotDragOver : ""}`}
      onDragOver={onDragOver}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDrop={(e) => onDrop(e, index)}
    >
      <span className={styles.slotLabel}>{label}</span>
      {entry ? (
        <div className={styles.miniCardWrap}>
          <PlayerCard
            mode="season"
            data={entry}
            scale={0.55}
            draggable
            onDragStart={(e) => onDragStart(e, index)}
          />
          <button
            type="button"
            className={styles.slotRemove}
            onClick={() => onRemove(index)}
            aria-label={`Remove ${entry.player_name}`}
          >
            ✕
          </button>
        </div>
      ) : (
        <span className={styles.slotHint}>DROP CARD</span>
      )}
    </div>
  );
}
