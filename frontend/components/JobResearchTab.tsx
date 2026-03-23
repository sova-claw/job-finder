"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FlaskConical, Plus } from "lucide-react";

import { createJobResearch, fetchJobResearch } from "@/lib/api";
import { JobDetail } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";

export function JobResearchTab({ job }: { job: JobDetail }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [findingType, setFindingType] = useState("company_signal");
  const [confidence, setConfidence] = useState("75");
  const [sourceUrl, setSourceUrl] = useState("");
  const [tags, setTags] = useState("");

  const researchQuery = useQuery({
    queryKey: ["job-research", job.id],
    queryFn: () => fetchJobResearch(job.id)
  });

  const findings = researchQuery.data?.items ?? [];
  const sourceDomains = useMemo(() => {
    const values = findings.flatMap((item) => item.evidence?.map((entry) => entry.source_domain).filter(Boolean) ?? []);
    return Array.from(new Set(values));
  }, [findings]);

  const createMutation = useMutation({
    mutationFn: () =>
      createJobResearch(job.id, {
        title,
        summary,
        finding_type: findingType,
        confidence: confidence ? Number(confidence) : null,
        tags: tags
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        source_url: sourceUrl || null
      }),
    onSuccess: async () => {
      setTitle("");
      setSummary("");
      setSourceUrl("");
      setTags("");
      await queryClient.invalidateQueries({ queryKey: ["job-research", job.id] });
    }
  });

  return (
    <ScrollArea className="h-[min(70vh,760px)] pr-4 xl:h-[calc(100vh-15rem)]">
      <div className="space-y-4 pb-1">
        <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Research layer</p>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                Store evidence-backed findings for this role and its company. This becomes reusable project memory instead of Slack-only notes.
              </p>
            </div>
            <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">{findings.length} findings</Badge>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Company</p>
              <p className="mt-2 text-sm font-medium text-white">{job.company ?? "Unknown"}</p>
            </div>
            <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Role fit</p>
              <p className="mt-2 text-sm font-medium text-white">{job.match_score ?? 0}% match</p>
            </div>
            <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Sources</p>
              <p className="mt-2 text-sm font-medium text-white">{sourceDomains.join(", ") || "No evidence yet"}</p>
            </div>
            <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Use case</p>
              <p className="mt-2 text-sm font-medium text-white">Recruiters, company intel, salary signals</p>
            </div>
          </div>
        </div>

        <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
          <div className="flex items-center gap-2">
            <FlaskConical size={15} className="text-[var(--accent)]" />
            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Add finding</p>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Short finding title" />
            <Input value={findingType} onChange={(event) => setFindingType(event.target.value)} placeholder="finding type" />
            <Input value={confidence} onChange={(event) => setConfidence(event.target.value)} placeholder="confidence 0-100" />
            <Input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="source URL" />
          </div>
          <Input
            value={tags}
            onChange={(event) => setTags(event.target.value)}
            placeholder="tags, comma-separated"
            className="mt-3"
          />
          <Textarea
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            placeholder="What matters here? recruiter lead, company signal, salary clue, hiring pattern, or a risk."
            className="mt-3"
          />
          <div className="mt-3 flex justify-end">
            <Button
              size="sm"
              className="gap-2"
              disabled={!title.trim() || !summary.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              <Plus size={13} />
              {createMutation.isPending ? "Saving" : "Save finding"}
            </Button>
          </div>
          {createMutation.isError ? (
            <p className="mt-3 text-sm text-[var(--signal-red)]">
              {createMutation.error instanceof Error ? createMutation.error.message : "Failed to save finding"}
            </p>
          ) : null}
        </div>

        <div className="space-y-3">
          {findings.length ? (
            findings.map((finding) => (
              <div key={finding.id} className="rounded-[20px] border border-white/8 bg-black/10 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-white">{finding.title}</p>
                      <Badge>{finding.finding_type}</Badge>
                      {typeof finding.confidence === "number" ? (
                        <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">{finding.confidence}%</Badge>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{finding.summary}</p>
                  </div>
                  <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">{finding.created_by ?? "manual"}</Badge>
                </div>
                {finding.tags?.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {finding.tags.map((tag) => (
                      <Badge key={tag} className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                ) : null}
                {finding.evidence?.length ? (
                  <div className="mt-4 space-y-2">
                    {finding.evidence.map((entry) => (
                      <a
                        key={entry.url}
                        href={entry.url}
                        rel="noreferrer"
                        target="_blank"
                        className="flex items-center justify-between rounded-[16px] border border-white/8 bg-white/[0.03] px-3 py-3 text-left transition hover:bg-white/[0.05]"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-white">{entry.title ?? entry.url}</p>
                          <p className="mt-1 truncate text-xs uppercase tracking-[0.16em] text-[var(--text-muted)]">
                            {entry.source_domain ?? "source"}
                          </p>
                        </div>
                        <ExternalLink size={13} className="text-[var(--text-muted)]" />
                      </a>
                    ))}
                  </div>
                ) : null}
              </div>
            ))
          ) : (
            <div className="rounded-[20px] border border-white/8 bg-black/10 p-4 text-sm text-[var(--text-secondary)]">
              No research saved for this role yet. Add recruiter leads, salary signals, company intelligence, or forum summaries here.
            </div>
          )}
        </div>
      </div>
    </ScrollArea>
  );
}
