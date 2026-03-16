import { JobSummary, Verdict } from "@/lib/types";

export function formatSalary(job: Pick<JobSummary, "salary_min" | "salary_max">): string {
  if (!job.salary_min && !job.salary_max) {
    return "n/a";
  }
  if (job.salary_min && job.salary_max) {
    return `$${job.salary_min.toLocaleString()}-$${job.salary_max.toLocaleString()}`;
  }
  return `$${(job.salary_max ?? job.salary_min ?? 0).toLocaleString()}`;
}

export function isFreshJob(postedAt: string | null): boolean {
  if (!postedAt) {
    return false;
  }
  return Date.now() - new Date(postedAt).getTime() < 24 * 60 * 60 * 1000;
}

export function formatAge(postedAt: string | null): string {
  if (!postedAt) {
    return "n/a";
  }

  const deltaMs = Date.now() - new Date(postedAt).getTime();
  if (deltaMs <= 0) {
    return "now";
  }

  const hours = Math.floor(deltaMs / (60 * 60 * 1000));
  if (hours < 24) {
    return `${Math.max(1, hours)}h`;
  }

  const days = Math.floor(hours / 24);
  if (days < 7) {
    return `${days}d`;
  }

  const weeks = Math.floor(days / 7);
  if (weeks < 5) {
    return `${weeks}w`;
  }

  return new Date(postedAt).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric"
  });
}

export function isHighPay(job: Pick<JobSummary, "salary_min" | "salary_max">): boolean {
  return (job.salary_max ?? job.salary_min ?? 0) >= 5000;
}

export function scoreClasses(score: number | null): { fill: string; text: string; pill: string } {
  if (score === null) {
    return {
      fill: "bg-white/18",
      text: "text-white/70",
      pill: "border-white/10 bg-white/6 text-[var(--text-secondary)]"
    };
  }

  if (score >= 70) {
    return {
      fill: "bg-[var(--signal-green)]",
      text: "text-[var(--signal-green)]",
      pill: "border-[var(--signal-green)]/30 bg-[var(--signal-green)]/10 text-[var(--signal-green)]"
    };
  }

  if (score >= 45) {
    return {
      fill: "bg-[var(--signal-amber)]",
      text: "text-[var(--signal-amber)]",
      pill: "border-[var(--signal-amber)]/30 bg-[var(--signal-amber)]/10 text-[var(--signal-amber)]"
    };
  }

  return {
    fill: "bg-[var(--signal-red)]",
    text: "text-[var(--signal-red)]",
    pill: "border-[var(--signal-red)]/30 bg-[var(--signal-red)]/10 text-[var(--signal-red)]"
  };
}

export function salaryClasses(job: Pick<JobSummary, "salary_min" | "salary_max">): string {
  if (!job.salary_min && !job.salary_max) {
    return "border-white/10 bg-white/6 text-[var(--text-secondary)]";
  }

  const value = job.salary_max ?? job.salary_min ?? 0;
  if (value >= 10000) {
    return "border-[var(--signal-green)]/28 bg-[var(--signal-green)]/12 text-[var(--signal-green)]";
  }
  if (value >= 5000) {
    return "border-[var(--signal-amber)]/28 bg-[var(--signal-amber)]/12 text-[var(--signal-amber)]";
  }
  return "border-[var(--accent)]/24 bg-[var(--accent)]/10 text-[var(--accent-strong)]";
}

export function verdictMeta(verdict: Verdict): {
  label: string;
  tone: string;
  badge: string;
} {
  if (verdict === "apply_now") {
    return {
      label: "Apply now",
      tone: "border-[var(--signal-green)]/22 bg-[var(--signal-green)]/10",
      badge: "border-[var(--signal-green)]/30 bg-[var(--signal-green)]/10 text-[var(--signal-green)]"
    };
  }

  if (verdict === "prepare_first") {
    return {
      label: "Prepare first",
      tone: "border-[var(--signal-amber)]/22 bg-[var(--signal-amber)]/10",
      badge: "border-[var(--signal-amber)]/30 bg-[var(--signal-amber)]/10 text-[var(--signal-amber)]"
    };
  }

  return {
    label: "Not aligned",
    tone: "border-[var(--signal-red)]/22 bg-[var(--signal-red)]/10",
    badge: "border-[var(--signal-red)]/30 bg-[var(--signal-red)]/10 text-[var(--signal-red)]"
  };
}
