"use client";

import { ArrowUpDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { formatAge, formatSalary, isFreshJob, salaryClasses, scoreClasses, verdictMeta } from "@/lib/jobs";
import { JobSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

export function JobTable({
  jobs,
  selectedId,
  onSelect,
  onSort,
  sortBy,
  sortDir,
  isLoading = false
}: {
  jobs: JobSummary[];
  selectedId: string | null;
  onSelect: (jobId: string) => void;
  onSort: (field: string) => void;
  sortBy: string;
  sortDir: string;
  isLoading?: boolean;
}) {
  const emptyMessage = isLoading ? "Loading jobs..." : "No roles match the current filters.";

  return (
    <Card className="overflow-hidden rounded-[24px]">
      <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--text-muted)]">Jobs</p>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">Dense triage view optimized for scanning.</p>
        </div>
        <span className="mono text-xs text-[var(--text-muted)]">{jobs.length} visible</span>
      </div>

      {!jobs.length ? (
        <div className="px-4 py-10 text-center text-sm text-[var(--text-secondary)]">{emptyMessage}</div>
      ) : (
        <>
          <div className="space-y-2 p-3 md:hidden">
            {jobs.map((job) => {
              const score = scoreClasses(job.match_score);
              const verdict = verdictMeta(job.verdict);

              return (
                <button
                  key={job.id}
                  type="button"
                  onClick={() => onSelect(job.id)}
                  className={cn(
                    "w-full rounded-[20px] border border-white/8 bg-black/10 p-4 text-left transition",
                    selectedId === job.id && "border-[var(--accent)]/35 bg-[var(--accent)]/10"
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate font-semibold text-white">{job.title ?? "Untitled role"}</p>
                        {isFreshJob(job.posted_at) ? (
                          <Badge className="border-[var(--accent)]/35 bg-[var(--accent)]/14 text-[var(--accent)]">
                            New
                          </Badge>
                        ) : null}
                      </div>
                      <p className="mt-1 text-sm text-[var(--text-secondary)]">{job.company ?? "Unknown company"}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--text-muted)]">
                        {job.source_group}
                        {job.remote ? " • Remote" : ""}
                      </p>
                    </div>
                    <Badge className={score.pill}>{job.match_score ?? 0}%</Badge>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Top gap</p>
                      <p className="mt-1 text-sm text-white">{job.top_gap ?? "No major gap"}</p>
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Salary</p>
                      <span className={cn("mt-1 inline-flex rounded-full border px-2.5 py-1 text-xs font-medium", salaryClasses(job))}>
                        {formatSalary(job)}
                      </span>
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Age</p>
                      <p className="mt-1 text-sm text-white">{formatAge(job.posted_at)}</p>
                    </div>
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Verdict</p>
                      <Badge className={verdict.badge}>{verdict.label}</Badge>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          <div className="hidden overflow-x-auto md:block">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-white/8 bg-white/4">
                <tr>
                  <th className="px-4 py-3 font-medium text-[var(--text-muted)]">Role / company</th>
                  <th className="px-3 py-3 font-medium text-[var(--text-muted)]">
                    <button className="inline-flex items-center gap-2" onClick={() => onSort("match_score")} type="button">
                      Match
                      <ArrowUpDown
                        size={13}
                        className={cn(
                          sortBy === "match_score" ? "text-white" : "text-[var(--text-muted)]",
                          sortBy === "match_score" && sortDir === "asc" && "rotate-180"
                        )}
                      />
                    </button>
                  </th>
                  <th className="px-3 py-3 font-medium text-[var(--text-muted)]">Top gap</th>
                  <th className="px-3 py-3 font-medium text-[var(--text-muted)]">
                    <button className="inline-flex items-center gap-2" onClick={() => onSort("salary_max")} type="button">
                      Salary
                      <ArrowUpDown
                        size={13}
                        className={cn(
                          sortBy === "salary_max" ? "text-white" : "text-[var(--text-muted)]",
                          sortBy === "salary_max" && sortDir === "asc" && "rotate-180"
                        )}
                      />
                    </button>
                  </th>
                  <th className="px-3 py-3 font-medium text-[var(--text-muted)]">
                    <button className="inline-flex items-center gap-2" onClick={() => onSort("posted_at")} type="button">
                      Age
                      <ArrowUpDown
                        size={13}
                        className={cn(
                          sortBy === "posted_at" ? "text-white" : "text-[var(--text-muted)]",
                          sortBy === "posted_at" && sortDir === "asc" && "rotate-180"
                        )}
                      />
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job, index) => {
                  const score = scoreClasses(job.match_score);

                  return (
                    <tr
                      key={job.id}
                      onClick={() => onSelect(job.id)}
                      className={cn(
                        "cursor-pointer border-b border-white/6 transition hover:bg-white/5",
                        index % 2 === 0 ? "bg-white/[0.02]" : "bg-transparent",
                        selectedId === job.id && "bg-[rgba(47,140,255,0.12)]"
                      )}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-start gap-3">
                          <div className={cn("mt-0.5 h-10 w-1 rounded-full", score.fill)} />
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-white">{job.title ?? "Untitled role"}</p>
                              {isFreshJob(job.posted_at) ? (
                                <Badge className="border-[var(--accent)]/35 bg-[var(--accent)]/14 text-[var(--accent)]">
                                  New
                                </Badge>
                              ) : null}
                            </div>
                            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[var(--text-muted)]">
                              <span className="text-[var(--text-secondary)]">{job.company ?? "Unknown company"}</span>
                              <span>•</span>
                              <span>{job.source_group}</span>
                              {job.company_type ? (
                                <>
                                  <span>•</span>
                                  <span>{job.company_type}</span>
                                </>
                              ) : null}
                              {job.remote ? (
                                <>
                                  <span>•</span>
                                  <span>Remote</span>
                                </>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="w-24">
                          <div className="flex items-center justify-between gap-2">
                            <span className={cn("text-sm font-semibold", score.text)}>{job.match_score ?? 0}%</span>
                          </div>
                          <div className="mt-2 h-1.5 rounded-full bg-white/10">
                            <div
                              className={cn("h-1.5 rounded-full", score.fill)}
                              style={{ width: `${job.match_score ?? 0}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-sm text-[var(--text-secondary)]">
                        <span className="text-white">{job.top_gap ?? "No major gap"}</span>
                      </td>
                      <td className="px-3 py-3">
                        <span className={cn("inline-flex rounded-full border px-2.5 py-1 text-xs font-medium", salaryClasses(job))}>
                          {formatSalary(job)}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-sm text-[var(--text-secondary)]">{formatAge(job.posted_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
