# Slack Agent Bridge

This utility lets one Slack thread coordinate two local agents:

- `Claude Code` = planner
- `Codex` = executor

It is intentionally separate from the `job_finder` runtime.

## Behavior

1. Human writes in a Slack DM or `@mentions` the bot in a thread.
2. The bridge stores the thread transcript locally.
3. The bridge invokes `Claude Code` with the transcript and planner instructions.
4. The planner reply is posted back to the same Slack thread.
5. The bridge invokes `Codex` with the transcript plus planner handoff.
6. The executor reply is posted back to the same Slack thread.

The bridge ignores bot messages so it does not loop on itself.

## Files

- `backend/app/agent_bridge/config.py`
- `backend/app/agent_bridge/session_store.py`
- `backend/app/agent_bridge/service.py`
- `backend/scripts/slack_agent_bridge.py`

## Required environment variables

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
PLANNER_COMMAND=claude -p --permission-mode bypassPermissions --model sonnet
EXECUTOR_COMMAND=codex exec --dangerously-bypass-approvals-and-sandbox --cd {cwd} -o {output_file}
```

Optional:

```env
BRIDGE_WORKDIR=/Users/sova/Desktop/Projects/job_finder
SESSIONS_PATH=/Users/sova/Desktop/Projects/job_finder/.codex/agent_bridge_sessions.json
MAX_HISTORY_MESSAGES=16
```

## Run

```bash
cd backend
uv sync --dev
uv run python scripts/slack_agent_bridge.py
```

## Slack app configuration

Use Socket Mode for the starter version.

The app should have:
- `app_mentions:read`
- `channels:history`
- `chat:write`
- `im:history`
- `im:write`
- Socket Mode enabled

This starter is intentionally minimal:
- no streaming edits
- no resumable subprocess sessions
- transcript persisted to a local JSON file

That keeps it small enough to harden before adding long-lived session plumbing.
