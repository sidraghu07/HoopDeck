"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Header.module.css";

const NAV_LINKS = [
  { href: "/players", label: "PLAYERS" },
  { href: "/lineups", label: "LINEUP SIM" },
  { href: "/trades", label: "TRADES" },
  { href: "/charts", label: "CHARTS" },
];

export default function Header() {
  const pathname = usePathname();

  return (
    <header className={styles.header}>
      <Link href="/" className={styles.brand}>
        HOOPDECK
      </Link>
      <nav className={styles.nav}>
        {NAV_LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`${styles.link} ${pathname.startsWith(l.href) ? styles.active : ""}`}
          >
            {l.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
