"use client";

import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, KanbanSquare, Network, Workflow } from "lucide-react";

import { fetchStrategy } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const ICONS = {
  Airtable: Network,
  Linear: KanbanSquare,
  CIS: BrainCircuit
} as const;

export function StrategyPanel() {
  const strategyQuery = useQuery({
    queryKey: ["strategy"],
    queryFn: fetchStrategy
  });

  const strategy = strategyQuery.data;

  return (
    <Card className="rounded-[24px] p-4 md:p-5">
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="border-[var(--accent)]/30 bg-[var(--accent)]/12 text-[var(--accent)]">
                Strategy
              </Badge>
              <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
                Dual track
              </Badge>
            </div>
            <h2 className="mt-3 text-xl font-semibold text-white">Operating model</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
              Airtable tracks the career search. Linear tracks implementation. CIS stays the
              intelligence layer that ranks openings, companies, and next actions.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(strategy?.metrics ?? []).map((metric) => (
              <div key={metric.label} className="rounded-[18px] border border-white/8 bg-black/10 px-3 py-3">
                <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  {metric.label}
                </p>
                <p className="mt-2 text-lg font-semibold text-white">{metric.value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <div className="grid gap-4 lg:grid-cols-2">
            {(strategy?.tracks ?? []).map((track) => (
              <div key={track.id} className="rounded-[20px] border border-white/8 bg-black/10 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-white">{track.name}</p>
                  <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
                    {track.horizon}
                  </Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{track.goal}</p>
                <div className="mt-4 rounded-[16px] border border-white/8 bg-white/[0.03] px-3 py-3">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                    Current focus
                  </p>
                  <p className="mt-2 text-sm text-white">{track.current_focus}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="space-y-4">
            <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
              <div className="flex items-center gap-2">
                <Workflow size={15} className="text-[var(--accent)]" />
                <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  Tool responsibilities
                </p>
              </div>
              <div className="mt-4 space-y-3">
                {(strategy?.tools ?? []).map((tool) => {
                  const Icon = ICONS[tool.tool as keyof typeof ICONS] ?? Workflow;
                  return (
                    <div key={tool.tool} className="rounded-[16px] border border-white/8 bg-white/[0.03] px-3 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <Icon size={14} className="text-[var(--accent)]" />
                          <span className="text-sm font-medium text-white">{tool.tool}</span>
                        </div>
                        <Badge className="border-white/10 bg-black/20 text-[var(--text-secondary)]">
                          {tool.role}
                        </Badge>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {tool.owns.map((item) => (
                          <Badge key={`${tool.tool}-${item}`}>{item}</Badge>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
                <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  Linear project
                </p>
                <p className="mt-2 text-lg font-semibold text-white">{strategy?.linear_project ?? "CIS v2"}</p>
                <div className="mt-4 space-y-2">
                  {(strategy?.linear_epics ?? []).map((epic) => (
                    <div
                      key={epic}
                      className="rounded-[14px] border border-white/8 bg-white/[0.03] px-3 py-2 text-sm text-[var(--text-secondary)]"
                    >
                      {epic}
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
                <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  Weekly loop
                </p>
                <ol className="mt-4 space-y-3">
                  {(strategy?.weekly_loop ?? []).map((step, index) => (
                    <li key={step} className="flex gap-3 text-sm leading-6 text-[var(--text-secondary)]">
                      <span className="mono mt-0.5 text-[var(--accent)]">{index + 1}</span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
