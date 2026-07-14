"use client";

import { useEffect, useState } from "react";
import styles from "./CookieConsent.module.css";

const CONSENT_KEY = "hoopdeck-cookie-consent";

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const consent = window.localStorage.getItem(CONSENT_KEY);
    if (!consent) {
      setVisible(true);
    }
  }, []);

  const handleChoice = (choice: "accepted" | "declined") => {
    window.localStorage.setItem(CONSENT_KEY, choice);
    setVisible(false);
  };

  if (!visible) {
    return null;
  }

  return (
    <div className={styles.banner} role="dialog" aria-live="polite" aria-label="Cookie consent">
      <p className={styles.text}>
        HoopDeck uses privacy-friendly, cookieless analytics (Vercel Analytics and Speed Insights)
        to understand site traffic and performance. No cookies are set. By continuing to use this
        site, you agree to this.
      </p>
      <div className={styles.actions}>
        <button className={styles.decline} onClick={() => handleChoice("declined")}>
          DECLINE
        </button>
        <button className={styles.accept} onClick={() => handleChoice("accepted")}>
          ACCEPT
        </button>
      </div>
    </div>
  );
}
