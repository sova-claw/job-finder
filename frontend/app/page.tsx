"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { Search } from "lucide-react";
import { useState, useTransition } from "react";

import { DetailPanel } from "@/components/DetailPanel";
import { JobTable } from "@/components/JobTable";
import { TabBar } from "@/components/TabBar";
import { TopBar } from "@/components/TopBar";
import { UrlAnalyzer } from "@/components/UrlAnalyzer";
import { Card } from "@/components/ui/card";
import { fetchJob, fetchJobs, fetchMarketInsight, fetchProfile, fetchStats } from "@/lib/api";
import { JobDetail, SourceGroup } from "@/lib/types";

export default function Page() {
  const [sourceGroup, setSourceGroup] = useState<SourceGroup>("All");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("match_score");
  const [sortDir, setSortDir] = useState("desc");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [manualJob, setManualJob] = useState<JobDetail | null>(null);
  const [, startTransition] = useTransition();

  const statsQuery = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats
  });

  const profileQuery = useQuery({
    queryKey: ["profile"],
    queryFn: fetchProfile
  });

  const marketQuery = useQuery({
    queryKey: ["market"],
    queryFn: fetchMarketInsight
  });

  const jobsQuery = useQuery({
    queryKey: ["jobs", sourceGroup, search, sortBy, sortDir],
    queryFn: () => fetchJobs({ sourceGroup, search, sortBy, sortDir })
  });

  const detailQuery = useQuery({
    queryKey: ["job", selectedJobId],
    queryFn: () => fetchJob(selectedJobId as string),
    enabled: Boolean(selectedJobId)
  });

  const selectedJob = manualJob && manualJob.id === selectedJobId ? manualJob : detailQuery.data ?? null;
  const sourceBreakdown = statsQuery.data?.source_breakdown ?? {};
  const chartData = Object.entries(sourceBreakdown).map(([name, count]) => ({ name, count }));
  const skillData = marketQuery.data?.top_skills ?? [];
  const salaryData = marketQuery.data?.salary_distribution ?? [];

  function handleSort(field: string) {
    startTransition(() => {
      if (field === sortBy) {
        setSortDir((current) => (current === "desc" ? "asc" : "desc"));
        return;
      }
      setSortBy(field);
      setSortDir("desc");
    });
  }

  function handleAnalyzed(job: JobDetail) {
    setManualJob(job);
    setSelectedJobId(job.id);
  }

  return (
    <main className="grid-lines min-h-screen px-4 py-6 md:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <section className="flex flex-col gap-5 rounded-[36px] border border-white/10 bg-[rgba(8,16,24,0.75)] px-6 py-8 backdrop-blur md:px-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="mono text-xs uppercase tracking-[0.4em] text-[var(--accent)]">
                Career Intelligence System
              </p>
              <h1 className="mt-3 text-4xl font-semibold leading-tight md:text-6xl">
                Wake up, open one URL, know the best role to attack next.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--text-secondary)]">
                CIS aggregates AI and Python roles, scores each one against your candidate profile,
                exposes the biggest gap in weeks, and drafts a targeted letter when the role is ready.
              </p>
            </div>

            <Card className="min-w-[280px] p-5">
              <p className="text-sm uppercase tracking-[0.2em] text-[var(--text-muted)]">Candidate profile</p>
              <p className="mt-2 text-2xl font-semibold">{profileQuery.data?.name ?? "Loading..."}</p>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">{profileQuery.data?.title}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {(profileQuery.data?.strong_skills ?? []).slice(0, 5).map((skill) => (
                  <span
                    key={skill}
                    className="rounded-full border border-white/8 bg-white/6 px-3 py-1 text-xs text-[var(--text-secondary)]"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </Card>
          </div>

          <TopBar stats={statsQuery.data} />
          <UrlAnalyzer onAnalyzed={handleAnalyzed} />
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.6fr_0.7fr]">
          <div className="space-y-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <TabBar
                active={sourceGroup}
                counts={{
                  All: statsQuery.data?.total_jobs ?? 0,
                  Ukraine: sourceBreakdown.Ukraine ?? 0,
                  BigCo: sourceBreakdown.BigCo ?? 0,
                  Startups: sourceBreakdown.Startups ?? 0,
                  Global: sourceBreakdown.Global ?? 0
                }}
                onChange={setSourceGroup}
              />
              <label className="relative block w-full max-w-sm">
                <Search
                  size={16}
                  className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search company, domain, or raw text"
                  className="h-11 w-full rounded-full border border-white/10 bg-white/5 pl-11 pr-4 text-sm outline-none focus:border-[var(--accent)]"
                />
              </label>
            </div>

            <JobTable
              jobs={jobsQuery.data?.items ?? []}
              selectedId={selectedJobId}
              onSelect={setSelectedJobId}
              onSort={handleSort}
              sortBy={sortBy}
              sortDir={sortDir}
            />
          </div>

          <div className="space-y-6">
            <Card className="p-5">
              <p className="text-sm uppercase tracking-[0.2em] text-[var(--text-muted)]">Source mix</p>
              <div className="mt-4 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <XAxis dataKey="name" stroke="#6c7c91" tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 18,
                        border: "1px solid rgba(255,255,255,0.1)",
                        background: "#101926"
                      }}
                    />
                    <Bar dataKey="count" radius={[10, 10, 0, 0]} fill="var(--accent)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card className="p-5">
              <p className="text-sm uppercase tracking-[0.2em] text-[var(--text-muted)]">Market heat</p>
              <div className="mt-2 flex items-center justify-between text-sm text-[var(--text-secondary)]">
                <span>Remote ratio</span>
                <span>{marketQuery.data?.remote_ratio ?? 0}%</span>
              </div>
              <div className="mt-4 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={skillData} layout="vertical">
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" horizontal={false} />
                    <XAxis type="number" stroke="#6c7c91" tickLine={false} axisLine={false} />
                    <YAxis
                      type="category"
                      dataKey="skill"
                      width={120}
                      stroke="#6c7c91"
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 18,
                        border: "1px solid rgba(255,255,255,0.1)",
                        background: "#101926"
                      }}
                    />
                    <Bar dataKey="count" radius={[0, 10, 10, 0]} fill="var(--signal-green)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card className="p-5">
              <p className="text-sm uppercase tracking-[0.2em] text-[var(--text-muted)]">Salary bands</p>
              <div className="mt-4 h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={salaryData}>
                    <XAxis dataKey="band" stroke="#6c7c91" tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 18,
                        border: "1px solid rgba(255,255,255,0.1)",
                        background: "#101926"
                      }}
                    />
                    <Bar dataKey="count" radius={[10, 10, 0, 0]} fill="var(--signal-amber)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card className="p-5">
              <p className="text-sm uppercase tracking-[0.2em] text-[var(--text-muted)]">8-week closing plan</p>
              <div className="mt-4 space-y-3">
                {Object.entries(profileQuery.data?.learning_plan ?? {}).map(([skill, weeks]) => (
                  <div key={skill} className="rounded-2xl border border-white/8 bg-white/4 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <span>{skill}</span>
                      <span className="text-sm text-[var(--signal-amber)]">{weeks} weeks</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </section>
      </div>

      <DetailPanel job={selectedJob} onClose={() => setSelectedJobId(null)} />
    </main>
  );
}
