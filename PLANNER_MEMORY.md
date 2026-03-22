# Planner Memory

## Current Focus
- Replace native Slack Claude planning with project-owned local planner context.
- Keep `Claude = planner` and `Codex = executor` as separate roles.
- Make Slack threads the visible conversation surface.

## Known Working Integrations
- Airtable base sync is live
- Slack webhook alerts are live
- Slack Socket Mode bridge is live for `@Codex`
- Linear project exists for engineering tracking

## Known Gaps
- final Slack flow should rely on local `@Claude`, not the native Claude Slack app
- planner context should persist across tasks and threads
- thread conversation should remain reliable for both planner and executor

## Active Decisions
- tracked long-lived context belongs in repo
- transient Slack thread transcript belongs in local session storage
- native Claude Slack app should not be the source of planning state

## Next Likely Tasks
- stabilize `local-roles` Slack routing
- persist bridge runtime with launchd or similar
- add self-updating planner memory after planner/executor replies

## Recent Planner Notes
- (empty)

## Recent Execution Notes
- (empty)

## Recent Risks or Blockers
- (empty)

## Last Activity
- (empty)
