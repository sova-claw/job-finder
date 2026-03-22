# Linear Backlog Blueprint

Use this file to create the initial `CIS v2` project in Linear.

## Epic: `Foundation`

Status:
- done

Issues:
- Define `Airtable vs Linear vs CIS` operating model
- Add strategy documentation and diagrams
- Extend backend schema for company snapshots

## Epic: `Airtable Sync`

Status:
- done

Issues:
- Add Airtable API client with pagination and backoff
- Add `Companies` sync service
- Add manual sync endpoint
- Add scheduled sync job
- Add tests for idempotent company sync
- Add Slack delivery for newly discovered jobs

## Epic: `Companies UI`

Status:
- done

Issues:
- Add tracked companies panel
- Add company detail panel with related openings
- Add strategy panel
- Add Airtable sync affordance in UI

## Epic: `Signals & Reddit`

Status:
- next

Issues:
- Add Reddit signal ingestion model
- Add signal aggregation service
- Add `Signals` API
- Add signal cards in dashboard

## Epic: `Telegram & Actions`

Status:
- next

Issues:
- Add action queue models and API
- Add Telegram digest preview
- Add due-follow-up alerts
- Add daily summary rules
