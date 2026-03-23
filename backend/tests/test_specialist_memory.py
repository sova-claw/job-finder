from pathlib import Path

from app.agent_bridge.specialist_memory import SpecialistMemoryStore


def test_specialist_memory_store_bootstraps_expected_sections(tmp_path: Path) -> None:
    memory_path = tmp_path / "LLAMA_MEMORY.md"

    SpecialistMemoryStore(str(memory_path)).ensure_exists()

    content = memory_path.read_text(encoding="utf-8")

    assert "# Llama Memory" in content
    assert "## Working Modes" in content
    assert "## Recent Structured Findings" in content
    assert "## Last Activity" in content


def test_specialist_memory_store_records_specialist_updates(tmp_path: Path) -> None:
    memory_path = tmp_path / "LLAMA_MEMORY.md"
    store = SpecialistMemoryStore(str(memory_path))

    store.record_specialist_reply(
        "C1:100.0",
        """Mode
Extract

Findings
- Extracted recruiter entities with names, countries, and LinkedIn URLs.

Recommended handoff
- Hand the normalized records to @Codex for schema mapping.
""",
    )

    content = memory_path.read_text(encoding="utf-8")

    assert "## Working Modes\n- Extract" in content
    assert (
        "- C1:100.0: Extracted recruiter entities with names, countries, and LinkedIn URLs."
        in content
    )
    assert (
        "- C1:100.0: Hand the normalized records to @Codex for schema mapping."
        in content
    )
    assert "specialist updated C1:100.0" in content
