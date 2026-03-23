import asyncio

import pytest

from app.agent_bridge import overnight as overnight_module
from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.overnight import (
    build_cycle_summary,
    build_kickoff_message,
    build_overnight_clients,
    detect_stop_reason,
    run_timed_agent_command,
)


def test_build_kickoff_message_includes_role_model() -> None:
    message = build_kickoff_message("Ship the first careers-page scraper.", max_cycles=3)

    assert "Night shift started" in message
    assert "Nazar = CEO" in message
    assert "Claude = Product Owner / PM / BA / Scrum Master" in message
    assert "Codex = Tech Lead / Super Senior executor" in message


def test_detect_stop_reason_returns_known_signal() -> None:
    reason = detect_stop_reason(
        "@Nazar [DECISION NEEDED]\nContext: pick the Slack routing policy."
    )

    assert reason == "@nazar [decision needed]"


def test_detect_stop_reason_returns_none_for_clear_progress() -> None:
    reason = detect_stop_reason(
        "What I changed or found\n- Implemented ATS parsing for Greenhouse."
    )

    assert reason is None


def test_detect_stop_reason_ignores_non_blocking_decision_phrase() -> None:
    reason = detect_stop_reason(
        "Risks\n- This is not a decision needed now, just a likely follow-up."
    )

    assert reason is None


def test_build_overnight_clients_uses_dedicated_bot_tokens() -> None:
    settings = BridgeSettings(
        _env_file=None,
        slack_bot_token="xoxb-codex",
        planner_post_token="xoxb-claude",
        specialist_post_token="xoxb-llama",
    )

    clients = build_overnight_clients(settings)

    assert clients.kickoff.token == "xoxb-codex"
    assert clients.executor.token == "xoxb-codex"
    assert clients.planner.token == "xoxb-claude"
    assert clients.specialist is not None
    assert clients.specialist.token == "xoxb-llama"


def test_build_cycle_summary_compacts_executor_reply() -> None:
    summary = build_cycle_summary(
        cycle=1,
        max_cycles=3,
        status="continuing",
        executor_reply=(
            "Goal\nShip the update.\n\n"
            "What I changed or found\nAdded a compact cycle summary for Slack threads."
        ),
    )

    assert summary.startswith("Cycle 1/3: continuing - ")
    assert "Added a compact cycle summary" in summary


@pytest.mark.asyncio
async def test_run_timed_agent_command_returns_timeout_result(monkeypatch, tmp_path) -> None:
    async def fake_run_agent_command(command: str, prompt: str, *, cwd):
        await asyncio.sleep(0.05)
        return "done"

    monkeypatch.setattr(overnight_module, "run_agent_command", fake_run_agent_command)

    result = await run_timed_agent_command(
        "codex exec",
        "prompt",
        cwd=tmp_path,
        timeout_seconds=0.01,
    )

    assert result.timed_out is True
    assert "Timed out" in result.content
