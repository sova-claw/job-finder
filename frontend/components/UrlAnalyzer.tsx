"use client";

import { FormEvent, useState, useTransition } from "react";
import { Link2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { analyzeUrl } from "@/lib/api";
import { JobDetail } from "@/lib/types";

export function UrlAnalyzer({
  onAnalyzed
}: {
  onAnalyzed: (job: JobDetail) => void;
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
        setError(
          submissionError instanceof Error ? submissionError.message : "Could not analyze URL"
        );
      }
    });
  }

  return (
    <Card className="p-5">
      <form className="flex flex-col gap-3 md:flex-row" onSubmit={onSubmit}>
        <label className="relative flex-1">
          <Link2
            size={16}
            className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
          />
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="Paste a job URL to scrape, extract, and score on demand"
            className="h-12 w-full rounded-full border border-white/10 bg-white/5 pl-11 pr-4 text-sm text-white outline-none transition focus:border-[var(--accent)]"
          />
        </label>
        <Button className="shrink-0" disabled={!url || isPending}>
          {isPending ? "Analyzing..." : "Analyze URL"}
        </Button>
      </form>
      {error ? <p className="mt-3 text-sm text-[var(--signal-red)]">{error}</p> : null}
    </Card>
  );
}
