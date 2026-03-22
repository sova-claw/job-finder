from app.agent_bridge.overnight import (
    build_kickoff_message,
    detect_stop_reason,
)


def test_build_kickoff_message_includes_role_model() -> None:
    message = build_kickoff_message("Ship the first careers-page scraper.", max_cycles=3)

    assert "Night shift started" in message
    assert "Nazar = CEO" in message
    assert "Claude = Product Owner / PM / BA / Scrum Master" in message
    assert "Codex = Tech Lead / Super Senior executor" in message


def test_detect_stop_reason_returns_known_signal() -> None:
    reason = detect_stop_reason("Blockers or next steps\n- Decision needed on Slack routing.")

    assert reason == "decision needed"


def test_detect_stop_reason_returns_none_for_clear_progress() -> None:
    reason = detect_stop_reason(
        "What I changed or found\n- Implemented ATS parsing for Greenhouse."
    )

    assert reason is None
