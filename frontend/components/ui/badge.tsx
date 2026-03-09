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
        "inline-flex items-center rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs uppercase tracking-[0.18em] text-[var(--text-secondary)]",
        className
      )}
    >
      {children}
    </span>
  );
}
