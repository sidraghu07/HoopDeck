function apiBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

export async function getPlayers(filters?: {
  season?: string;
  league?: string;
  tier?: string;
  position?: string;
  name?: string;
  page?: number;
  sort?: string;
  dir?: string;
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

export async function getPlayerPlayoffs(id: number, season?: string) {
  const params = season ? `?season=${season}` : "";
  const res = await fetch(`${apiBase()}/api/players/${id}/playoffs${params}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getPlayerStatsBySeason(season: string, league: string = "NBA") {
  const res = await fetch(`${apiBase()}/api/stats/players?season=${season}&league=${league}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getTeamStatsBySeason(season: string, league: string = "NBA") {
  const res = await fetch(`${apiBase()}/api/stats/teams?season=${season}&league=${league}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getPlayerStatsBySeasons(seasons: string[], league: string = "NBA") {
  const res = await fetch(`${apiBase()}/api/stats/players?seasons=${seasons.join(",")}&league=${league}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getTeamStatsBySeasons(seasons: string[], league: string = "NBA") {
  const res = await fetch(`${apiBase()}/api/stats/teams?seasons=${seasons.join(",")}&league=${league}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getTeamStats(teams: string[], league: string = "NBA") {
  const res = await fetch(`${apiBase()}/api/stats/teams?teams=${teams.join(",")}&league=${league}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getTeamList(league: string = "NBA") {
  const res = await fetch(`${apiBase()}/api/stats/teams?league=${league}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getCurrentTeams(league: string) {
  const res = await fetch(`${apiBase()}/api/teams/${league}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getTeamRoster(league: string, team: string, season?: string) {
  const params = season ? `?season=${season}` : "";
  const res = await fetch(`${apiBase()}/api/teams/${league}/${team}/roster${params}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getTeamPicks(league: string, team: string) {
  const res = await fetch(`${apiBase()}/api/teams/${league}/${team}/picks`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function simulateTrade(payload: {
  league: string;
  team_a: string;
  team_b: string;
  players_from_a: number[];
  players_from_b: number[];
  picks_from_a?: number[];
  picks_from_b?: number[];
  season?: string;
}) {
  const res = await fetch(`${apiBase()}/api/trades/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `API ${res.status}`);
  }
  return res.json();
}

export async function simulateLineup(
  league: string,
  players: { player_id: number; season: string; position?: string }[]
) {
  const res = await fetch(`${apiBase()}/api/lineups/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ league, players }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `API ${res.status}`);
  }
  return res.json();
}
