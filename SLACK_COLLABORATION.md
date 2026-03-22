# Slack Collaboration Protocol

Recommended channel:
- `#agent-room`

## Role Model

- `@Claude`
  - local planner role handled by the bridge
- `@Codex`
  - local executor role handled by the bridge
- `Nazar`
  - decision maker

This setup does not rely on the native Claude Slack app for planning state.
The bridge owns the planner context and reuses it on every call.

## Where Context Lives

Tracked in repo:
- `PLANNER_CONTEXT.md`
- `PLANNER_MEMORY.md`
  - updated by the bridge after planner and executor replies

Local runtime state:
- `.codex/agent_bridge_sessions.json`

Live repo context:
- current branch
- working tree status
- recent commits

## Thread Model

- one task = one Slack thread
- start with `@Claude`
- move to `@Codex` for implementation
- keep follow-ups in the same thread

## Example

```text
@Claude plan the next step for careers-page scraping.
```

Planner reply appears in-thread as `Claude planner`.

Then:

```text
@Codex execute that plan.
```

Executor reply appears in-thread as `Codex executor`.

## Why This Works Better

- planner context is project-owned, not Slack-app-owned
- every planner call gets the same long-lived context
- thread transcript adds task-local context
- repo state adds current implementation context
