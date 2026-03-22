from __future__ import annotations

from app.schemas.strategy import StrategyMetric, StrategySnapshot, StrategyTrack, ToolResponsibility


def build_strategy_snapshot(*, active_jobs: int, total_companies: int) -> StrategySnapshot:
    return StrategySnapshot(
        tracks=[
            StrategyTrack(
                id="sdet_qa",
                name="SDET / Python QA Automation",
                horizon="2-3 months",
                goal="Land one 6k+ contract and consolidate into a single project.",
                current_focus="Recruiters, careers pages, and high-probability openings.",
            ),
            StrategyTrack(
                id="ai_engineering",
                name="AI Engineering / Python AI",
                horizon="6-12 months",
                goal="Build CIS as the portfolio case that proves AI engineering capability.",
                current_focus="AI-powered product features, signals, and company watchlists.",
            ),
        ],
        tools=[
            ToolResponsibility(
                tool="Airtable",
                role="Career CRM",
                owns=["companies", "career sources", "recruiters", "contacts", "outreach"],
            ),
            ToolResponsibility(
                tool="Linear",
                role="Engineering delivery",
                owns=["epics", "implementation tasks", "milestones", "bugs", "releases"],
            ),
            ToolResponsibility(
                tool="CIS",
                role="Intelligence dashboard",
                owns=["opening intelligence", "company analytics", "signals", "alerts"],
            ),
        ],
        linear_project="CIS v2",
        linear_epics=[
            "Foundation",
            "Airtable Sync",
            "Companies UI",
            "Signals & Reddit",
            "Telegram & Actions",
        ],
        weekly_loop=[
            "Update Airtable company universe and outreach statuses.",
            "Sync Airtable into CIS and review new company/opening intelligence.",
            "Run recruiter and careers-page outreach for the SDET track.",
            "Use CIS development work as the AI engineering portfolio lane.",
        ],
        metrics=[
            StrategyMetric(label="Active roles", value=active_jobs),
            StrategyMetric(label="Tracked companies", value=total_companies),
            StrategyMetric(label="Tracks", value=2),
            StrategyMetric(label="Linear epics", value=5),
        ],
    )
