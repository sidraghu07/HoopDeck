const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  const res = await fetch(`${API}/api/players${qs ? `?${qs}` : ""}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getPlayer(id: number, season?: string) {
  const params = season ? `?season=${season}` : "";
  const res = await fetch(`${API}/api/players/${id}${params}`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
