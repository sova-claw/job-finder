"use client";

import { useDeferredValue } from "react";
import { ExternalLink } from "lucide-react";

import { CoverLetterTab } from "@/components/CoverLetterTab";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

function InspectorBody({ job, onClear }: { job: JobDetail; onClear: () => void }) {
  const verdict = verdictMeta(job.verdict);
  const score = scoreClasses(job.match_score);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 px-5 pt-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--text-muted)]">{job.source_group}</p>
            <Badge className={verdict.badge}>{verdict.label}</Badge>
          </div>
          <h2 className="mt-2 text-2xl font-semibold text-white">{job.title}</h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{job.company ?? "Unknown company"}</p>
        </div>
        <Button variant="ghost" size="sm" className="hidden xl:inline-flex" onClick={onClear}>
          Clear
        </Button>
      </div>

      <div className={cn("mx-5 mt-4 rounded-[22px] border px-4 py-4", verdict.tone)}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Verdict</p>
            <p className="mt-2 text-lg font-semibold text-white">{verdict.label}</p>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {job.top_gap ? `Biggest blocker right now: ${job.top_gap}.` : "No major blocker identified in the current gap set."}
            </p>
          </div>
          <Badge className={score.pill}>{job.match_score ?? 0}% match</Badge>
        </div>
      </div>

      <div className="px-5 pb-5 pt-4">
        <Tabs defaultValue="details" className="gap-4">
          <TabsList className="rounded-full border border-white/8 bg-black/10 p-1">
            <TabsTrigger
              value="details"
              className="rounded-full px-3 text-xs uppercase tracking-[0.16em] data-[state=active]:bg-[var(--accent)] data-[state=active]:text-white"
            >
              Details
            </TabsTrigger>
            <TabsTrigger
              value="cover-letter"
              className="rounded-full px-3 text-xs uppercase tracking-[0.16em] data-[state=active]:bg-[var(--accent)] data-[state=active]:text-white"
            >
              Cover letter
            </TabsTrigger>
          </TabsList>

          <TabsContent value="details" className="m-0">
            <ScrollArea className="h-[min(70vh,760px)] pr-4 xl:h-[calc(100vh-15rem)]">
              <div className="space-y-4 pb-1">
                <div className="grid gap-3 sm:grid-cols-2">
                  <DetailStat label="Salary" value={formatSalary(job)} pillClass={salaryClasses(job)} />
                  <DetailStat label="Source" value={`${job.source_group} · ${job.source}`} />
                  <DetailStat label="Location" value={job.location ?? (job.remote ? "Remote" : "n/a")} />
                  <DetailStat label="Company type" value={job.company_type ?? "n/a"} />
                </div>

                <Separator className="bg-white/8" />

                <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Top gaps</p>
                      <p className="mt-1 text-sm text-[var(--text-secondary)]">What blocks an immediate application.</p>
                    </div>
                    <Button className="gap-2" size="sm" onClick={() => window.open(job.url, "_blank") }>
                      <ExternalLink size={13} />
                      Open job page
                    </Button>
                  </div>
                  <div className="mt-4 space-y-3">
                    {(job.gaps ?? []).length ? (
                      job.gaps?.map((gap) => (
                        <div key={gap.skill} className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-sm font-medium text-white">{gap.skill}</span>
                            <span className="text-xs uppercase tracking-[0.16em] text-[var(--signal-amber)]">
                              {gap.weeks_to_close}w to close
                            </span>
                          </div>
                          <div className="mt-2 h-1.5 rounded-full bg-white/8">
                            <div className="h-1.5 rounded-full bg-[var(--signal-amber)]" style={{ width: `${gap.current}%` }} />
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
                      <RequirementList items={job.requirements_must} emptyText="No must-have requirements extracted." />
                    </div>
                  </div>
                  <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
                    <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Nice-to-have</p>
                    <div className="mt-3">
                      <RequirementList items={job.requirements_nice} emptyText="No nice-to-have requirements extracted." />
                    </div>
                  </div>
                </div>

                <Collapsible>
                  <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
                    <CollapsibleTrigger asChild>
                      <button type="button" className="flex w-full items-center justify-between text-left">
                        <span className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Original text</span>
                        <span className="text-xs text-[var(--text-muted)]">Expand</span>
                      </button>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="pt-3">
                      <p className="max-h-56 overflow-auto whitespace-pre-wrap text-sm leading-6 text-[var(--text-secondary)]">
                        {job.raw_text ?? "No source text captured."}
                      </p>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="cover-letter" className="m-0">
            <ScrollArea className="h-[min(70vh,760px)] pr-4 xl:h-[calc(100vh-15rem)]">
              <CoverLetterTab job={job} compact />
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export function DetailPanel({
  job,
  onClose
}: {
  job: JobDetail | null;
  onClose: () => void;
}) {
  const deferredJob = useDeferredValue(job);

  if (!deferredJob) {
    return <EmptyInspector />;
  }

  return (
    <>
      <aside className="hidden xl:block">
        <div className="sticky top-6">
          <Card className="overflow-hidden rounded-[24px] border-white/10 bg-[var(--card-strong)]/95">
            <InspectorBody job={deferredJob} onClear={onClose} />
          </Card>
        </div>
      </aside>

      <div className="xl:hidden">
        <Sheet open={Boolean(deferredJob)} onOpenChange={(open) => !open && onClose()}>
          <SheetContent
            side="bottom"
            showCloseButton
            className="h-auto max-h-[82vh] rounded-t-[28px] border-white/15 bg-[var(--card-strong)]/98 p-0 text-[var(--text-primary)] sm:max-w-none"
          >
            <SheetHeader className="sr-only">
              <SheetTitle>{deferredJob.title}</SheetTitle>
              <SheetDescription>{deferredJob.company ?? "Selected job details"}</SheetDescription>
            </SheetHeader>
            <InspectorBody job={deferredJob} onClear={onClose} />
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
