export type SourceGroup = "All" | "Ukraine" | "BigCo" | "Startups" | "Global";
export type Tone = "professional" | "direct" | "enthusiastic";
export type Verdict = "apply_now" | "prepare_first" | "not_aligned";

export interface Gap {
  skill: string;
  current: number;
  target: number;
  weeks_to_close: number;
}

export interface JobSummary {
  id: string;
  url: string;
  source: string;
  source_group: Exclude<SourceGroup, "All">;
  title: string | null;
  company: string | null;
  company_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  tags: string[] | null;
  domain: string | null;
  remote: boolean | null;
  location: string | null;
  match_score: number | null;
  top_gap: string | null;
  verdict: Verdict;
  posted_at: string | null;
  scraped_at: string | null;
  is_active: boolean;
}

export interface JobDetail extends JobSummary {
  raw_text: string | null;
  requirements_must: string[] | null;
  requirements_nice: string[] | null;
  gaps: Gap[] | null;
  extracted_at: string | null;
}

export interface JobListResponse {
  items: JobSummary[];
  total: number;
}

export interface JobStats {
  total_jobs: number;
  active_jobs: number;
  avg_score: number;
  high_pay_count: number;
  top_gap: string | null;
  source_breakdown: Record<string, number>;
}

export interface MarketInsight {
  top_skills: { skill: string; count: number }[];
  salary_distribution: { band: string; count: number }[];
  remote_ratio: number;
}

export interface CandidateProfile {
  name: string;
  title: string;
  summary: string;
  location: string;
  english_level: string;
  years_experience: Record<string, number>;
  strong_skills: string[];
  working_skills: string[];
  certifications: { name: string; provider: string }[];
  current_projects: string[];
  target_roles: string[];
  preferred_domains: string[];
  achievements: string[];
  learning_plan: Record<string, number>;
}

export interface CoverLetterResponse {
  id: string;
  job_id: string;
  tone: Tone;
  letter: string;
  profile_tags_used: string[];
  cached: boolean;
  created_at: string | null;
}
