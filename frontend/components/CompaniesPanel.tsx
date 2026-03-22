"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, ExternalLink, Linkedin, RefreshCcw, Search } from "lucide-react";

import { fetchCompanies, fetchCompany, syncAirtableCompanies } from "@/lib/api";
import { CompanySummary, Track } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

type TrackFilter = "all" | Track;

const TRACK_FILTERS: { value: TrackFilter; label: string; helper: string }[] = [
  { value: "all", label: "All", helper: "Full company universe" },
  { value: "sdet_qa", label: "SDET", helper: "Short-term monetization track" },
  { value: "ai_engineering", label: "AI", helper: "Portfolio and switch track" }
];

function CompanyRow({
  company,
  selected,
  onSelect
}: {
  company: CompanySummary;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-[18px] border px-3 py-3 text-left transition",
        selected
          ? "border-[var(--accent)]/35 bg-[var(--accent)]/10"
          : "border-white/8 bg-black/10 hover:bg-white/[0.05]"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-semibold text-white">{company.name}</p>
            {company.brand_tier ? <Badge>{company.brand_tier}</Badge> : null}
          </div>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--text-muted)]">
            {[company.country, company.city].filter(Boolean).join(" · ") || company.geo_bucket || "Location TBD"}
          </p>
        </div>
        <Badge className="border-transparent bg-black/20 text-white">{company.openings_count}</Badge>
      </div>
      <p className="mt-3 text-sm text-[var(--text-secondary)]">{company.recommended_action}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {company.track_fit_sdet ? <Badge className="text-[var(--signal-green)]">SDET</Badge> : null}
        {company.track_fit_ai ? <Badge className="text-[var(--accent)]">AI</Badge> : null}
        {company.priority ? (
          <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
            {company.priority}
          </Badge>
        ) : null}
      </div>
    </button>
  );
}

export function CompaniesPanel({
  onSelectJob
}: {
  onSelectJob?: (jobId: string) => void;
}) {
  const queryClient = useQueryClient();
  const [track, setTrack] = useState<TrackFilter>("all");
  const [search, setSearch] = useState("");
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null);

  const companiesQuery = useQuery({
    queryKey: ["companies", track, search],
    queryFn: () =>
      fetchCompanies({
        track: track === "all" ? undefined : track,
        search: search || undefined
      })
  });

  const companies = companiesQuery.data?.items ?? [];
  const activeCompanyId = useMemo(() => {
    if (selectedCompanyId && companies.some((company) => company.id === selectedCompanyId)) {
      return selectedCompanyId;
    }
    return companies[0]?.id ?? null;
  }, [companies, selectedCompanyId]);

  useEffect(() => {
    if (activeCompanyId !== selectedCompanyId) {
      setSelectedCompanyId(activeCompanyId);
    }
  }, [activeCompanyId, selectedCompanyId]);

  const detailQuery = useQuery({
    queryKey: ["company", activeCompanyId],
    queryFn: () => fetchCompany(activeCompanyId as string),
    enabled: Boolean(activeCompanyId)
  });

  const syncMutation = useMutation({
    mutationFn: syncAirtableCompanies,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["companies"] }),
        queryClient.invalidateQueries({ queryKey: ["company"] }),
        queryClient.invalidateQueries({ queryKey: ["strategy"] })
      ]);
    }
  });

  const selectedCompany = detailQuery.data;

  return (
    <Card className="rounded-[24px] p-4 md:p-5">
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="border-[var(--signal-green)]/30 bg-[var(--signal-green)]/12 text-[var(--signal-green)]">
                Airtable
              </Badge>
              <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
                Read model in CIS
              </Badge>
            </div>
            <h2 className="mt-3 text-xl font-semibold text-white">Tracked companies</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
              Edit the company universe in Airtable. CIS syncs the snapshot, attaches live openings,
              and suggests the next action. Linear stays for engineering work only.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
              {companiesQuery.data?.total ?? 0} tracked
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="gap-2"
            >
              <RefreshCcw size={13} className={syncMutation.isPending ? "animate-spin" : ""} />
              {syncMutation.isPending ? "Syncing" : "Sync Airtable"}
            </Button>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
          <div className="space-y-4">
            <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
              <div className="relative">
                <Search
                  size={15}
                  className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search companies, notes, or cities"
                  className="pl-10"
                />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {TRACK_FILTERS.map((filter) => (
                  <button
                    key={filter.value}
                    type="button"
                    onClick={() => setTrack(filter.value)}
                    className={cn(
                      "rounded-full border px-3 py-2 text-left text-xs uppercase tracking-[0.16em] transition",
                      track === filter.value
                        ? "border-[var(--accent)]/35 bg-[var(--accent)]/12 text-white"
                        : "border-white/8 bg-black/10 text-[var(--text-secondary)] hover:bg-white/[0.05]"
                    )}
                    title={filter.helper}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-[20px] border border-white/8 bg-black/10">
              <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  Company universe
                </p>
                <span className="mono text-xs text-[var(--text-muted)]">{companies.length} visible</span>
              </div>
              <ScrollArea className="h-[420px]">
                <div className="space-y-2 p-3">
                  {companies.length ? (
                    companies.map((company) => (
                      <CompanyRow
                        key={company.id}
                        company={company}
                        selected={company.id === activeCompanyId}
                        onSelect={() => setSelectedCompanyId(company.id)}
                      />
                    ))
                  ) : (
                    <div className="px-3 py-6 text-sm text-[var(--text-secondary)]">
                      {companiesQuery.isPending
                        ? "Loading companies..."
                        : "No companies synced yet. Add records in Airtable, then run Sync Airtable."}
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>
          </div>

          <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
            {selectedCompany ? (
              <div className="flex h-full flex-col">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-2xl font-semibold text-white">{selectedCompany.name}</p>
                      {selectedCompany.brand_tier ? <Badge>{selectedCompany.brand_tier}</Badge> : null}
                      {selectedCompany.priority ? (
                        <Badge className="border-white/10 bg-white/6 text-[var(--text-secondary)]">
                          {selectedCompany.priority}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm text-[var(--text-secondary)]">
                      {[selectedCompany.country, selectedCompany.city].filter(Boolean).join(" · ") ||
                        selectedCompany.geo_bucket ||
                        "Location TBD"}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {selectedCompany.careers_url ? (
                      <Button asChild size="sm" variant="outline" className="gap-2">
                        <a href={selectedCompany.careers_url} rel="noreferrer" target="_blank">
                          <ExternalLink size={13} />
                          Careers
                        </a>
                      </Button>
                    ) : null}
                    {selectedCompany.linkedin_url ? (
                      <Button asChild size="sm" variant="outline" className="gap-2">
                        <a href={selectedCompany.linkedin_url} rel="noreferrer" target="_blank">
                          <Linkedin size={13} />
                          LinkedIn
                        </a>
                      </Button>
                    ) : null}
                  </div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                      Priority score
                    </p>
                    <p className="mt-2 text-lg font-semibold text-white">{selectedCompany.priority_score}</p>
                  </div>
                  <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                      Openings
                    </p>
                    <p className="mt-2 text-lg font-semibold text-white">{selectedCompany.openings_count}</p>
                  </div>
                  <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                      Salary hypothesis
                    </p>
                    <p className="mt-2 text-sm font-medium text-white">
                      {selectedCompany.salary_hypothesis ?? "Unknown"}
                    </p>
                  </div>
                  <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                      Next action
                    </p>
                    <p className="mt-2 text-sm font-medium text-white">{selectedCompany.recommended_action}</p>
                  </div>
                </div>

                <Separator className="my-4 bg-white/8" />

                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
                  <div className="space-y-4">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Company context
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {selectedCompany.track_fit_sdet ? (
                          <Badge className="text-[var(--signal-green)]">SDET track</Badge>
                        ) : null}
                        {selectedCompany.track_fit_ai ? (
                          <Badge className="text-[var(--accent)]">AI track</Badge>
                        ) : null}
                        {selectedCompany.status ? <Badge>{selectedCompany.status}</Badge> : null}
                        {selectedCompany.geo_bucket ? <Badge>{selectedCompany.geo_bucket}</Badge> : null}
                      </div>
                    </div>

                    <div className="rounded-[18px] border border-white/8 bg-white/[0.03] p-4">
                      <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Notes</p>
                      <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
                        {selectedCompany.notes ??
                          "No manual notes yet. This company is still a raw Airtable record waiting for human context."}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-[18px] border border-white/8 bg-white/[0.03] p-4">
                    <div className="flex items-center gap-2">
                      <Building2 size={15} className="text-[var(--accent)]" />
                      <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Related openings
                      </p>
                    </div>
                    <div className="mt-4 space-y-3">
                      {selectedCompany.related_jobs.length ? (
                        selectedCompany.related_jobs.map((job) => (
                          <button
                            key={job.id}
                            type="button"
                            onClick={() => onSelectJob?.(job.id)}
                            className="w-full rounded-[16px] border border-white/8 bg-black/10 px-3 py-3 text-left transition hover:bg-white/[0.05]"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="truncate text-sm font-medium text-white">{job.title ?? "Untitled role"}</p>
                                <p className="mt-1 text-xs uppercase tracking-[0.16em] text-[var(--text-muted)]">
                                  {job.source_group}
                                </p>
                              </div>
                              <Badge className="border-transparent bg-black/20 text-white">
                                {job.match_score ?? 0}%
                              </Badge>
                            </div>
                          </button>
                        ))
                      ) : (
                        <p className="text-sm text-[var(--text-secondary)]">
                          No active openings currently attached to this company snapshot.
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-full min-h-[360px] items-center justify-center text-center text-sm text-[var(--text-secondary)]">
                {detailQuery.isPending
                  ? "Loading company details..."
                  : "No company selected yet. Sync Airtable or choose a company from the list."}
              </div>
            )}
          </div>
        </div>

        {syncMutation.isError ? (
          <div className="rounded-[18px] border border-[var(--signal-red)]/25 bg-[var(--signal-red)]/10 px-4 py-3 text-sm text-[var(--signal-red)]">
            {syncMutation.error instanceof Error ? syncMutation.error.message : "Airtable sync failed"}
          </div>
        ) : null}
      </div>
    </Card>
  );
}
