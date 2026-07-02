"use client";

import Link from "next/link";
import styles from "./error.module.css";

export default function PlayersError({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className={styles.wrap}>
      <div className={styles.box}>
        <div className={styles.title}>CONNECTION ERROR</div>
        <div className={styles.message}>
          {error.message.includes("fetch")
            ? "Could not reach the API. Make sure it is running on port 8000."
            : error.message}
        </div>
        <div className={styles.hint}>
          Run: <code>uvicorn api.main:app --reload</code>
        </div>
        <div className={styles.actions}>
          <button className={styles.btn} onClick={reset}>RETRY</button>
          <Link href="/" className={styles.btn}>← HOME</Link>
        </div>
      </div>
    </div>
  );
}
