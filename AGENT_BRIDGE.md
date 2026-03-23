# Slack Agent Bridge

This utility supports three Slack collaboration modes:

- `orchestrator`: the local bridge runs both `Claude Code` and `Codex`
- `codex-follower`: native `Claude` speaks in Slack and the local bridge runs `Codex`
- `local-roles`: the local bridge owns the agent roles and routes `@Claude`, `@Codex`, and optional specialist bots like `@Llama`

For a stable planner context, use `local-roles`.

## Recommended Architecture

Slack is only the interface.
The planner state lives in the project:

- `PLANNER_CONTEXT.md`
  - long-lived product and role context
- `PLANNER_MEMORY.md`
  - rolling operational memory
  - auto-updated by the bridge after planner and executor replies
- `.codex/agent_bridge_sessions.json`
  - per-thread transcript memory
- current repo state
  - branch, status, recent commits

Every planner call receives all four inputs.

## How Memory Updates Work

After a planner reply, the bridge extracts:
- `Intent`
- `Risks`
- `Handoff`

After an executor reply, the bridge extracts:
- `What I changed or found`
- `Blockers or next steps`

Those summaries are written back into `PLANNER_MEMORY.md` under:
- `Recent Planner Notes`
- `Recent Execution Notes`
- `Recent Risks or Blockers`
- `Next Suggested Tasks`
- `Last Activity`

This keeps one planner brain across many Slack threads without relying on the native Claude Slack app.

## How Slack Invocation Works

In `local-roles` mode:
- writing `@Claude ...` in Slack does not require the native Claude app
- the bridge listens to normal channel message events
- if a message contains `@Claude`, the bridge runs local `claude`
- if a message contains `@Codex`, the bridge runs local `codex`
- if a message contains `@Llama`, the bridge runs the configured specialist command
- after an agent has participated in a thread, plain follow-ups in that thread continue the same role unless redirected

This gives you one planner context across many tasks.

## Dual-Bot Mode

If you create separate Slack bots for `Claude`, `Codex`, and optional specialists like `Llama`, run one bridge process per bot and share:
- the same repo
- the same session store
- the same planner memory

Use:
- `BRIDGE_MODE=local-roles`
- `BRIDGE_ROLE=planner` for the `Claude` bot
- `BRIDGE_ROLE=executor` for the `Codex` bot
- `BRIDGE_ROLE=specialist` for the `Llama` bot

In this mode:
- real Slack mentions trigger each bot directly
- the planner can mention the executor with a real Slack mention
- the executor can hand review back to the planner with a real Slack mention

Example launch:

```bash
cd backend
PYTHONPATH=. uv run python scripts/slack_agent_bridge.py --env-file .env.claude
PYTHONPATH=. uv run python scripts/slack_agent_bridge.py --env-file .env.codex
PYTHONPATH=. uv run python scripts/slack_agent_bridge.py --env-file .env.llama
```

## Night Shift Mode

For an autonomous but bounded overnight run:

```bash
cd backend
PYTHONPATH=. uv run python scripts/agent_night_shift.py --channel-id <SLACK_CHANNEL_ID>
```

The night shift runner:
- opens one new Slack thread
- uses the same planner context and planner memory as the bridge
- runs `Claude planner -> Codex executor` in cycles
- stops when it hits a real blocker or decision
- posts a final summary into the same Slack thread

Recommended role model:
- `Nazar = CEO`
- `Claude = Product Owner / PM / BA / Scrum Master`
- `Codex = Tech Lead / Super Senior executor`

## Required Environment Variables

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
BRIDGE_MODE=local-roles
BRIDGE_ROLE=both
PLANNER_TRIGGER_PHRASE=@Claude
CODEX_TRIGGER_PHRASE=@Codex
SPECIALIST_TRIGGER_PHRASE=@Llama
PLANNER_COMMAND=claude -p --permission-mode bypassPermissions --model sonnet
EXECUTOR_COMMAND=codex exec --dangerously-bypass-approvals-and-sandbox --cd {cwd} -o {output_file}
SPECIALIST_COMMAND=ollama run llama3.2:3b
```

Optional:

```env
BRIDGE_WORKDIR=/Users/sova/Desktop/Projects/job_finder
PLANNER_CONTEXT_PATH=/Users/sova/Desktop/Projects/job_finder/PLANNER_CONTEXT.md
PLANNER_MEMORY_PATH=/Users/sova/Desktop/Projects/job_finder/PLANNER_MEMORY.md
SESSIONS_PATH=/Users/sova/Desktop/Projects/job_finder/.codex/agent_bridge_sessions.json
PLANNER_BOT_USER_ID=
EXECUTOR_BOT_USER_ID=
SPECIALIST_BOT_USER_ID=
DEFAULT_AGENT_CHANNEL_ID=
OVERNIGHT_MAX_CYCLES=3
OVERNIGHT_GOAL=Work the highest-priority unblocked task in the repo, keep tasks bounded, post progress in Slack, and stop when a real blocker or decision is needed.
MAX_HISTORY_MESSAGES=16
```

## Run

```bash
cd backend
uv sync --dev
PYTHONPATH=. uv run python scripts/slack_agent_bridge.py
```

## Slack App Configuration

Use Socket Mode.

Enable bot events:
- `app_mention`
- `message.channels`
- `message.groups`
- `message.im`
- `message.mpim`

Required bot scopes:
- `app_mentions:read`
- `chat:write`
- `channels:history`
- `groups:history`
- `im:history`
- `mpim:history`

## Recommended Slack Pattern

Start a task thread with:

```text
@Claude plan the next step for the careers scraper.
```

Then continue with:

```text
@Codex implement it.
```

For critique, summarization, or structured extraction:

```text
@Llama summarize the thread and list the main risks.
```

Later in the same thread, plain follow-ups can work too:

```text
status?
any blockers?
refine the plan
```
