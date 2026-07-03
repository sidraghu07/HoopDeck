import type { Metadata } from "next";
import { pressStart2P, vt323 } from "@/lib/fonts";
import ClickSparkGate from "@/components/ClickSpark/ClickSparkGate";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import "./globals.css";

export const metadata: Metadata = {
  title: "HoopDeck",
  description: "Pixel-art NBA player cards database",
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
      </body>
    </html>
  );
}
