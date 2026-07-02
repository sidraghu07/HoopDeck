import Link from "next/link";
import FaultyTerminalSafe from "@/components/FaultyTerminal/FaultyTerminalSafe";
import Shuffle from "@/components/Shuffle/Shuffle";
import HomeGallery from "@/components/HomeGallery";
import { getPlayers } from "@/lib/api";
import { PlayerSeasonCard } from "@/lib/types";
import styles from "./page.module.css";

const FEATURED_SEASON = "2025-26";
const GALLERY_SIZE = 8;
const MIN_OVERALL = 80;

function pickRandom<T>(pool: T[], count: number): T[] {
  const shuffled = [...pool];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled.slice(0, count);
}

export default async function HomePage() {
  let players: PlayerSeasonCard[] = [];
  try {
    const data = await getPlayers({ season: FEATURED_SEASON });
    players = data?.players ?? [];
  } catch {
  }

  const eligible = players.filter((p) => p.ratings.overall >= MIN_OVERALL);
  const featured = pickRandom(eligible, GALLERY_SIZE);

  return (
    <main className={styles.main}>
      <div className={styles.terminalBg} aria-hidden>
        <FaultyTerminalSafe
          tint="#6b5499"
          scale={1.4}
          gridMul={[2, 1]}
          digitSize={1.2}
          timeScale={0.4}
          scanlineIntensity={0.4}
          glitchAmount={1}
          flickerAmount={0.6}
          noiseAmp={1}
          chromaticAberration={0}
          curvature={0.15}
          mouseReact
          mouseStrength={0.3}
          brightness={0.85}
        />
      </div>
      <div className={styles.scanlines} aria-hidden />

      <div className={styles.hero}>
        <div className={styles.heroLeft}>
          <h1 className={styles.title}>
            <Shuffle
              text="NBA"
              tag="span"
              duration={0.4}
              shuffleDirection="right"
              stagger={0.04}
              colorFrom="#a99bc4"
              colorTo="#f4ecd8"
              triggerOnHover
              style={{
                fontSize: "clamp(28px, 7vw, 64px)",
                letterSpacing: "4px",
                textShadow: "3px 3px 0 #6b5499, 6px 6px 0 rgba(107, 84, 153, 0.3)"
              }}
            />
            <Shuffle
              text="CARDS"
              tag="span"
              duration={0.45}
              shuffleDirection="right"
              stagger={0.05}
              colorFrom="#8a5a12"
              colorTo="#e8b339"
              triggerOnHover
              style={{
                fontSize: "clamp(44px, 11vw, 104px)",
                letterSpacing: "6px",
                textShadow: "3px 3px 0 #8a5a12, 6px 6px 0 rgba(232, 179, 57, 0.3)"
              }}
            />
          </h1>

          <p className={styles.sub}>
            An Easy Way to Analyze Your Favorite Players
          </p>

          <Link href="/players" className={styles.enterBtn}>
            <span className={styles.btnCaret}>&gt;</span>
            ENTER GALLERY
            <span className={styles.btnCaret2}>_</span>
          </Link>

          <div className={styles.footer}>
            <span>POWERED BY NBA STATS &amp; SHOT TRACKING</span>
          </div>
        </div>

        {featured.length > 0 && (
          <div className={styles.heroRight}>
            <div className={styles.gallery}>
              <HomeGallery players={featured} />
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
