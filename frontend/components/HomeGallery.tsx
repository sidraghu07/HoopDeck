"use client";

import { useMemo } from "react";
import Carousel, { type CarouselItem } from "./Carousel/Carousel";
import PlayerCard from "./PlayerCard";
import { PlayerSeasonCard } from "@/lib/types";

export default function HomeGallery({ players }: { players: PlayerSeasonCard[] }) {
  const items: CarouselItem[] = useMemo(
    () =>
      players.map((p) => ({
        id: p.player_id,
        content: (
          <PlayerCard
            mode="season"
            data={p}
            onClick={() => { window.location.href = `/players/${p.player_id}?season=${p.season}`; }}
          />
        ),
      })),
    [players]
  );

  if (items.length === 0) return null;

  return (
    <Carousel
      items={items}
      baseWidth={272}
      autoplay
      autoplayDelay={3500}
      pauseOnHover
      loop
    />
  );
}
