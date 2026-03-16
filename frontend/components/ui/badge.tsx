import { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Badge({
  children,
  className
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-white/10 bg-white/6 px-2.5 py-0.5 text-[11px] uppercase tracking-[0.16em] text-[var(--text-secondary)]",
        className
      )}
    >
      {children}
    </span>
  );
}
