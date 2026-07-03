function apiBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

export async function getPlayers(filters?: {
  season?: string;
  tier?: string;
  position?: string;
  name?: string;
  page?: number;
}) {
  const clean: Record<string, string> = {};
  for (const [k, v] of Object.entries(filters ?? {})) {
    if (v) clean[k] = String(v);
  }
  const params = new URLSearchParams(clean);
  const qs = params.toString();
  const res = await fetch(`${apiBase()}/api/players${qs ? `?${qs}` : ""}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getPlayer(id: number, season?: string) {
  const params = season ? `?season=${season}` : "";
  const res = await fetch(`${apiBase()}/api/players/${id}${params}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getPlayerStatsBySeason(season: string) {
  const res = await fetch(`${apiBase()}/api/stats/players?season=${season}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getTeamStatsBySeason(season: string) {
  const res = await fetch(`${apiBase()}/api/stats/teams?season=${season}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getPlayerStatsBySeasons(seasons: string[]) {
  const res = await fetch(`${apiBase()}/api/stats/players?seasons=${seasons.join(",")}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getTeamStatsBySeasons(seasons: string[]) {
  const res = await fetch(`${apiBase()}/api/stats/teams?seasons=${seasons.join(",")}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getTeamStats(teams: string[]) {
  const res = await fetch(`${apiBase()}/api/stats/teams?teams=${teams.join(",")}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getTeamList() {
  const res = await fetch(`${apiBase()}/api/stats/teams`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function simulateLineup(players: { player_id: number; season: string; position?: string }[]) {
  const res = await fetch(`${apiBase()}/api/lineups/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ players }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `API ${res.status}`);
  }
  return res.json();
}
