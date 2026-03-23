"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Hash, Loader2, PlusSquare } from "lucide-react";

import { ensureJobSlackChannel } from "@/lib/api";
import { JobDetail } from "@/lib/types";
import { Button } from "@/components/ui/button";

export function JobSlackTab({ job }: { job: JobDetail }) {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: () => ensureJobSlackChannel(job.id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["job", job.id] }),
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      ]);
    },
  });

  const channelId = createMutation.data?.channel_id ?? job.slack_channel_id;
  const channelName = createMutation.data?.channel_name ?? job.slack_channel_name;
  const channelUrl = createMutation.data?.channel_url ?? job.slack_channel_url;
  const channelCreatedAt = createMutation.data?.created_at ?? job.slack_channel_created_at;
  const hasChannel = Boolean(channelId && channelName && channelUrl);

  return (
    <div className="flex h-[min(70vh,760px)] flex-col gap-4 xl:h-[calc(100vh-15rem)]">
      <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
        <div className="flex items-start gap-3">
          <span className="rounded-full border border-white/10 bg-white/6 p-2 text-[var(--accent)]">
            <Hash size={14} />
          </span>
          <div>
            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Slack workspace channel</p>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Create one real Slack channel for this job. Use it for research, recruiter outreach, interview prep,
              and next actions instead of local notes.
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-[24px] border border-white/8 bg-black/10 p-5">
        {hasChannel ? (
          <>
            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Connected channel</p>
            <h3 className="mt-2 text-xl font-semibold text-white">#{channelName}</h3>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              This job already has a Slack workspace channel. The initial job brief has been seeded there so we can
              continue the conversation in Slack.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--text-muted)]">Channel id</p>
                <p className="mt-2 text-sm font-medium text-white">{channelId}</p>
              </div>
              <div className="rounded-[18px] border border-white/8 bg-white/[0.03] px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--text-muted)]">Created</p>
                <p className="mt-2 text-sm font-medium text-white">
                  {channelCreatedAt ? new Date(channelCreatedAt).toLocaleString() : "Connected"}
                </p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <Button className="gap-2" onClick={() => window.open(channelUrl ?? undefined, "_blank")}>
                <ExternalLink size={14} />
                Open Slack channel
              </Button>
              <Button
                variant="outline"
                className="gap-2 border-white/10 bg-transparent text-white hover:bg-white/5"
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Hash size={14} />}
                Refresh link
              </Button>
            </div>
          </>
        ) : (
          <>
            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">No channel yet</p>
            <h3 className="mt-2 text-xl font-semibold text-white">Create the Slack room for this role</h3>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              We’ll create one public Slack channel, store it on this job, and post the initial job brief there.
            </p>
            <div className="mt-4">
              <Button className="gap-2" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
                {createMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <PlusSquare size={14} />}
                {createMutation.isPending ? "Creating channel" : "Create Slack channel"}
              </Button>
            </div>
          </>
        )}

        {createMutation.isSuccess ? (
          <p className="mt-4 text-sm text-[var(--signal-green)]">
            {createMutation.data.created ? "Slack channel created and seeded." : "Existing Slack channel connected."}
          </p>
        ) : null}

        {createMutation.isError ? (
          <p className="mt-4 text-sm text-[var(--signal-red)]">
            {createMutation.error instanceof Error ? createMutation.error.message : "Failed to create Slack channel"}
          </p>
        ) : null}
      </div>
    </div>
  );
}
