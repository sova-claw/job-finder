import {
  CandidateProfile,
  CoverLetterResponse,
  JobDetail,
  JobListResponse,
  MarketInsight,
  JobStats,
  SourceGroup,
  Tone
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function fetchJobs(params: {
  sourceGroup: SourceGroup;
  search: string;
  sortBy: string;
  sortDir: string;
}): Promise<JobListResponse> {
  const searchParams = new URLSearchParams();
  if (params.sourceGroup !== "All") {
    searchParams.set("source_group", params.sourceGroup);
  }
  if (params.search) {
    searchParams.set("search", params.search);
  }
  searchParams.set("sort_by", params.sortBy);
  searchParams.set("sort_dir", params.sortDir);
  return request<JobListResponse>(`/jobs?${searchParams.toString()}`);
}

export async function fetchJob(jobId: string): Promise<JobDetail> {
  return request<JobDetail>(`/jobs/${jobId}`);
}

export async function analyzeUrl(url: string): Promise<JobDetail> {
  return request<JobDetail>("/jobs/analyze-url", {
    method: "POST",
    body: JSON.stringify({ url })
  });
}

export async function fetchStats(): Promise<JobStats> {
  return request<JobStats>("/stats");
}

export async function fetchProfile(): Promise<CandidateProfile> {
  return request<CandidateProfile>("/profile");
}

export async function fetchMarketInsight(): Promise<MarketInsight> {
  return request<MarketInsight>("/market");
}

export async function generateCoverLetter(
  jobId: string,
  tone: Tone
): Promise<CoverLetterResponse> {
  return request<CoverLetterResponse>(`/jobs/${jobId}/cover-letter`, {
    method: "POST",
    body: JSON.stringify({ tone })
  });
}
