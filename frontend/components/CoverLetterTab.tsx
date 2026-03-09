"use client";

import { useMutation } from "@tanstack/react-query";
import { Copy, RefreshCcw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { generateCoverLetter } from "@/lib/api";
import { JobDetail, Tone } from "@/lib/types";

const tones: Tone[] = ["professional", "direct", "enthusiastic"];

export function CoverLetterTab({ job }: { job: JobDetail }) {
  const [tone, setTone] = useState<Tone>("professional");
  const [draft, setDraft] = useState("");

  const mutation = useMutation({
    mutationFn: () => generateCoverLetter(job.id, tone),
    onSuccess: (result) => setDraft(result.letter)
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {tones.map((toneValue) => (
          <Button
            key={toneValue}
            variant={toneValue === tone ? "default" : "secondary"}
            size="sm"
            onClick={() => setTone(toneValue)}
          >
            {toneValue}
          </Button>
        ))}
        <Button size="sm" onClick={() => mutation.mutate()} className="gap-2">
          <RefreshCcw size={14} />
          {mutation.isPending ? "Generating..." : "Generate cover letter"}
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

      <div className="rounded-3xl border border-[var(--signal-green)]/20 bg-[var(--signal-green)]/8 px-4 py-3 text-sm text-[var(--signal-green)]">
        Add one personal reason you want to work at {job.company ?? "this company"} before sending.
      </div>

      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        className="min-h-72 w-full rounded-[28px] border border-white/10 bg-black/15 p-5 text-sm leading-7 text-[var(--text-primary)] outline-none focus:border-[var(--accent)]"
        placeholder="Generate a tailored letter, then edit it inline here."
      />

      <div className="flex justify-between gap-3">
        <p className="text-sm text-[var(--text-muted)]">
          {mutation.data?.cached ? "Loaded from cache." : "Fresh generation."}
        </p>
        <Button
          variant="secondary"
          className="gap-2"
          onClick={() => navigator.clipboard.writeText(draft)}
          disabled={!draft}
        >
          <Copy size={14} />
          Copy
        </Button>
      </div>
    </div>
  );
}
