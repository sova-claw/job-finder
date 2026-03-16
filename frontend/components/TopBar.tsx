"use client";

import { Activity, DollarSign, Sparkles, Target } from "lucide-react";

import { Card } from "@/components/ui/card";
import { JobStats } from "@/lib/types";

const metrics = [
  {
    key: "total_jobs",
    label: "Tracked roles",
    icon: Activity
  },
  {
    key: "avg_score",
    label: "Average match",
    icon: Target
  },
  {
    key: "high_pay_count",
    label: "High-pay roles",
    icon: DollarSign
  },
  {
    key: "top_gap",
    label: "Top gap",
    icon: Sparkles
  }
] as const;

export function TopBar({ stats }: { stats?: JobStats }) {
  return (
    <Card className="rounded-[22px] px-3 py-3 md:px-4">
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map(({ key, label, icon: Icon }) => {
          const rawValue = stats?.[key];
          const value =
            key === "avg_score"
              ? `${rawValue ?? 0}%`
              : typeof rawValue === "number"
                ? rawValue.toLocaleString()
                : rawValue ?? "n/a";

          return (
            <div
              key={key}
              className="flex items-center gap-3 rounded-[18px] border border-white/8 bg-black/10 px-3 py-3"
            >
              <span className="rounded-full border border-white/10 bg-white/6 p-2 text-[var(--accent)]">
                <Icon size={14} />
              </span>
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--text-muted)]">
                  {label}
                </p>
                <p className="mt-1 truncate text-lg font-semibold text-white">{value}</p>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
