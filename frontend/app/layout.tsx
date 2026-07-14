import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import { pressStart2P, vt323 } from "@/lib/fonts";
import ClickSparkGate from "@/components/ClickSpark/ClickSparkGate";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import CookieConsent from "@/components/CookieConsent";
import "./globals.css";

export const metadata: Metadata = {
  title: "HoopDeck",
  description: "An Easy Way to Analyze Your Favorite Players",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${pressStart2P.variable} ${vt323.variable}`}>
      <body>
        <ClickSparkGate>
          <Header />
          {children}
          <Footer />
        </ClickSparkGate>
        <CookieConsent />
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
