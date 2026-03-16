import { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Card({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-[24px] border border-white/10 bg-[var(--card)]/95 shadow-[0_16px_56px_rgba(0,0,0,0.32)] backdrop-blur",
        className
      )}
    >
      {children}
    </div>
  );
}
