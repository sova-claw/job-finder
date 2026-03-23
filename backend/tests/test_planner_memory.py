from pathlib import Path

from app.agent_bridge.planner_memory import PlannerMemoryStore


def test_planner_memory_store_bootstraps_expected_sections(tmp_path: Path) -> None:
    memory_path = tmp_path / "PLANNER_MEMORY.md"

    PlannerMemoryStore(str(memory_path)).ensure_exists()

    content = memory_path.read_text(encoding="utf-8")

    assert "# Planner Memory" in content
    assert "## Current Goal" in content
    assert "## Current Success Check" in content
    assert "## Current Communication Guidance" in content
    assert "## Recent Coaching Notes" in content
    assert "## Recent Planner Notes" in content
    assert "## Recent Execution Notes" in content
    assert "## Last Activity" in content


def test_planner_memory_store_records_planner_and_executor_updates(tmp_path: Path) -> None:
    memory_path = tmp_path / "PLANNER_MEMORY.md"
    store = PlannerMemoryStore(str(memory_path))

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
- Some companies use custom HTML pages.

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

    content = memory_path.read_text(encoding="utf-8")

    assert "## Current Goal\n- Ship the careers scraper for the first ATS targets." in content
    assert "## Current Success Check\n- JFrog and monday roles land in CIS." in content
    assert "- C1:100.0: Keep the first iteration ATS-first." in content
    assert "- C1:100.0: Added company board discovery and normalized job extraction." in content
    assert "- C1:100.0: Some companies use custom HTML pages." in content
    assert "- C1:100.0: Start with JFrog and monday.com." in content
    assert "executor updated C1:100.0" in content
    planner_section = (
        "## Recent Planner Notes\n"
        "- C1:100.0: Ship the careers scraper for the first ATS targets.\n"
        "- (empty)"
    )
    execution_section = (
        "## Recent Execution Notes\n"
        "- C1:100.0: Added company board discovery and normalized job extraction.\n"
        "- (empty)"
    )
    assert planner_section not in content
    assert execution_section not in content


def test_planner_memory_store_deduplicates_repeated_items(tmp_path: Path) -> None:
    memory_path = tmp_path / "PLANNER_MEMORY.md"
    store = PlannerMemoryStore(str(memory_path))

    planner_reply = """Goal
Keep Slack as UI only.

Decision
- Reuse local planner context.

Risks
- none

Handoff
- Add memory auto-update.
"""

    store.record_planner_reply("C1:100.0", planner_reply)
    store.record_planner_reply("C1:100.0", planner_reply)

    content = memory_path.read_text(encoding="utf-8")

    assert content.count("Keep Slack as UI only.") == 1


def test_planner_memory_store_records_human_feedback(tmp_path: Path) -> None:
    memory_path = tmp_path / "PLANNER_MEMORY.md"
    store = PlannerMemoryStore(str(memory_path))

    store.record_human_feedback(
        "C1:100.0",
        "Claude is too technical. Make him more human readable and shorter.",
    )

    content = memory_path.read_text(encoding="utf-8")

    assert "## Current Communication Guidance" in content
    assert "Use more human-readable language." in content
    assert "Reduce technical jargon in planner replies." in content
    assert "Keep planner replies shorter." in content
    assert "## Recent Coaching Notes" in content
    assert "coaching updated C1:100.0" in content


def test_planner_memory_store_accumulates_coaching_feedback(tmp_path: Path) -> None:
    memory_path = tmp_path / "PLANNER_MEMORY.md"
    store = PlannerMemoryStore(str(memory_path))

    store.record_human_feedback(
        "C1:100.0",
        "Claude is too technical. Make him more human readable.",
    )
    store.record_human_feedback(
        "C1:100.0",
        "Claude should set goals clearly and stay shorter.",
    )

    content = memory_path.read_text(encoding="utf-8")

    assert "Use more human-readable language." in content
    assert "Reduce technical jargon in planner replies." in content
    assert "Drive the thread with a clear goal and next move." in content
    assert "Keep planner replies shorter." in content
