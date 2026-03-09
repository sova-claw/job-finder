"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
    <div className="flex flex-wrap gap-3">
      {tabs.map((tab) => (
        <Button
          key={tab.value}
          variant={tab.value === active ? "default" : "secondary"}
          size="sm"
          onClick={() => onChange(tab.value)}
          className="gap-2"
        >
          {tab.label}
          <Badge className="border-transparent bg-black/20 px-2 py-0.5 text-[10px] text-white">
            {counts[tab.value] ?? 0}
          </Badge>
        </Button>
      ))}
    </div>
  );
}
