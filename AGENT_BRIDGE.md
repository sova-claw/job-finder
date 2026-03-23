# Slack Agent Bridge

This bridge lets Slack act as the operating surface for a small agent team.

Supported modes:
- `orchestrator`
  - one local bridge runs planner and executor together
- `codex-follower`
  - native Claude speaks in Slack and the bridge only runs Codex
- `local-roles`
  - the local bridge owns `@Claude`, `@Codex`, and optional specialists like `@Llama`

For the most stable setup, use `local-roles` with dedicated Slack bots.

## Project-Owned Agent Space

Slack is only the UI. The agent state lives in the repo.

### Claude planner
- `agents/claude/CONTEXT.md`
  - stable planner role and operating rules
- `agents/claude/MEMORY.md`
  - rolling planner memory, updated after planner and executor replies
  - also updated from human Slack coaching feedback
- `agents/claude/GOALS.md`
  - current goal, success check, active thread goals, recent progress, open risks

### Codex executor
- `agents/codex/CONTEXT.md`
  - executor role and response contract

### Llama specialist
- `agents/llama/CONTEXT.md`
  - specialist role and compression rules
- `agents/llama/MEMORY.md`
  - rolling specialist memory

### Shared runtime state
- `.codex/agent_bridge_sessions.json`
  - per-thread transcript memory
- current repo state
  - branch, status, recent commits

Every planner call receives all of those inputs.

## Goal-Driven Flow

Planner replies now follow this packet:
- `Goal`
- `Decision`
- `Task`
- `Success Check`
- `Risks`
- `Handoff`

Executor replies follow this packet:
- `Goal`
- `What I will do`
- `What I changed or found`
- `Next Check`
- `Blockers or next steps`

This keeps the thread aligned around one explicit goal at a time.

Human Slack feedback can also teach Claude over time.
If a human says things like:
- be more human-readable
- reduce technical jargon
- keep replies shorter
- stay in planner mode

the bridge records that as planner coaching in `agents/claude/MEMORY.md`.

## Active Planning / Development

With dedicated `Claude` and `Codex` bots, one thread can run a bounded active loop:
- Claude sets the goal and next task
- Codex executes one bounded step
- Codex hands the thread back to Claude
- Claude can refine the next step

This loop is limited by:
- `AUTO_THREAD_MAX_CYCLES`

The loop stops early when a reply contains a real blocker or decision-needed signal.
Status-style questions do not auto-start another execution pass.

## Automatic Llama Assist

When a thread gets noisy, the planner bridge can auto-run `@Llama` first.

That summary is kept short and focuses on:
- current goal
- progress
- blockers
- clean handoff

The auto-trigger threshold is controlled with:
- `AUTO_SPECIALIST_SUMMARY_THRESHOLD`

Set it to `0` to disable auto-summarization.

## Bot-to-Bot Planning

Dedicated role bots can now ask each other questions in-thread.

Examples:
- `@Codex` can ask `@Claude` to clarify the goal or next task
- `@Llama` can hand a compressed summary back to `@Claude`
- `@Claude` can hand execution to `@Codex`

The bridge now accepts known bot-authored messages from the other agent bots instead of dropping them.
For the most reliable baton pass, the executor and specialist bridges can use
`PLANNER_POST_TOKEN` to post the next planner reply directly as the Claude bot.
For Codex-to-Llama delegation, the executor bridge can use `SPECIALIST_POST_TOKEN`
to post a specialist reply directly as the Llama bot.

## Codex Planner Mode

Codex can switch into a technical-planner mode when the thread is asking for:
- planning
- design
- discovery
- options
- delegation

In that mode, Codex stays technical and can:
- shape a bounded technical plan
- ask Claude for product or priority clarification
- delegate summarize / critique / extraction work to Llama

Claude remains the primary planner for product direction and priority.

## Dual-Bot / Multi-Bot Mode

Run one bridge process per bot and share:
- the same repo
- the same session store
- the same planner memory
- the same goal board

Use:
- `BRIDGE_MODE=local-roles`
- `BRIDGE_ROLE=planner` for the `Claude` bot
- `BRIDGE_ROLE=executor` for the `Codex` bot
- `BRIDGE_ROLE=specialist` for the `Llama` bot

Example launch:

```bash
cd backend
PYTHONPATH=. uv run python scripts/slack_agent_bridge.py --env-file .env.claude
PYTHONPATH=. uv run python scripts/slack_agent_bridge.py --env-file .env.codex
PYTHONPATH=. uv run python scripts/slack_agent_bridge.py --env-file .env.llama
```

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
SPECIALIST_COMMAND=ollama-api:qwen3.5:9b
SPECIALIST_OLLAMA_HOST=http://127.0.0.1:11434
EXECUTOR_DISPLAY_NAME=Codex
AUTO_SPECIALIST_SUMMARY_THRESHOLD=10
PLANNER_POST_TOKEN=xoxb-...
SPECIALIST_POST_TOKEN=xoxb-...
AUTO_THREAD_MAX_CYCLES=2
```

Optional explicit paths:

```env
BRIDGE_WORKDIR=/Users/sova/Desktop/Projects/job_finder
PLANNER_CONTEXT_PATH=/Users/sova/Desktop/Projects/job_finder/agents/claude/CONTEXT.md
PLANNER_MEMORY_PATH=/Users/sova/Desktop/Projects/job_finder/agents/claude/MEMORY.md
PLANNER_GOALS_PATH=/Users/sova/Desktop/Projects/job_finder/agents/claude/GOALS.md
EXECUTOR_CONTEXT_PATH=/Users/sova/Desktop/Projects/job_finder/agents/codex/CONTEXT.md
SPECIALIST_CONTEXT_PATH=/Users/sova/Desktop/Projects/job_finder/agents/llama/CONTEXT.md
SPECIALIST_MEMORY_PATH=/Users/sova/Desktop/Projects/job_finder/agents/llama/MEMORY.md
SESSIONS_PATH=/Users/sova/Desktop/Projects/job_finder/.codex/agent_bridge_sessions.json
PLANNER_BOT_USER_ID=
PLANNER_POST_TOKEN=
EXECUTOR_BOT_USER_ID=
SPECIALIST_BOT_USER_ID=
SPECIALIST_POST_TOKEN=
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

## Recommended Slack Pattern

Start a thread with:

```text
@Claude set the goal and next task.
```

Then continue with:

```text
@Codex execute it.
```

If the thread gets messy or you want a second opinion:

```text
@Llama compress the thread and list the blind spots.
```

Once a bot has joined a thread, follow-ups can stay in the same thread.
