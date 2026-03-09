"use client";

import { Activity, DollarSign, Sparkles, Target } from "lucide-react";

import { Card } from "@/components/ui/card";
import { JobStats } from "@/lib/types";

const cards = [
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
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {cards.map(({ key, label, icon: Icon }) => {
        const rawValue = stats?.[key];
        const value =
          key === "avg_score"
            ? `${rawValue ?? 0}%`
            : typeof rawValue === "number"
              ? rawValue.toLocaleString()
              : rawValue ?? "n/a";

        return (
          <Card className="p-5" key={key}>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.2em] text-[var(--text-muted)]">{label}</p>
                <p className="mt-3 text-3xl font-semibold">{value}</p>
              </div>
              <span className="rounded-full border border-white/10 bg-white/6 p-3 text-[var(--accent)]">
                <Icon size={18} />
              </span>
            </div>
          </Card>
        );
      })}
    </section>
  );
}
