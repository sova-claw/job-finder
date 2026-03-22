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
import {
  BrainCircuit,
  ChevronDown,
  ChevronUp,
  Radar,
  Search,
  Sparkles,
  Target
} from "lucide-react";
import { useMemo, useState, useTransition } from "react";

import { CompaniesPanel } from "@/components/CompaniesPanel";
import { DetailPanel } from "@/components/DetailPanel";
import { JobTable } from "@/components/JobTable";
import { StrategyPanel } from "@/components/StrategyPanel";
import { TabBar } from "@/components/TabBar";
import { TopBar } from "@/components/TopBar";
import { UrlAnalyzer } from "@/components/UrlAnalyzer";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { fetchJob, fetchJobs, fetchMarketInsight, fetchProfile, fetchStats } from "@/lib/api";
import { isHighPay } from "@/lib/jobs";
import { JobDetail, SourceGroup } from "@/lib/types";

const TOOLTIP_STYLE = {
  borderRadius: 18,
  border: "1px solid rgba(255,255,255,0.1)",
  background: "#101926"
};

type QuickFilter = "all" | "ready" | "remote" | "high_pay";

export default function Page() {
  const [sourceGroup, setSourceGroup] = useState<SourceGroup>("All");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("match_score");
  const [sortDir, setSortDir] = useState("desc");
  const [quickFilter, setQuickFilter] = useState<QuickFilter>("all");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [manualJob, setManualJob] = useState<JobDetail | null>(null);
  const [isMarketOpen, setIsMarketOpen] = useState(false);
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

  const jobs = jobsQuery.data?.items ?? [];
  const selectedJob = manualJob && manualJob.id === selectedJobId ? manualJob : detailQuery.data ?? null;
  const sourceBreakdown = statsQuery.data?.source_breakdown ?? {};
  const chartData = Object.entries(sourceBreakdown).map(([name, count]) => ({ name, count }));
  const skillData = marketQuery.data?.top_skills ?? [];
  const salaryData = marketQuery.data?.salary_distribution ?? [];

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      if (quickFilter === "ready") {
        return job.verdict === "apply_now";
      }
      if (quickFilter === "remote") {
        return Boolean(job.remote);
      }
      if (quickFilter === "high_pay") {
        return isHighPay(job);
      }
      return true;
    });
  }, [jobs, quickFilter]);

  const filterCounts = useMemo(() => {
    return {
      all: jobs.length,
      ready: jobs.filter((job) => job.verdict === "apply_now").length,
      remote: jobs.filter((job) => job.remote).length,
      high_pay: jobs.filter((job) => isHighPay(job)).length
    };
  }, [jobs]);

  const dominantSource = useMemo(() => {
    const entries = Object.entries(sourceBreakdown).sort((left, right) => right[1] - left[1]);
    return entries[0]?.[0] ?? "n/a";
  }, [sourceBreakdown]);

  const topMarketSkill = skillData[0]?.skill ?? "n/a";
  const learningFocus = Object.entries(profileQuery.data?.learning_plan ?? {}).slice(0, 4);
  const strongSkills = (profileQuery.data?.strong_skills ?? []).slice(0, 5);
  const quickFilters: { value: QuickFilter; label: string; count: number; helper: string }[] = [
    { value: "all", label: "All roles", count: filterCounts.all, helper: "Full queue" },
    { value: "ready", label: "Ready now", count: filterCounts.ready, helper: "70%+ match" },
    { value: "remote", label: "Remote", count: filterCounts.remote, helper: "Work from anywhere" },
    { value: "high_pay", label: "High pay", count: filterCounts.high_pay, helper: "$5k+ salary" }
  ];

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
    void Promise.all([jobsQuery.refetch(), statsQuery.refetch(), marketQuery.refetch()]);
  }

  return (
    <main className="grid-lines min-h-screen px-3 py-4 md:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1580px] flex-col gap-4">
        <section className="rounded-[30px] border border-white/10 bg-[rgba(8,16,24,0.78)] p-4 backdrop-blur md:p-5">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="mono text-[11px] uppercase tracking-[0.34em] text-[var(--accent)]">
                    Career Intelligence System
                  </p>
                  <Badge className="border-[var(--signal-green)]/30 bg-[var(--signal-green)]/12 text-[var(--signal-green)]">
                    Live
                  </Badge>
                  <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
                    Airtable + Linear + CIS
                  </Badge>
                </div>
                <div className="mt-2 flex flex-col gap-2 md:flex-row md:items-end md:gap-3">
                  <h1 className="text-2xl font-semibold text-white md:text-3xl">Dual-track career OS</h1>
                  <p className="max-w-2xl text-sm text-[var(--text-secondary)]">
                    Short-term SDET search, long-term AI portfolio, one operating surface for jobs, companies, and next actions.
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
                  Remote {marketQuery.data?.remote_ratio ?? 0}%
                </Badge>
                <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
                  Hot skill {topMarketSkill}
                </Badge>
                <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
                  Source leader {dominantSource}
                </Badge>
                <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
                  Strategy layer active
                </Badge>
              </div>
            </div>

            <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_320px_420px] xl:items-center">
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

              <div className="relative block w-full">
                <Search
                  size={15}
                  className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search role, company, or text"
                  className="pl-10"
                />
              </div>

              <UrlAnalyzer onAnalyzed={handleAnalyzed} />
            </div>

            <TopBar stats={statsQuery.data} />
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)_380px]">
          <div className="space-y-4">
            <Card className="rounded-[24px] p-4">
              <div className="flex items-start gap-3">
                <span className="rounded-full border border-white/10 bg-white/6 p-2 text-[var(--accent)]">
                  <BrainCircuit size={15} />
                </span>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--text-muted)]">Candidate</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">{profileQuery.data?.name ?? "Loading..."}</h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">{profileQuery.data?.title ?? "Profile loading"}</p>
                </div>
              </div>

              <Separator className="my-4 bg-white/8" />

              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Strongest skills</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {strongSkills.length ? (
                    strongSkills.map((skill) => <Badge key={skill}>{skill}</Badge>)
                  ) : (
                    <p className="text-sm text-[var(--text-muted)]">No skill profile available yet.</p>
                  )}
                </div>
              </div>
            </Card>

            <Card className="rounded-[24px] p-4">
              <div className="flex items-start gap-3">
                <span className="rounded-full border border-white/10 bg-white/6 p-2 text-[var(--signal-amber)]">
                  <Target size={15} />
                </span>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--text-muted)]">Quick filters</p>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">Trim the queue without leaving the triage view.</p>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                {quickFilters.map((filter) => (
                  <button
                    key={filter.value}
                    type="button"
                    onClick={() => setQuickFilter(filter.value)}
                    className={`flex w-full items-center justify-between rounded-[18px] border px-3 py-3 text-left transition ${
                      quickFilter === filter.value
                        ? "border-[var(--accent)]/35 bg-[var(--accent)]/10"
                        : "border-white/8 bg-black/10 hover:bg-white/[0.05]"
                    }`}
                  >
                    <div>
                      <p className="text-sm font-medium text-white">{filter.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.16em] text-[var(--text-muted)]">{filter.helper}</p>
                    </div>
                    <Badge className="border-transparent bg-black/20 text-white">{filter.count}</Badge>
                  </button>
                ))}
              </div>
            </Card>

            <Card className="rounded-[24px] p-4">
              <div className="flex items-start gap-3">
                <span className="rounded-full border border-white/10 bg-white/6 p-2 text-[var(--signal-green)]">
                  <Sparkles size={15} />
                </span>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--text-muted)]">8-week focus</p>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">The gaps most worth closing next.</p>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                {learningFocus.length ? (
                  learningFocus.map(([skill, weeks]) => (
                    <div key={skill} className="rounded-[18px] border border-white/8 bg-black/10 px-3 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm text-white">{skill}</span>
                        <span className="text-xs uppercase tracking-[0.16em] text-[var(--signal-amber)]">{weeks} weeks</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-[var(--text-muted)]">Learning plan unavailable.</p>
                )}
              </div>
            </Card>
          </div>

          <div className="space-y-4">
            <JobTable
              jobs={filteredJobs}
              selectedId={selectedJobId}
              onSelect={setSelectedJobId}
              onSort={handleSort}
              sortBy={sortBy}
              sortDir={sortDir}
              isLoading={jobsQuery.isPending}
            />

            <Collapsible open={isMarketOpen} onOpenChange={setIsMarketOpen}>
              <Card className="overflow-hidden rounded-[24px]">
                <CollapsibleTrigger asChild>
                  <button type="button" className="flex w-full items-center justify-between px-4 py-4 text-left">
                    <div className="flex items-start gap-3">
                      <span className="rounded-full border border-white/10 bg-white/6 p-2 text-[var(--accent)]">
                        <Radar size={15} />
                      </span>
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--text-muted)]">Market snapshot</p>
                      <p className="mt-1 text-sm text-[var(--text-secondary)]">
                        Secondary analytics: source mix, hot skills, and salary bands.
                      </p>
                    </div>
                  </div>
                    <span className="inline-flex size-8 items-center justify-center rounded-full text-[var(--text-secondary)]">
                      {isMarketOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </span>
                  </button>
                </CollapsibleTrigger>

                <CollapsibleContent>
                  <Separator className="bg-white/8" />
                  <div className="grid gap-4 p-4 xl:grid-cols-3">
                    <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
                      <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Source mix</p>
                      <div className="mt-4 h-44">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={chartData}>
                            <XAxis dataKey="name" stroke="#6c7c91" tickLine={false} axisLine={false} />
                            <Tooltip contentStyle={TOOLTIP_STYLE} />
                            <Bar dataKey="count" radius={[8, 8, 0, 0]} fill="var(--accent)" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
                      <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Top skills</p>
                      <div className="mt-4 h-44">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={skillData} layout="vertical">
                            <CartesianGrid stroke="rgba(255,255,255,0.06)" horizontal={false} />
                            <XAxis type="number" stroke="#6c7c91" tickLine={false} axisLine={false} />
                            <YAxis
                              type="category"
                              dataKey="skill"
                              width={110}
                              stroke="#6c7c91"
                              tickLine={false}
                              axisLine={false}
                            />
                            <Tooltip contentStyle={TOOLTIP_STYLE} />
                            <Bar dataKey="count" radius={[0, 8, 8, 0]} fill="var(--signal-green)" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
                      <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Salary bands</p>
                      <div className="mt-4 h-44">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={salaryData}>
                            <XAxis dataKey="band" stroke="#6c7c91" tickLine={false} axisLine={false} />
                            <Tooltip contentStyle={TOOLTIP_STYLE} />
                            <Bar dataKey="count" radius={[8, 8, 0, 0]} fill="var(--signal-amber)" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                </CollapsibleContent>
              </Card>
            </Collapsible>
          </div>

          <DetailPanel job={selectedJob} onClose={() => setSelectedJobId(null)} />
        </section>

        <section className="grid gap-4">
          <StrategyPanel />
          <CompaniesPanel onSelectJob={setSelectedJobId} />
        </section>
      </div>
    </main>
  );
}
