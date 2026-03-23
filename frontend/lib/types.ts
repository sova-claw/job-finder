export type SourceGroup = "All" | "Ukraine" | "BigCo" | "Startups" | "Global";
export type Tone = "professional" | "direct" | "enthusiastic";
export type Verdict = "apply_now" | "prepare_first" | "not_aligned";
export type Track = "sdet_qa" | "ai_engineering";

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
  scored_at: string | null;
  slack_channel_id: string | null;
  slack_channel_name: string | null;
  slack_channel_url: string | null;
  slack_channel_created_at: string | null;
  is_active: boolean;
}

export interface JobDetail extends JobSummary {
  raw_text: string | null;
  requirements_must: string[] | null;
  requirements_nice: string[] | null;
  gaps: Gap[] | null;
  extracted_at: string | null;
}

export interface JobSlackChannelResponse {
  job_id: string;
  channel_id: string;
  channel_name: string;
  channel_url: string;
  created: boolean;
  created_at: string | null;
}

export interface ResearchEvidence {
  url: string;
  title: string | null;
  source_domain: string | null;
  snippet: string | null;
}

export interface ResearchFinding {
  id: string;
  job_id: string | null;
  company_snapshot_id: string | null;
  finding_type: string;
  title: string;
  summary: string;
  confidence: number | null;
  tags: string[] | null;
  evidence: ResearchEvidence[] | null;
  source_kind: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ResearchFindingListResponse {
  items: ResearchFinding[];
  total: number;
}

export interface CreateResearchFindingPayload {
  finding_type?: string;
  title: string;
  summary: string;
  confidence?: number | null;
  tags?: string[] | null;
  source_kind?: string;
  created_by?: string;
  source_url?: string | null;
  source_title?: string | null;
  source_domain?: string | null;
  source_snippet?: string | null;
}

export type JobChatRole = "user" | "assistant" | "system";

export interface JobChatMessage {
  id: string;
  job_id: string;
  role: JobChatRole;
  author: string | null;
  content: string;
  created_at: string | null;
}

export interface JobChatResponse {
  items: JobChatMessage[];
  total: number;
}

export interface CreateJobChatMessagePayload {
  role?: JobChatRole;
  author?: string;
  content: string;
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

export interface CompanySummary {
  id: string;
  airtable_record_id: string;
  name: string;
  country: string | null;
  city: string | null;
  geo_bucket: string | null;
  track_fit_sdet: boolean;
  track_fit_ai: boolean;
  brand_tier: string | null;
  salary_hypothesis: string | null;
  careers_url: string | null;
  linkedin_url: string | null;
  priority: string | null;
  status: string | null;
  notes: string | null;
  openings_count: number;
  priority_score: number;
  recommended_action: string;
  last_synced_at: string | null;
  updated_at: string | null;
}

export interface CompanyDetail extends CompanySummary {
  related_jobs: JobSummary[];
}

export interface CompanyListResponse {
  items: CompanySummary[];
  total: number;
}

export interface AirtableSyncResponse {
  source: string;
  count_found: number;
  count_created: number;
  count_updated: number;
  count_skipped: number;
  synced_at: string;
}

export interface ToolResponsibility {
  tool: string;
  role: string;
  owns: string[];
}

export interface StrategyTrack {
  id: Track;
  name: string;
  horizon: string;
  goal: string;
  current_focus: string;
}

export interface StrategyMetric {
  label: string;
  value: number;
}

export interface StrategySnapshot {
  tracks: StrategyTrack[];
  tools: ToolResponsibility[];
  linear_project: string;
  linear_epics: string[];
  weekly_loop: string[];
  metrics: StrategyMetric[];
}
