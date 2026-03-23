from pathlib import Path

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.service import (
    build_executor_prompt,
    build_planner_prompt,
    build_specialist_prompt,
    build_thread_key,
    contains_trigger_phrase,
    event_dedup_key,
    inject_known_mentions,
    normalize_event_payload,
    planner_review_suffix,
    should_trigger_executor,
    should_trigger_planner,
    should_trigger_specialist,
    targets_codex,
    targets_planner,
    targets_specialist,
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


def test_thread_session_store_upsert_updates_existing_message(tmp_path: Path) -> None:
    store = ThreadSessionStore(str(tmp_path / "sessions.json"))
    thread_key = build_thread_key("C123", "171.222")

    store.upsert(
        thread_key,
        role="user",
        author="Human",
        content="status?",
        message_ts="111.1",
    )
    store.upsert(
        thread_key,
        role="user",
        author="Human",
        content="status??",
        message_ts="111.1",
    )

    loaded = store.get(thread_key)
    assert len(loaded) == 1
    assert loaded[0].content == "status??"
    assert loaded[0].message_ts == "111.1"


def test_prompt_builders_include_context(tmp_path: Path) -> None:
    context = tmp_path / "PLANNER_CONTEXT.md"
    memory = tmp_path / "PLANNER_MEMORY.md"
    specialist_context = tmp_path / "LLAMA_CONTEXT.md"
    specialist_memory = tmp_path / "LLAMA_MEMORY.md"
    context.write_text("stable context")
    memory.write_text("rolling memory")
    specialist_context.write_text("specialist context")
    specialist_memory.write_text("specialist memory")
    settings = BridgeSettings(
        _env_file=None,
        planner_context_path=str(context),
        planner_memory_path=str(memory),
        specialist_context_path=str(specialist_context),
        specialist_memory_path=str(specialist_memory),
    )
    messages = [
        SessionMessage(
            created_at="2026-03-22T18:00:00+00:00",
            author="Human",
            role="user",
            content="Build the careers scraper.",
        )
    ]

    planner_prompt = build_planner_prompt(
        messages, settings=settings, repo_state="branch main", limit=8
    )
    executor_prompt = build_executor_prompt(
        messages,
        "Do ATS first.",
        settings=settings,
        repo_state="branch main",
        limit=8,
    )
    specialist_prompt = build_specialist_prompt(
        messages,
        settings=settings,
        repo_state="branch main",
        limit=8,
    )

    assert "stable context" in planner_prompt
    assert "rolling memory" in planner_prompt
    assert "branch main" in executor_prompt
    assert "Planner handoff" in executor_prompt
    assert "Slack thread transcript" in specialist_prompt
    assert "specialist context" in specialist_prompt
    assert "specialist memory" in specialist_prompt


def test_planner_review_suffix_in_local_roles_uses_trigger_phrase() -> None:
    settings = BridgeSettings(
        _env_file=None,
        bridge_mode="local-roles",
        planner_trigger_phrase="@Claude",
    )
    assert planner_review_suffix(settings) == "@Claude please review and plan the next step."


def test_planner_review_suffix_prefers_real_slack_mention() -> None:
    settings = BridgeSettings(
        _env_file=None,
        bridge_mode="local-roles",
        planner_trigger_phrase="@Claude",
        planner_bot_user_id="UCLAUDE",
    )

    assert planner_review_suffix(settings) == "<@UCLAUDE> please review and plan the next step."


def test_inject_known_mentions_rewrites_trigger_phrases() -> None:
    settings = BridgeSettings(
        _env_file=None,
        planner_bot_user_id="UCLAUDE",
        executor_bot_user_id="UCODEX",
        specialist_bot_user_id="ULLAMA",
        planner_trigger_phrase="@Claude",
        codex_trigger_phrase="@Codex",
        specialist_trigger_phrase="@Llama",
    )

    rewritten = inject_known_mentions(
        "@Codex ship it, ask @Claude for review, then ask @Llama for critique.",
        settings,
    )

    assert "<@UCODEX>" in rewritten
    assert "<@UCLAUDE>" in rewritten
    assert "<@ULLAMA>" in rewritten


def test_contains_trigger_phrase_normalizes_case() -> None:
    assert contains_trigger_phrase("please ask @claude next", "@Claude") is True
    assert contains_trigger_phrase("hello there", "@Claude") is False


def test_codex_target_detection_supports_mentions_and_plain_text() -> None:
    settings = BridgeSettings(_env_file=None, codex_trigger_phrase="@Codex")

    assert targets_codex("hello <@UCODEX>", "hello", settings, codex_user_id="UCODEX") is True
    assert targets_codex("hello @Codex", "hello @Codex", settings, codex_user_id="") is True
    assert targets_codex("hello there", "hello there", settings, codex_user_id="UCODEX") is False


def test_planner_target_detection_supports_trigger_phrase() -> None:
    settings = BridgeSettings(_env_file=None, planner_trigger_phrase="@Claude")

    assert targets_planner("@Claude review this", "@Claude review this", settings) is True
    assert targets_planner("review this", "review this", settings) is False


def test_specialist_target_detection_supports_trigger_phrase() -> None:
    settings = BridgeSettings(_env_file=None, specialist_trigger_phrase="@Llama")

    assert targets_specialist("@Llama summarize this", "@Llama summarize this", settings) is True
    assert targets_specialist("summarize this", "summarize this", settings) is False


def test_should_trigger_executor_for_codex_and_thread_follow_up() -> None:
    settings = BridgeSettings(_env_file=None)
    history = [
        SessionMessage(
            created_at="2026-03-22T18:01:00+00:00",
            author="Codex executor",
            role="executor",
            content="Need one clarification.",
        )
    ]

    assert should_trigger_executor(
        raw_text="@Codex status",
        cleaned_text="@Codex status",
        settings=settings,
        codex_user_id="",
        planner_user_id="",
        history=history,
    ) is True
    assert should_trigger_executor(
        raw_text="status?",
        cleaned_text="status?",
        settings=settings,
        codex_user_id="",
        planner_user_id="",
        history=history,
    ) is True


def test_should_trigger_planner_for_phrase_and_thread_follow_up() -> None:
    settings = BridgeSettings(_env_file=None, planner_trigger_phrase="@Claude")
    history = [
        SessionMessage(
            created_at="2026-03-22T18:01:00+00:00",
            author="Claude planner",
            role="planner",
            content="Intent...",
        )
    ]

    assert should_trigger_planner(
        raw_text="@Claude refine this",
        cleaned_text="@Claude refine this",
        settings=settings,
        planner_user_id="",
        codex_user_id="",
        history=history,
    ) is True
    assert should_trigger_planner(
        raw_text="one more variant",
        cleaned_text="one more variant",
        settings=settings,
        planner_user_id="",
        codex_user_id="",
        history=history,
    ) is True


def test_should_trigger_specialist_for_phrase_and_thread_follow_up() -> None:
    settings = BridgeSettings(_env_file=None, specialist_trigger_phrase="@Llama")
    history = [
        SessionMessage(
            created_at="2026-03-22T18:01:00+00:00",
            author="Llama specialist",
            role="specialist",
            content="Mode\nSummarize",
        )
    ]

    assert should_trigger_specialist(
        raw_text="@Llama summarize this",
        cleaned_text="@Llama summarize this",
        settings=settings,
        specialist_user_id="",
        planner_user_id="",
        codex_user_id="",
        history=history,
    ) is True
    assert should_trigger_specialist(
        raw_text="tighten the summary",
        cleaned_text="tighten the summary",
        settings=settings,
        specialist_user_id="",
        planner_user_id="",
        codex_user_id="",
        history=history,
    ) is True


def test_normalize_event_payload_unwraps_thread_subtypes() -> None:
    event = {
        "type": "message",
        "subtype": "message_changed",
        "channel": "C123",
        "message": {
            "ts": "1.23",
            "thread_ts": "1.00",
            "text": "<@UCODEX> status?",
            "user": "UUSER",
        },
    }

    normalized = normalize_event_payload(event)

    assert normalized is not None
    assert normalized["channel"] == "C123"
    assert normalized["thread_ts"] == "1.00"


def test_event_dedup_key_changes_when_text_changes() -> None:
    one = event_dedup_key({"channel": "C1", "ts": "1.0", "user": "U1", "text": "hi"})
    two = event_dedup_key({"channel": "C1", "ts": "1.0", "user": "U1", "text": "hello"})

    assert one != two
