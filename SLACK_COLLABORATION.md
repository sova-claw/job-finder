# Slack Collaboration Protocol

Recommended channels:
- `#plans`
- `#jobs-inbox`
- `#scraper-runs`

## Role Model

- `Planner`
  - local planning role handled by the bridge via `#plans`
- `@Codex`
  - local executor role handled by the bridge
- `Nazar`
  - decision maker

This setup does not rely on the native Claude Slack app for planning state.
The bridge owns the planner context and reuses it on every call.

## Where Context Lives

Tracked in repo:
- `agents/planner/CONTEXT.md`
- `agents/codex/CONTEXT.md`
- `agents/llama/CONTEXT.md`
- `agents/llama/MEMORY.md`

Local runtime state:
- `.codex/agent_bridge_sessions.json`

Live repo context:
- current branch
- working tree status
- recent commits

## Thread Model

- one task = one Slack thread
- start with a planning note in `#plans`
- move to `@Codex` for implementation
- keep follow-ups in the same thread

## Example

Planner reply appears in-thread as `Planner`.

Then:

```text
@Codex execute that plan.
```

Executor reply appears in-thread as `Codex`.

## Why This Works Better

- planner context is project-owned, not Slack-app-owned
- every planner call gets the same stable planner context
- thread transcript adds task-local context
- repo state adds current implementation context
- keeping the planner stateless reduces stale carry-over between threads
