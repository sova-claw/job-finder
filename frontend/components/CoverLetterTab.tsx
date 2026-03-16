"use client";

import { useMutation } from "@tanstack/react-query";
import { Copy, RefreshCcw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { generateCoverLetter } from "@/lib/api";
import { JobDetail, Tone } from "@/lib/types";
import { cn } from "@/lib/utils";

const tones: Tone[] = ["professional", "direct", "enthusiastic"];

export function CoverLetterTab({
  job,
  compact = false
}: {
  job: JobDetail;
  compact?: boolean;
}) {
  const [tone, setTone] = useState<Tone>("professional");
  const [draft, setDraft] = useState("");

  const mutation = useMutation({
    mutationFn: () => generateCoverLetter(job.id, tone),
    onSuccess: (result) => setDraft(result.letter)
  });

  return (
    <div className={cn("space-y-4", compact && "space-y-3")}>
      <div className="flex flex-wrap items-center gap-2">
        {tones.map((toneValue) => (
          <Button
            key={toneValue}
            variant={toneValue === tone ? "default" : "secondary"}
            size="sm"
            onClick={() => setTone(toneValue)}
            className="h-8 px-3 text-xs uppercase tracking-[0.16em]"
          >
            {toneValue}
          </Button>
        ))}
        <Button size="sm" onClick={() => mutation.mutate()} className="h-8 gap-2 px-3 text-xs uppercase tracking-[0.16em]">
          <RefreshCcw size={13} />
          {mutation.isPending ? "Generating..." : draft ? "Regenerate" : "Generate"}
        </Button>
      </div>

      {mutation.data?.profile_tags_used?.length ? (
        <div className="flex flex-wrap gap-2">
          {mutation.data.profile_tags_used.map((tag) => (
            <Badge
              key={tag}
              className="border-[var(--signal-green)]/40 bg-[var(--signal-green)]/12 text-[var(--signal-green)]"
            >
              {tag}
            </Badge>
          ))}
        </div>
      ) : null}

      <div className="rounded-[20px] border border-[var(--signal-green)]/18 bg-[var(--signal-green)]/8 px-3 py-2 text-sm text-[var(--signal-green)]">
        Add one concrete reason you want to work at {job.company ?? "this company"} before sending.
      </div>

      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        className={cn(
          "w-full rounded-[22px] border border-white/10 bg-black/15 p-4 text-sm leading-6 text-[var(--text-primary)] outline-none focus:border-[var(--accent)]",
          compact ? "min-h-60" : "min-h-72"
        )}
        placeholder="Generate a tailored letter, then edit it inline here."
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-[var(--text-muted)]">
          {mutation.data ? (mutation.data.cached ? "Loaded from cache." : "Fresh generation.") : "Draft not generated yet."}
        </p>
        <Button
          variant="secondary"
          className="h-8 gap-2 px-3 text-xs uppercase tracking-[0.16em]"
          onClick={() => navigator.clipboard.writeText(draft)}
          disabled={!draft}
          size="sm"
        >
          <Copy size={13} />
          Copy
        </Button>
      </div>
    </div>
  );
}
