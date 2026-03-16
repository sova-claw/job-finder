"use client";

import { FormEvent, useState, useTransition } from "react";
import { Link2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { analyzeUrl } from "@/lib/api";
import { JobDetail } from "@/lib/types";

export function UrlAnalyzer({
  onAnalyzed,
  className
}: {
  onAnalyzed: (job: JobDetail) => void;
  className?: string;
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    startTransition(async () => {
      try {
        const job = await analyzeUrl(url);
        setUrl("");
        onAnalyzed(job);
      } catch (submissionError) {
        setError(submissionError instanceof Error ? submissionError.message : "Could not analyze URL");
      }
    });
  }

  return (
    <Card className={cn("rounded-[22px] px-3 py-3", className)}>
      <form className="flex flex-col gap-2 lg:flex-row" onSubmit={onSubmit}>
        <label className="relative min-w-0 flex-1">
          <Link2
            size={15}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
          />
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="Analyze one job URL on demand"
            className="h-10 w-full rounded-full border border-white/10 bg-white/5 pl-10 pr-4 text-sm text-white outline-none transition focus:border-[var(--accent)]"
          />
        </label>
        <Button className="h-10 shrink-0 px-4" disabled={!url || isPending} size="sm">
          {isPending ? "Analyzing..." : "Analyze URL"}
        </Button>
      </form>
      {error ? <p className="mt-2 text-sm text-[var(--signal-red)]">{error}</p> : null}
    </Card>
  );
}
