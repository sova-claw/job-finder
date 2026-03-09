"use client";

import { useDeferredValue, useState } from "react";
import { ExternalLink } from "lucide-react";

import { CoverLetterTab } from "@/components/CoverLetterTab";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { JobDetail } from "@/lib/types";

export function DetailPanel({
  job,
  onClose
}: {
  job: JobDetail | null;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"details" | "cover-letter">("details");
  const deferredJob = useDeferredValue(job);

  if (!deferredJob) {
    return null;
  }

  return (
    <div className="fixed inset-x-4 bottom-4 z-30 mx-auto max-w-7xl">
      <Card className="border-white/15 bg-[var(--card-strong)]/98 p-6">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">
              {deferredJob.source_group}
            </p>
            <h2 className="mt-2 text-2xl font-semibold">{deferredJob.title}</h2>
            <p className="mt-1 text-[var(--text-secondary)]">{deferredJob.company}</p>
          </div>
          <div className="flex gap-2">
            <Button variant={tab === "details" ? "default" : "secondary"} onClick={() => setTab("details")}>
              Job details
            </Button>
            <Button
              variant={tab === "cover-letter" ? "default" : "secondary"}
              onClick={() => setTab("cover-letter")}
            >
              Cover letter
            </Button>
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>

        {tab === "details" ? (
          <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-5">
              <div>
                <p className="text-sm uppercase tracking-[0.16em] text-[var(--text-muted)]">Must-have requirements</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(deferredJob.requirements_must ?? []).map((item) => (
                    <Badge key={item}>{item}</Badge>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-sm uppercase tracking-[0.16em] text-[var(--text-muted)]">Nice-to-have</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(deferredJob.requirements_nice ?? []).map((item) => (
                    <Badge key={item}>{item}</Badge>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-sm uppercase tracking-[0.16em] text-[var(--text-muted)]">Original text</p>
                <p className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap rounded-[24px] border border-white/8 bg-black/15 p-4 text-sm leading-7 text-[var(--text-secondary)]">
                  {deferredJob.raw_text}
                </p>
              </div>
            </div>

            <div className="space-y-5">
              <div className="rounded-[24px] border border-white/10 bg-black/15 p-5">
                <p className="text-sm uppercase tracking-[0.16em] text-[var(--text-muted)]">Gap analysis</p>
                <div className="mt-4 space-y-3">
                  {(deferredJob.gaps ?? []).map((gap) => (
                    <div key={gap.skill} className="rounded-2xl border border-white/8 bg-white/4 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <span>{gap.skill}</span>
                        <span className="text-sm text-[var(--signal-amber)]">
                          {gap.weeks_to_close}w to close
                        </span>
                      </div>
                      <div className="mt-3 h-2 rounded-full bg-white/8">
                        <div
                          className="h-2 rounded-full bg-[var(--signal-amber)]"
                          style={{ width: `${gap.current}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <Button className="w-full gap-2" onClick={() => window.open(deferredJob.url, "_blank")}>
                <ExternalLink size={14} />
                Open source job page
              </Button>
            </div>
          </div>
        ) : (
          <CoverLetterTab job={deferredJob} />
        )}
      </Card>
    </div>
  );
}
