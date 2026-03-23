"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus, Send } from "lucide-react";

import { createJobChatMessage, fetchJobChat } from "@/lib/api";
import { JobDetail } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export function JobChatTab({ job }: { job: JobDetail }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");

  const chatQuery = useQuery({
    queryKey: ["job-chat", job.id],
    queryFn: () => fetchJobChat(job.id)
  });

  const messages = chatQuery.data?.items ?? [];

  const createMutation = useMutation({
    mutationFn: () => createJobChatMessage(job.id, { content: draft, role: "user", author: "Nazar" }),
    onSuccess: async () => {
      setDraft("");
      await queryClient.invalidateQueries({ queryKey: ["job-chat", job.id] });
    }
  });

  return (
    <div className="flex h-[min(70vh,760px)] flex-col xl:h-[calc(100vh-15rem)]">
      <div className="rounded-[20px] border border-white/8 bg-black/10 p-4">
        <div className="flex items-start gap-3">
          <span className="rounded-full border border-white/10 bg-white/6 p-2 text-[var(--accent)]">
            <MessageSquarePlus size={14} />
          </span>
          <div>
            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--text-muted)]">Job workspace chat</p>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              One persistent thread per job for outreach ideas, interview prep, objections, and next actions.
            </p>
          </div>
        </div>
      </div>

      <ScrollArea className="mt-4 flex-1 pr-4">
        <div className="space-y-3 pb-1">
          {messages.length ? (
            messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "max-w-[88%] rounded-[20px] border px-4 py-3",
                  message.role === "user"
                    ? "ml-auto border-[var(--accent)]/20 bg-[var(--accent)]/10"
                    : "border-white/8 bg-black/10"
                )}
              >
                <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  {message.author ?? message.role}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--text-secondary)]">
                  {message.content}
                </p>
              </div>
            ))
          ) : (
            <div className="rounded-[20px] border border-white/8 bg-black/10 p-4 text-sm text-[var(--text-secondary)]">
              No chat yet for this job. Start with outreach ideas, prep questions, or a mini action plan.
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="mt-4 rounded-[20px] border border-white/8 bg-black/10 p-4">
        <Textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Write a note for this job: outreach angle, why this company matters, prep topics, interview risks, or next action."
        />
        <div className="mt-3 flex justify-end">
          <Button
            size="sm"
            className="gap-2"
            disabled={!draft.trim() || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            <Send size={13} />
            {createMutation.isPending ? "Posting" : "Post message"}
          </Button>
        </div>
        {createMutation.isError ? (
          <p className="mt-3 text-sm text-[var(--signal-red)]">
            {createMutation.error instanceof Error ? createMutation.error.message : "Failed to post message"}
          </p>
        ) : null}
      </div>
    </div>
  );
}
