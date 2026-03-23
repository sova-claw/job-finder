from pathlib import Path

from app.agent_bridge.goal_memory import GoalBoardStore


def test_goal_board_store_bootstraps_expected_sections(tmp_path: Path) -> None:
    goals_path = tmp_path / "GOALS.md"

    GoalBoardStore(str(goals_path)).ensure_exists()

    content = goals_path.read_text(encoding="utf-8")

    assert "# Claude Goal Board" in content
    assert "## Current Goal" in content
    assert "## Active Thread Goals" in content
    assert "## Last Activity" in content


def test_goal_board_records_planner_and_executor_updates(tmp_path: Path) -> None:
    goals_path = tmp_path / "GOALS.md"
    store = GoalBoardStore(str(goals_path))

    store.record_planner_reply(
        "C1:100.0",
        """Goal
Ship the careers scraper for the first ATS targets.

Decision
Keep the first iteration ATS-first.

Task
- Parse Greenhouse boards first.

Success Check
- JFrog and monday roles land in CIS.

Risks
- monday may still need a custom selector.

Handoff
- Start with JFrog and monday.com.
""",
    )
    store.record_executor_reply(
        "C1:100.0",
        """Goal
Ship the careers scraper for the first ATS targets.

What I will do
- Implement the Greenhouse parser.

What I changed or found
- Added company board discovery and normalized job extraction.

Next Check
- Validate two target companies end-to-end.

Blockers or next steps
- Need one more selector for monday custom cards.
""",
    )

    content = goals_path.read_text(encoding="utf-8")

    assert "## Current Goal\n- Ship the careers scraper for the first ATS targets." in content
    assert "## Success Check\n- JFrog and monday roles land in CIS." in content
    assert (
        "- C1:100.0: Ship the careers scraper for the first ATS targets. "
        "| task: Parse Greenhouse boards first. "
        "| success: JFrog and monday roles land in CIS."
        in content
    )
    assert (
        "- C1:100.0: Added company board discovery and normalized job extraction. "
        "| next check: Validate two target companies end-to-end."
        in content
    )
    assert "- C1:100.0: monday may still need a custom selector." in content
    assert "- C1:100.0: Need one more selector for monday custom cards." in content
