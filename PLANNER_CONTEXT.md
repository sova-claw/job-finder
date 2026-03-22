# Planner Context

Career Intelligence System is a local-first career operating system for Nazar.

## Mission
- Short term: land one strong `SDET / Python QA Automation` role in the `6k+` range.
- Medium term: use CIS itself as a portfolio case for `AI Engineering / Python AI` transition.

## Roles
- `Claude planner`
  - plans work
  - writes acceptance criteria
  - reviews executor output
  - chooses the next highest-leverage task
- `Codex executor`
  - implements code
  - validates changes
  - commits and pushes
  - reports blockers and progress
- `Nazar`
  - makes product and priority decisions

## Product Constraints
- Stack stays: `FastAPI + Next.js + PostgreSQL`
- Local-first is preferred
- Slack is the visible coordination surface
- Airtable is the editable company/outreach layer
- Linear tracks engineering work only

## Current Priorities
1. careers-page sourcing
2. deduplication quality
3. high-confidence scoring
4. Slack routing and digests
5. recruiter/company intelligence
6. AI-track portfolio evolution

## Target Markets
- Israel
- UK / London
- Poland / Krakow / Warsaw
- Remote EMEA

## Target Company Profile
- product companies
- 100-2000 employees
- fintech / payments / devtools / cybersecurity

## Working Agreement
- Planner should produce compact, execution-ready handoffs.
- Planner should preserve continuity across threads using planner memory, repo state, and session transcript.
- Planner should ask Nazar for decisions only when tradeoffs are non-obvious.
- Claude only plans and reviews; Codex executes.
