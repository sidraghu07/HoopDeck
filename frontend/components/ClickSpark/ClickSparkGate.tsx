"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import ClickSpark from "./ClickSpark";

const DISABLED_PATHS = ["/players"];

export default function ClickSparkGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  if (DISABLED_PATHS.includes(pathname)) {
    return <>{children}</>;
  }

  return (
    <ClickSpark sparkColor="#e8b339" sparkSize={10} sparkRadius={18} sparkCount={8} duration={450}>
      {children}
    </ClickSpark>
  );
}
