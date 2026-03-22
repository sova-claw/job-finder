from pathlib import Path

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.service import (
    build_executor_prompt,
    build_planner_prompt,
    build_thread_key,
    is_planner_event,
    planner_review_suffix,
    render_transcript,
)
from app.agent_bridge.session_store import SessionMessage, ThreadSessionStore


def test_thread_session_store_round_trip(tmp_path: Path) -> None:
    store = ThreadSessionStore(str(tmp_path / "sessions.json"))
    thread_key = build_thread_key("C123", "171.222")

    store.append(thread_key, role="user", author="Human", content="Find the next task.")
    store.append(
        thread_key,
        role="planner",
        author="Claude planner",
        content="Do the scraper first.",
    )

    loaded = store.get(thread_key)

    assert len(loaded) == 2
    assert loaded[0].author == "Human"
    assert loaded[1].content == "Do the scraper first."


def test_prompt_builders_include_transcript() -> None:
    messages = [
        SessionMessage(
            created_at="2026-03-22T18:00:00+00:00",
            author="Human",
            role="user",
            content="Build the careers scraper.",
        ),
        SessionMessage(
            created_at="2026-03-22T18:01:00+00:00",
            author="Claude planner",
            role="planner",
            content="Start with company ATS endpoints.",
        ),
    ]

    transcript = render_transcript(messages, limit=8)
    planner_prompt = build_planner_prompt(messages, limit=8)
    executor_prompt = build_executor_prompt(messages, "Planner says do ATS first.", limit=8)

    assert "Build the careers scraper." in transcript
    assert "Claude Code acting as the planner" in planner_prompt
    assert "Planner handoff" in executor_prompt


def test_is_planner_event_matches_slack_plugin_shapes() -> None:
    settings = BridgeSettings(
        planner_bot_user_id="UCLAUDE",
        planner_bot_id="BCLAUDE",
        planner_display_name="Claude",
    )

    assert is_planner_event({"user": "UCLAUDE"}, settings) is True
    assert is_planner_event({"bot_id": "BCLAUDE"}, settings) is True
    assert is_planner_event({"username": "Claude"}, settings) is True
    assert is_planner_event({"bot_profile": {"name": "Claude"}}, settings) is True
    assert is_planner_event({"user": "UOTHER"}, settings) is False


def test_planner_review_suffix_prefers_real_mention() -> None:
    settings = BridgeSettings(planner_bot_user_id="UCLAUDE")
    assert planner_review_suffix(settings) == "<@UCLAUDE> please review and plan the next step."

    fallback = BridgeSettings()
    assert planner_review_suffix(fallback) == "@Claude please review and plan the next step."
