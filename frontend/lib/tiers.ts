import { Tier } from "./types";

export const TIER_RANK: Record<Tier, number> = {
  Bench: 0,
  Rotation: 1,
  Starter: 2,
  "All-Star": 3,
  "Franchise Player": 4,
};

export const TIER_STYLE: Record<
  Tier,
  { border: string; glow: string; label: string; bg: string }
> = {
  Bench: {
    border: "#7d8597",
    glow: "rgba(125,133,151,0.35)",
    bg: "#2a2e3a",
    label: "ROLE PLAYER",
  },
  Rotation: {
    border: "#4ade80",
    glow: "rgba(74,222,128,0.45)",
    bg: "#163325",
    label: "ROTATION",
  },
  Starter: {
    border: "#38bdf8",
    glow: "rgba(56,189,248,0.5)",
    bg: "#122d3d",
    label: "STARTER",
  },
  "All-Star": {
    border: "#c084fc",
    glow: "rgba(192,132,252,0.55)",
    bg: "#2a1f40",
    label: "ALL-STAR",
  },
  "Franchise Player": {
    border: "#fbbf24",
    glow: "rgba(251,191,36,0.65)",
    bg: "#3a2c10",
    label: "SUPERSTAR",
  },
};
