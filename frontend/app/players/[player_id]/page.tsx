import { notFound } from "next/navigation";
import { PlayerSeason, PlayoffPlayerSeason } from "@/lib/types";
import PlayerDetail from "@/components/PlayerDetail";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getPlayerSeasons(id: number): Promise<PlayerSeason[]> {
  const res = await fetch(`${API}/api/players/${id}`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

async function getPlayerPlayoffSeasons(id: number): Promise<PlayoffPlayerSeason[]> {
  const res = await fetch(`${API}/api/players/${id}/playoffs`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

interface PageProps {
  params: Promise<{ player_id: string }>;
  searchParams: Promise<{ season?: string }>;
}

export default async function PlayerPage({ params, searchParams }: PageProps) {
  const { player_id } = await params;
  const { season } = await searchParams;

  const id = parseInt(player_id, 10);
  if (isNaN(id)) return notFound();

  const [seasons, playoffSeasons] = await Promise.all([
    getPlayerSeasons(id),
    getPlayerPlayoffSeasons(id),
  ]);
  if (!seasons.length) return notFound();

  const sorted = [...seasons].sort((a, b) => a.season.localeCompare(b.season));
  const active = season
    ? (sorted.find((s) => s.season === season) ?? sorted[sorted.length - 1])
    : sorted[sorted.length - 1];

  const playoffsBySeason: Record<string, PlayoffPlayerSeason> = {};
  for (const p of playoffSeasons) playoffsBySeason[p.season] = p;

  return <PlayerDetail seasons={sorted} active={active} playoffsBySeason={playoffsBySeason} />;
}
