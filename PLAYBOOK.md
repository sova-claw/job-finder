# CIS Playbook

## Goal Structure

### Track 1: `SDET / Python QA Automation`

- horizon: `2-3 months`
- objective: close one `6k+` role and collapse to one main project
- bias:
  - high-probability roles
  - recruiter outreach
  - careers pages
  - remote or abroad-friendly roles

### Track 2: `AI Engineering / Python AI`

- horizon: `6-12 months`
- objective: use CIS as the portfolio proof for AI engineering capability
- bias:
  - productized AI features
  - intelligence workflows
  - company watchlists
  - medium-term brand targets

These tracks do not conflict.

## Tool Responsibilities

### Airtable

Use Airtable for:
- company universe
- careers pages
- recruiters and agencies
- contacts
- outreach registry
- strategy targets

Do not use Airtable for:
- implementation backlog
- code bugs
- release planning

### Linear

Use Linear for:
- epics
- implementation tasks
- milestones
- bugs
- releases

Do not use Linear for:
- company list
- recruiter list
- outreach CRM
- salary hypotheses

### CIS

Use CIS for:
- openings intelligence
- company ranking
- dual-track dashboard
- strategy visibility
- signals and alerts

Do not use CIS v1 for:
- editing company CRM records
- editing recruiter CRM records
- editing outreach source-of-truth data

## Airtable Schema

### Table: `Companies`

Recommended columns:
- `Company`
- `Country`
- `City`
- `Geo bucket`
- `Track fit SDET`
- `Track fit AI`
- `Brand tier`
- `Salary hypothesis`
- `Careers URL`
- `LinkedIn URL`
- `Priority`
- `Status`
- `Notes`

Suggested views:
- `SDET Priority`
- `AI Watchlist`
- `Poland`
- `UK / London`
- `Remote EMEA`

### Table: `Career Sources`

Recommended columns:
- `Company`
- `Source type`
- `Source URL`
- `ATS type`
- `Status`
- `Notes`

### Table: `Recruiters & Agencies`

Recommended columns:
- `Name`
- `Agency`
- `Country`
- `Track`
- `LinkedIn URL`
- `Email`
- `Status`
- `Notes`

### Table: `Contacts`

Recommended columns:
- `Person`
- `Company`
- `Role`
- `Country`
- `LinkedIn URL`
- `Relationship`
- `Status`
- `Notes`

### Table: `Outreach`

Recommended columns:
- `Target type`
- `Company`
- `Person`
- `Track`
- `Channel`
- `Stage`
- `Due date`
- `Last touch`
- `Next action`
- `Notes`

### Table: `Strategy Targets`

Recommended columns:
- `Target`
- `Track`
- `Country`
- `Brand tier`
- `Rationale`
- `Status`

## CIS Runtime Boundaries

In v1:
- Airtable sync starts with `Companies` only
- sync direction is `Airtable -> CIS`
- no Linear runtime integration
- no Airtable write-back

Backend modules:
- `backend/app/integrations/airtable.py`
- `backend/app/services/company_sync.py`
- `backend/app/services/strategy.py`
- `backend/app/routers/companies.py`
- `backend/app/routers/strategy.py`

Runtime endpoints:
- `GET /api/companies`
- `GET /api/companies/{id}`
- `POST /api/sync/airtable`
- `GET /api/strategy`

## Decision Rules

### Compensation

Use a soft salary gate:
- `priority`: `6k+`
- `watch`: strong brand, strong geo, or unclear compensation
- `below_gate`: below `6k`

Below-gate roles remain visible in analytics, but do not drive immediate action.

### Track Assignment

Use separate ranking profiles:
- `sdet_qa`
- `ai_engineering`

Avoid collapsing both tracks into one score.

### Company Priority

Company priority should consider:
- brand tier
- geo fit
- track fit
- openings count
- salary hypothesis
- recruiter path quality
- current actionability

## Weekly Execution Loop

1. Update `Airtable` records:
   - companies
   - careers pages
   - outreach statuses
2. Sync Airtable into `CIS`
3. Review:
   - priority openings
   - company snapshots
   - source changes
4. Execute SDET actions:
   - apply
   - reach out
   - follow up
5. Build CIS features that strengthen the AI portfolio lane
6. Update `Linear` with implementation progress

## Linear Operating Model

Project:
- `CIS v2`

Epics:
- `Foundation`
- `Airtable Sync`
- `Companies UI`
- `Signals & Reddit`
- `Telegram & Actions`

Use `ops/linear/cis_v2_backlog.md` as the initial backlog blueprint.

## Source Hierarchy

Primary sources:
- LinkedIn via Apify
- company careers pages
- Airtable company universe

Secondary sources:
- Djinni
- DOU

Signals:
- Reddit and community intelligence

## Immediate Execution Order

1. Keep SDET outreach active now.
2. Stand up Airtable as the editable company CRM.
3. Sync Airtable `Companies` into CIS.
4. Use the new company panel and strategy view to drive targeting.
5. Expand later into:
   - recruiters
   - outreach sync
   - Reddit signals
   - Telegram digests
