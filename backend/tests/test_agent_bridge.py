from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.agent_bridge import service as service_module
from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.service import (
    SlackAgentBridge,
    build_executor_prompt,
    build_planner_prompt,
    build_specialist_prompt,
    build_thread_key,
    contains_trigger_phrase,
    count_role,
    detect_auto_stop_reason,
    event_author_identity,
    event_dedup_key,
    extract_ollama_model,
    inject_known_mentions,
    looks_like_planning_request,
    looks_like_status_request,
    normalize_event_payload,
    planner_review_suffix,
    should_auto_continue_thread,
    should_auto_summarize_for_planner,
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
    goals = tmp_path / "GOALS.md"
    executor_context = tmp_path / "CODEX_CONTEXT.md"
    specialist_context = tmp_path / "LLAMA_CONTEXT.md"
    specialist_memory = tmp_path / "LLAMA_MEMORY.md"
    context.write_text("stable context")
    memory.write_text("rolling memory")
    goals.write_text("goal board")
    executor_context.write_text("executor context")
    specialist_context.write_text("specialist context")
    specialist_memory.write_text("specialist memory")
    settings = BridgeSettings(
        _env_file=None,
        planner_context_path=str(context),
        planner_memory_path=str(memory),
        planner_goals_path=str(goals),
        executor_context_path=str(executor_context),
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
    assert "goal board" in planner_prompt
    assert "branch main" in executor_prompt
    assert "executor context" in executor_prompt
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


def test_extract_ollama_model_supports_api_and_cli_styles() -> None:
    assert extract_ollama_model("ollama-api:qwen3.5:9b") == "qwen3.5:9b"
    assert extract_ollama_model("ollama run qwen3.5:9b --hidethinking") == "qwen3.5:9b"
    assert extract_ollama_model("codex exec --dangerously-bypass-approvals-and-sandbox") is None


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


def test_should_auto_summarize_for_planner_requires_noisy_thread() -> None:
    history = [
        SessionMessage(
            created_at="2026-03-22T18:01:00+00:00",
            author="Human",
            role="user",
            content=f"message {index}",
        )
        for index in range(10)
    ]

    assert should_auto_summarize_for_planner(history, threshold=10) is True

    history.append(
        SessionMessage(
            created_at="2026-03-22T18:02:00+00:00",
            author="Llama specialist",
            role="specialist",
            content="Mode\nSummarize",
        )
    )
    assert should_auto_summarize_for_planner(history, threshold=10) is False


def test_event_author_identity_maps_known_bot_users() -> None:
    settings = BridgeSettings(
        _env_file=None,
        planner_bot_user_id="UCLAUDE",
        executor_bot_user_id="UCODEX",
        specialist_bot_user_id="ULLAMA",
    )

    assert event_author_identity(
        {"user": "UCLAUDE"},
        settings,
        self_bot_user_id="USELF",
    ) == ("planner", "Claude planner")
    assert event_author_identity(
        {"user": "UCODEX"},
        settings,
        self_bot_user_id="USELF",
    ) == ("executor", "Codex executor")
    assert event_author_identity(
        {"user": "ULLAMA"},
        settings,
        self_bot_user_id="USELF",
    ) == ("specialist", "Llama specialist")


def test_count_role_counts_matching_messages() -> None:
    history = [
        SessionMessage(
            created_at="2026-03-22T18:01:00+00:00",
            author="Claude planner",
            role="planner",
            content="Goal",
        ),
        SessionMessage(
            created_at="2026-03-22T18:02:00+00:00",
            author="Codex executor",
            role="executor",
            content="Done 1",
        ),
        SessionMessage(
            created_at="2026-03-22T18:03:00+00:00",
            author="Codex executor",
            role="executor",
            content="Done 2",
        ),
    ]

    assert count_role(history, "executor") == 2
    assert count_role(history, "planner") == 1


def test_detect_auto_stop_reason_and_status_request_helpers() -> None:
    assert detect_auto_stop_reason("Blocked: waiting on Nazar") == "blocked:"
    assert detect_auto_stop_reason("All clear") is None
    assert looks_like_status_request("status?") is True
    assert looks_like_status_request("what changed?") is True
    assert looks_like_status_request("implement the next step") is False
    assert looks_like_planning_request("plan the next technical step") is True
    assert looks_like_planning_request("give me status") is False


def test_should_auto_continue_thread_respects_budget_and_stop_signals() -> None:
    history = [
        SessionMessage(
            created_at="2026-03-22T18:01:00+00:00",
            author="Codex executor",
            role="executor",
            content="Cycle 1",
        )
    ]

    assert (
        should_auto_continue_thread(
            history,
            max_cycles=2,
            latest_text="Ship the next bounded change.",
        )
        is True
    )
    assert (
        should_auto_continue_thread(
            history,
            max_cycles=1,
            latest_text="Ship the next bounded change.",
        )
        is False
    )
    assert (
        should_auto_continue_thread(
            history,
            max_cycles=2,
            latest_text="Blocked: waiting on credentials.",
        )
        is False
    )


@pytest.mark.asyncio
async def test_run_executor_and_post_in_dedicated_mode_hands_off_to_planner(
    monkeypatch, tmp_path: Path
) -> None:
    settings = BridgeSettings(
        _env_file=None,
        bridge_mode="local-roles",
        bridge_role="executor",
        planner_post_token="xoxb-planner",
        slack_bot_token="xoxb-test",
        sessions_path=str(tmp_path / "sessions.json"),
    )
    bridge = SlackAgentBridge(settings)
    planner_handoff = AsyncMock()
    thread_key = build_thread_key("C123", "171.222")

    async def fake_collect_repo_state(cwd: Path) -> str:
        return "Branch: main"

    async def fake_run_agent_command(command_template: str, prompt: str, *, cwd: Path) -> str:
        return "Executor result"

    async def fake_post_long_message(
        client, *, channel: str, thread_ts: str, header: str, content: str
    ) -> None:
        return None

    monkeypatch.setattr(service_module, "collect_repo_state", fake_collect_repo_state)
    monkeypatch.setattr(service_module, "run_agent_command", fake_run_agent_command)
    monkeypatch.setattr(service_module, "post_long_message", fake_post_long_message)
    monkeypatch.setattr(bridge, "_run_planner_via_peer_token", planner_handoff)

    await bridge._run_executor_and_post(
        client=object(),
        channel="C123",
        thread_ts="171.222",
        thread_key=thread_key,
        planner_output="Do one smoke test.",
        continue_with_planner=True,
    )

    planner_handoff.assert_awaited_once_with(
        channel="C123",
        thread_ts="171.222",
        thread_key=thread_key,
    )
    assert bridge.sessions.get(thread_key)[-1].content == (
        "Executor result\n\n@Claude please review and plan the next step."
    )


@pytest.mark.asyncio
async def test_run_executor_and_post_skips_planner_handoff_when_not_continuing(
    monkeypatch, tmp_path: Path
) -> None:
    settings = BridgeSettings(
        _env_file=None,
        bridge_mode="local-roles",
        bridge_role="executor",
        planner_post_token="xoxb-planner",
        slack_bot_token="xoxb-test",
        sessions_path=str(tmp_path / "sessions.json"),
    )
    bridge = SlackAgentBridge(settings)
    planner_handoff = AsyncMock()
    thread_key = build_thread_key("C123", "171.222")

    async def fake_collect_repo_state(cwd: Path) -> str:
        return "Branch: main"

    async def fake_run_agent_command(command_template: str, prompt: str, *, cwd: Path) -> str:
        return "Executor result"

    async def fake_post_long_message(
        client, *, channel: str, thread_ts: str, header: str, content: str
    ) -> None:
        return None

    monkeypatch.setattr(service_module, "collect_repo_state", fake_collect_repo_state)
    monkeypatch.setattr(service_module, "run_agent_command", fake_run_agent_command)
    monkeypatch.setattr(service_module, "post_long_message", fake_post_long_message)
    monkeypatch.setattr(bridge, "_run_planner_via_peer_token", planner_handoff)

    await bridge._run_executor_and_post(
        client=object(),
        channel="C123",
        thread_ts="171.222",
        thread_key=thread_key,
        planner_output="Status only.",
        continue_with_planner=False,
    )

    planner_handoff.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_planner_via_peer_token_requires_token(tmp_path: Path) -> None:
    settings = BridgeSettings(
        _env_file=None,
        bridge_mode="local-roles",
        bridge_role="executor",
        slack_bot_token="xoxb-test",
        sessions_path=str(tmp_path / "sessions.json"),
    )
    bridge = SlackAgentBridge(settings)

    with pytest.raises(RuntimeError, match="PLANNER_POST_TOKEN is required"):
        await bridge._run_planner_via_peer_token(
            channel="C123",
            thread_ts="171.222",
            thread_key=build_thread_key("C123", "171.222"),
        )


@pytest.mark.asyncio
async def test_run_specialist_via_peer_token_requires_token(tmp_path: Path) -> None:
    settings = BridgeSettings(
        _env_file=None,
        bridge_mode="local-roles",
        bridge_role="executor",
        slack_bot_token="xoxb-test",
        sessions_path=str(tmp_path / "sessions.json"),
    )
    bridge = SlackAgentBridge(settings)

    with pytest.raises(RuntimeError, match="SPECIALIST_POST_TOKEN is required"):
        await bridge._run_specialist_via_peer_token(
            channel="C123",
            thread_ts="171.222",
            thread_key=build_thread_key("C123", "171.222"),
        )


@pytest.mark.asyncio
async def test_run_codex_planner_and_post_can_delegate_to_peers(
    monkeypatch, tmp_path: Path
) -> None:
    settings = BridgeSettings(
        _env_file=None,
        bridge_mode="local-roles",
        bridge_role="executor",
        planner_post_token="xoxb-planner",
        specialist_post_token="xoxb-llama",
        planner_bot_user_id="UCLAUDE",
        specialist_bot_user_id="ULLAMA",
        slack_bot_token="xoxb-test",
        sessions_path=str(tmp_path / "sessions.json"),
    )
    bridge = SlackAgentBridge(settings)
    planner_handoff = AsyncMock()
    specialist_handoff = AsyncMock()
    thread_key = build_thread_key("C123", "171.222")

    async def fake_collect_repo_state(cwd: Path) -> str:
        return "Branch: main"

    async def fake_run_agent_command(command_template: str, prompt: str, *, cwd: Path) -> str:
        return (
            "Goal\n- Tighten the implementation plan.\n\n"
            "Technical Plan\n- Split the work into one parser change.\n\n"
            "Claude Question\n- <@UCLAUDE> confirm the success check.\n\n"
            "Llama Delegation\n- <@ULLAMA> compress the current thread into 3 bullets.\n\n"
            "Next Check\n- Wait for Claude and Llama, then execute."
        )

    async def fake_post_long_message(
        client, *, channel: str, thread_ts: str, header: str, content: str
    ) -> None:
        return None

    monkeypatch.setattr(service_module, "collect_repo_state", fake_collect_repo_state)
    monkeypatch.setattr(service_module, "run_agent_command", fake_run_agent_command)
    monkeypatch.setattr(service_module, "post_long_message", fake_post_long_message)
    monkeypatch.setattr(bridge, "_run_planner_via_peer_token", planner_handoff)
    monkeypatch.setattr(bridge, "_run_specialist_via_peer_token", specialist_handoff)

    await bridge._run_codex_planner_and_post(
        client=object(),
        channel="C123",
        thread_ts="171.222",
        thread_key=thread_key,
        prompt_source="Plan the next technical step.",
    )

    planner_handoff.assert_awaited_once_with(
        channel="C123",
        thread_ts="171.222",
        thread_key=thread_key,
    )
    specialist_handoff.assert_awaited_once_with(
        channel="C123",
        thread_ts="171.222",
        thread_key=thread_key,
    )
    assert bridge.sessions.get(thread_key)[-1].author == "Codex planner mode"
