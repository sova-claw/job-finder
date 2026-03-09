"use client";

import { ArrowUpDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { JobSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

function formatSalary(job: JobSummary) {
  if (!job.salary_min && !job.salary_max) {
    return "n/a";
  }
  if (job.salary_min && job.salary_max) {
    return `$${job.salary_min.toLocaleString()} - $${job.salary_max.toLocaleString()}`;
  }
  return `$${(job.salary_max ?? job.salary_min ?? 0).toLocaleString()}`;
}

function scoreColor(score: number | null) {
  if (score === null) {
    return "bg-white/15";
  }
  if (score >= 70) {
    return "bg-[var(--signal-green)]";
  }
  if (score >= 40) {
    return "bg-[var(--signal-amber)]";
  }
  return "bg-[var(--signal-red)]";
}

export function JobTable({
  jobs,
  selectedId,
  onSelect,
  onSort,
  sortBy,
  sortDir
}: {
  jobs: JobSummary[];
  selectedId: string | null;
  onSelect: (jobId: string) => void;
  onSort: (field: string) => void;
  sortBy: string;
  sortDir: string;
}) {
  const columns = [
    { key: "company", label: "Company" },
    { key: "match_score", label: "Match" },
    { key: "salary_max", label: "Salary" },
    { key: "posted_at", label: "Posted" }
  ];

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-white/10 bg-white/4">
            <tr>
              <th className="px-6 py-4 font-medium text-[var(--text-muted)]">Role</th>
              {columns.map((column) => (
                <th key={column.key} className="px-4 py-4 font-medium text-[var(--text-muted)]">
                  <button
                    className="inline-flex items-center gap-2"
                    onClick={() => onSort(column.key)}
                    type="button"
                  >
                    {column.label}
                    <ArrowUpDown
                      size={14}
                      className={cn(
                        sortBy === column.key ? "text-white" : "text-[var(--text-muted)]",
                        sortBy === column.key && sortDir === "asc" ? "rotate-180" : ""
                      )}
                    />
                  </button>
                </th>
              ))}
              <th className="px-4 py-4 font-medium text-[var(--text-muted)]">Tags</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job, index) => (
              <tr
                key={job.id}
                onClick={() => onSelect(job.id)}
                className={cn(
                  "cursor-pointer border-b border-white/6 transition hover:bg-white/6",
                  index % 2 === 0 ? "bg-white/[0.02]" : "bg-transparent",
                  selectedId === job.id ? "bg-[rgba(47,140,255,0.12)]" : ""
                )}
              >
                <td className="px-6 py-4">
                  <div className="flex items-start gap-3">
                    <div>
                      <p className="font-medium text-white">{job.title ?? "Untitled role"}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        {job.source_group}
                      </p>
                    </div>
                    {job.posted_at &&
                    new Date(job.posted_at).getTime() > Date.now() - 24 * 60 * 60 * 1000 ? (
                      <Badge className="border-[var(--signal-green)]/40 bg-[var(--signal-green)]/15 text-[var(--signal-green)]">
                        New
                      </Badge>
                    ) : null}
                  </div>
                </td>
                <td className="px-4 py-4 text-[var(--text-secondary)]">{job.company ?? "n/a"}</td>
                <td className="px-4 py-4">
                  <div className="flex items-center gap-3">
                    <span className="w-10 text-sm font-semibold">{job.match_score ?? 0}%</span>
                    <div className="h-2 w-24 rounded-full bg-white/10">
                      <div
                        className={cn("h-2 rounded-full", scoreColor(job.match_score))}
                        style={{ width: `${job.match_score ?? 0}%` }}
                      />
                    </div>
                  </div>
                </td>
                <td className="px-4 py-4 text-[var(--text-secondary)]">{formatSalary(job)}</td>
                <td className="px-4 py-4 text-[var(--text-secondary)]">
                  {job.posted_at ? new Date(job.posted_at).toLocaleDateString() : "n/a"}
                </td>
                <td className="px-4 py-4">
                  <div className="flex flex-wrap gap-2">
                    {(job.tags ?? []).slice(0, 3).map((tag) => (
                      <Badge key={tag}>{tag}</Badge>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
