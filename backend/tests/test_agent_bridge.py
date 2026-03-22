from pathlib import Path

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.service import (
    build_executor_prompt,
    build_planner_prompt,
    build_thread_key,
    is_planner_event,
    planner_review_suffix,
    render_transcript,
    should_trigger_executor,
    targets_codex,
    targets_planner,
    thread_has_executor_activity,
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


def test_codex_target_detection_supports_mentions_and_plain_text() -> None:
    settings = BridgeSettings(codex_trigger_phrase="@Codex")

    assert targets_codex("hello <@UCODEX>", "hello", settings, codex_user_id="UCODEX") is True
    assert targets_codex("hello @Codex", "hello @Codex", settings, codex_user_id="") is True
    assert targets_codex("hello there", "hello there", settings, codex_user_id="UCODEX") is False


def test_planner_target_detection_supports_mentions_and_plain_text() -> None:
    settings = BridgeSettings(planner_bot_user_id="UCLAUDE", planner_display_name="Claude")

    assert targets_planner("<@UCLAUDE> please review", "please review", settings) is True
    assert targets_planner("@Claude review this", "@Claude review this", settings) is True
    assert targets_planner("review this", "review this", settings) is False


def test_thread_has_executor_activity_detects_prior_codex_turns() -> None:
    history = [
        SessionMessage(
            created_at="2026-03-22T18:00:00+00:00",
            author="Human",
            role="user",
            content="hi",
        ),
        SessionMessage(
            created_at="2026-03-22T18:01:00+00:00",
            author="Codex executor",
            role="executor",
            content="question",
        ),
    ]

    assert thread_has_executor_activity(history) is True


def test_should_trigger_executor_for_planner_handoff_and_human_follow_up() -> None:
    settings = BridgeSettings(planner_bot_user_id="UCLAUDE", planner_display_name="Claude")
    history = [
        SessionMessage(
            created_at="2026-03-22T18:00:00+00:00",
            author="Human",
            role="user",
            content="start",
        ),
        SessionMessage(
            created_at="2026-03-22T18:01:00+00:00",
            author="Codex executor",
            role="executor",
            content="Need one clarification.",
        ),
    ]

    assert should_trigger_executor(
        planner_event=True,
        raw_text="@Codex please execute",
        cleaned_text="@Codex please execute",
        settings=settings,
        codex_user_id="",
        history=history,
    ) is True

    assert should_trigger_executor(
        planner_event=False,
        raw_text="status?",
        cleaned_text="status?",
        settings=settings,
        codex_user_id="",
        history=history,
    ) is True

    assert should_trigger_executor(
        planner_event=False,
        raw_text="@Claude please review",
        cleaned_text="@Claude please review",
        settings=settings,
        codex_user_id="",
        history=history,
    ) is False
