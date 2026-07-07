import { redirect } from "next/navigation";
import { getPlayers } from "@/lib/api";
import { CareerCard, PlayerSeasonCard } from "@/lib/types";
import PlayersExplorer from "@/components/PlayersExplorer";

const DEFAULT_SEASON: Record<string, string> = { NBA: "2025-26", WNBA: "2025" };
const LEAGUES = ["NBA", "WNBA"];

interface PageProps {
  searchParams: Promise<{
    league?: string;
    season?: string;
    name?: string;
    tier?: string;
    position?: string;
    page?: string;
    sort?: string;
    dir?: string;
  }>;
}

const SORT_FIELDS = ["overall", "pts", "reb", "ast", "stl", "blk", "min"];

export default async function PlayersPage({ searchParams }: PageProps) {
  const { league: rawLeague, season, name, tier, position, page, sort, dir } = await searchParams;
  const league = LEAGUES.includes(rawLeague ?? "") ? (rawLeague as string) : "NBA";

  if (!season) {
    redirect(`/players?league=${league}&season=${DEFAULT_SEASON[league]}`);
  }

  const isAllSeasons = season === "ALL";
  const currentPage = Math.max(1, parseInt(page ?? "1", 10) || 1);
  const currentSort = SORT_FIELDS.includes(sort ?? "") ? (sort as string) : "overall";
  const currentDir = dir === "asc" ? "asc" : "desc";

  const data = await getPlayers({
    season,
    league,
    name,
    tier,
    position,
    page: isAllSeasons ? currentPage : undefined,
    sort: currentSort,
    dir: currentDir,
  });

  const seasonCards: PlayerSeasonCard[] = isAllSeasons ? [] : (data?.players ?? []);
  const careerCards: CareerCard[] = isAllSeasons ? (data?.players ?? []) : [];

  const metaSeasons: string[] = (data?.meta?.seasons ?? [DEFAULT_SEASON[league]])
    .slice()
    .sort((a: string, b: string) => b.localeCompare(a));
  const seasons = ["ALL", ...metaSeasons];

  const positions = Array.from(
    new Set(
      isAllSeasons
        ? careerCards.map((c) => c.career.primary_position)
        : seasonCards.map((p) => p.primary_position)
    )
  ).sort();

  return (
    <PlayersExplorer
      seasonCards={seasonCards}
      careerCards={careerCards}
      cardCount={data?.meta?.total ?? 0}
      isAllSeasons={isAllSeasons}
      league={league}
      season={season}
      name={name ?? ""}
      tier={tier ?? ""}
      position={position ?? ""}
      seasons={seasons}
      positions={positions}
      page={currentPage}
      totalPages={data?.meta?.total_pages ?? 1}
      sort={currentSort}
      dir={currentDir}
    />
  );
}
