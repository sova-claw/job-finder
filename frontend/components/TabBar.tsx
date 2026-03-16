"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { SourceGroup } from "@/lib/types";

const tabs: { value: SourceGroup; label: string }[] = [
  { value: "All", label: "All" },
  { value: "Ukraine", label: "Ukraine" },
  { value: "BigCo", label: "Big Co." },
  { value: "Startups", label: "Startups" },
  { value: "Global", label: "Global" }
];

export function TabBar({
  active,
  counts,
  onChange
}: {
  active: SourceGroup;
  counts: Record<string, number>;
  onChange: (value: SourceGroup) => void;
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {tabs.map((tab) => (
        <Button
          key={tab.value}
          variant={tab.value === active ? "default" : "secondary"}
          size="sm"
          onClick={() => onChange(tab.value)}
          className={cn(
            "h-8 shrink-0 gap-2 rounded-full px-3 text-xs uppercase tracking-[0.18em]",
            tab.value !== active && "text-[var(--text-secondary)]"
          )}
        >
          {tab.label}
          <Badge className="border-transparent bg-black/20 px-2 py-0.5 text-[9px] tracking-[0.18em] text-white">
            {counts[tab.value] ?? 0}
          </Badge>
        </Button>
      ))}
    </div>
  );
}
