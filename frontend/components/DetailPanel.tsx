"use client";

import { useDeferredValue, useEffect, useState } from "react";
import { ExternalLink, X } from "lucide-react";

import { CoverLetterTab } from "@/components/CoverLetterTab";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatSalary, salaryClasses, scoreClasses, verdictMeta } from "@/lib/jobs";
import { JobDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

function RequirementList({
  items,
  emptyText
}: {
  items: string[] | null | undefined;
  emptyText: string;
}) {
  if (!items?.length) {
    return <p className="text-sm text-[var(--text-muted)]">{emptyText}</p>;
  }

  return (
    <ul className="space-y-2 text-sm text-[var(--text-secondary)]">
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="rounded-[16px] border border-white/8 bg-black/10 px-3 py-2 leading-6">
          {item}
        </li>
      ))}
    </ul>
  );
}

function DetailStat({
  label,
  value,
  valueClass,
  pillClass
}: {
  label: string;
  value: string;
  valueClass?: string;
  pillClass?: string;
}) {
  return (
    <div className="rounded-[18px] border border-white/8 bg-black/10 px-3 py-3">
      <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">{label}</p>
      {pillClass ? (
        <span className={cn("mt-2 inline-flex rounded-full border px-2.5 py-1 text-xs font-medium", pillClass)}>
          {value}
        </span>
      ) : (
        <p className={cn("mt-1 text-sm font-medium text-white", valueClass)}>{value}</p>
      )}
    </div>
  );
}

function EmptyInspector() {
  return (
    <aside className="hidden xl:block">
      <div className="sticky top-6">
        <Card className="rounded-[24px] border-white/10 bg-[var(--card-strong)]/95 p-5">
          <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--text-muted)]">Inspector</p>
          <h2 className="mt-3 text-xl font-semibold text-white">Select a role</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
            Keep the table in view, open roles in the right rail, and generate letters only for the jobs worth attacking now.
          </p>
        </Card>
      </div>
    </aside>
  );
}

export function DetailPanel({
  job,
  onClose
}: {
  job: JobDetail | null;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"details" | "cover-letter">("details");
  const deferredJob = useDeferredValue(job);

  useEffect(() => {
    setTab("details");
  }, [deferredJob?.id]);

  if (!deferredJob) {
    return <EmptyInspector />;
  }

  const verdict = verdictMeta(deferredJob.verdict);
  const score = scoreClasses(deferredJob.match_score);
  const shell = (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--text-muted)]">
              {deferredJob.source_group}
            </p>
            <Badge className={verdict.badge}>{verdict.label}</Badge>
          </div>
          <h2 className="mt-2 text-2xl font-semibold text-white">{deferredJob.title}</h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{deferredJob.company ?? "Unknown company"}</p>
        </div>
        <div className="flex gap-2 xl:hidden">
          <Button variant="ghost" size="sm" onClick={onClose} className="h-8 px-3">
            <X size={14} />
          </Button>
        </div>
      </div>

      <div className={cn("mt-4 rounded-[22px] border px-4 py-4", verdict.tone)}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Verdict</p>
            <p className="mt-2 text-lg font-semibold text-white">{verdict.label}</p>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {deferredJob.top_gap
                ? `Biggest blocker right now: ${deferredJob.top_gap}.`
                : "No major blocker identified in the current gap set."}
            </p>
          </div>
          <Badge className={score.pill}>{deferredJob.match_score ?? 0}% match</Badge>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          variant={tab === "details" ? "default" : "secondary"}
          onClick={() => setTab("details")}
          size="sm"
          className="h-8 px-3 text-xs uppercase tracking-[0.16em]"
        >
          Details
        </Button>
        <Button
          variant={tab === "cover-letter" ? "default" : "secondary"}
          onClick={() => setTab("cover-letter")}
          size="sm"
          className="h-8 px-3 text-xs uppercase tracking-[0.16em]"
        >
          Cover letter
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto hidden h-8 px-3 text-xs uppercase tracking-[0.16em] xl:inline-flex"
          onClick={onClose}
        >
          Clear
        </Button>
      </div>

      {tab === "details" ? (
        <div className="mt-4 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <DetailStat label="Salary" value={formatSalary(deferredJob)} pillClass={salaryClasses(deferredJob)} />
            <DetailStat label="Source" value={`${deferredJob.source_group} · ${deferredJob.source}`} />
            <DetailStat label="Location" value={deferredJob.location ?? (deferredJob.remote ? "Remote" : "n/a")} />
            <DetailStat label="Company type" value={deferredJob.company_type ?? "n/a"} />
          </div>

          <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Top gaps</p>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">What blocks an immediate application.</p>
              </div>
              <Button className="h-8 gap-2 px-3 text-xs uppercase tracking-[0.16em]" size="sm" onClick={() => window.open(deferredJob.url, "_blank") }>
                <ExternalLink size={13} />
                Open job page
              </Button>
            </div>
            <div className="mt-4 space-y-3">
              {(deferredJob.gaps ?? []).length ? (
                deferredJob.gaps?.map((gap) => (
                  <div key={gap.skill} className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium text-white">{gap.skill}</span>
                      <span className="text-xs uppercase tracking-[0.16em] text-[var(--signal-amber)]">
                        {gap.weeks_to_close}w to close
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 rounded-full bg-white/8">
                      <div
                        className="h-1.5 rounded-full bg-[var(--signal-amber)]"
                        style={{ width: `${gap.current}%` }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-[var(--text-muted)]">No gap analysis available yet.</p>
              )}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
              <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Must-have requirements</p>
              <div className="mt-3">
                <RequirementList items={deferredJob.requirements_must} emptyText="No must-have requirements extracted." />
              </div>
            </div>
            <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
              <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Nice-to-have</p>
              <div className="mt-3">
                <RequirementList items={deferredJob.requirements_nice} emptyText="No nice-to-have requirements extracted." />
              </div>
            </div>
          </div>

          <details className="rounded-[20px] border border-white/8 bg-black/10 p-4">
            <summary className="cursor-pointer list-none text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">
              Original text
            </summary>
            <p className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-sm leading-6 text-[var(--text-secondary)]">
              {deferredJob.raw_text ?? "No source text captured."}
            </p>
          </details>
        </div>
      ) : (
        <div className="mt-4">
          <CoverLetterTab job={deferredJob} compact />
        </div>
      )}
    </>
  );

  return (
    <>
      <aside className="hidden xl:block">
        <div className="sticky top-6">
          <Card className="rounded-[24px] border-white/10 bg-[var(--card-strong)]/95 p-5">{shell}</Card>
        </div>
      </aside>

      <div className="fixed inset-x-3 bottom-3 z-30 xl:hidden">
        <Card className="max-h-[82vh] overflow-hidden rounded-[24px] border-white/15 bg-[var(--card-strong)]/98 p-4">
          <div className="max-h-[calc(82vh-2rem)] overflow-auto pr-1">{shell}</div>
        </Card>
      </div>
    </>
  );
}
