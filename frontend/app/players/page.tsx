import Link from "next/link";
import { redirect } from "next/navigation";
import { getPlayers } from "@/lib/api";
import { CareerCard, PlayerSeasonCard } from "@/lib/types";
import PlayersExplorer from "@/components/PlayersExplorer";
import styles from "./page.module.css";

const DEFAULT_SEASON = "2025-26";

interface PageProps {
  searchParams: Promise<{ season?: string; name?: string; tier?: string; position?: string; page?: string }>;
}

export default async function PlayersPage({ searchParams }: PageProps) {
  const { season, name, tier, position, page } = await searchParams;

  if (!season) {
    redirect(`/players?season=${DEFAULT_SEASON}`);
  }

  const isAllSeasons = season === "ALL";
  const currentPage = Math.max(1, parseInt(page ?? "1", 10) || 1);

  const data = await getPlayers({
    season,
    name,
    tier,
    position,
    page: isAllSeasons ? currentPage : undefined,
  });

  const seasonCards: PlayerSeasonCard[] = isAllSeasons ? [] : (data?.players ?? []);
  const careerCards: CareerCard[] = isAllSeasons ? (data?.players ?? []) : [];

  const metaSeasons: string[] = (data?.meta?.seasons ?? [DEFAULT_SEASON])
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
    <>
      <nav className={styles.nav}>
        <Link href="/" className={styles.homeLink}>← HOME</Link>
        <span className={styles.navTitle}>PLAYER DATABASE</span>
      </nav>
      <PlayersExplorer
        seasonCards={seasonCards}
        careerCards={careerCards}
        cardCount={data?.meta?.total ?? 0}
        isAllSeasons={isAllSeasons}
        season={season}
        name={name ?? ""}
        tier={tier ?? ""}
        position={position ?? ""}
        seasons={seasons}
        positions={positions}
        page={currentPage}
        totalPages={data?.meta?.total_pages ?? 1}
      />
    </>
  );
}
