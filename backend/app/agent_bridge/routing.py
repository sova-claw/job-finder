from __future__ import annotations

import hashlib

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.session_store import SessionMessage

AUTO_STOP_PHRASES = [
    "@nazar [decision needed]",
    "blocked:",
    "cannot continue without",
    "blocked",
    "cannot continue",
    "can't continue",
    "need clarification",
    "requires clarification",
    "waiting on",
]


def planner_review_suffix(settings: BridgeSettings) -> str:
    del settings
    return ""


def text_targets_planner(text: str, settings: BridgeSettings) -> bool:
    planner_mention = (
        f"<@{settings.planner_bot_user_id}>"
        if settings.planner_bot_user_id
        else settings.planner_trigger_phrase
    )
    return planner_mention in text or settings.planner_trigger_phrase in text


def text_targets_specialist(text: str, settings: BridgeSettings) -> bool:
    specialist_mention = (
        f"<@{settings.specialist_bot_user_id}>"
        if settings.specialist_bot_user_id
        else settings.specialist_trigger_phrase
    )
    return specialist_mention in text or settings.specialist_trigger_phrase in text


def inject_known_mentions(text: str, settings: BridgeSettings) -> str:
    updated = text
    if settings.planner_bot_user_id:
        updated = updated.replace(
            settings.planner_trigger_phrase,
            f"<@{settings.planner_bot_user_id}>",
        )
    if settings.executor_bot_user_id:
        updated = updated.replace(
            settings.codex_trigger_phrase,
            f"<@{settings.executor_bot_user_id}>",
        )
    if settings.specialist_bot_user_id:
        updated = updated.replace(
            settings.specialist_trigger_phrase,
            f"<@{settings.specialist_bot_user_id}>",
        )
    return updated


def mentions_user(raw_text: str, user_id: str) -> bool:
    return bool(user_id and f"<@{user_id}>" in raw_text)


def contains_trigger_phrase(cleaned_text: str, trigger_phrase: str) -> bool:
    phrase = trigger_phrase.strip().lower()
    return bool(phrase and phrase in cleaned_text.strip().lower())


def targets_codex(
    raw_text: str,
    cleaned_text: str,
    settings: BridgeSettings,
    *,
    codex_user_id: str,
) -> bool:
    return any(
        [
            mentions_user(raw_text, codex_user_id),
            contains_trigger_phrase(cleaned_text, settings.codex_trigger_phrase),
        ]
    )


def targets_planner(
    raw_text: str,
    cleaned_text: str,
    settings: BridgeSettings,
    *,
    planner_user_id: str | None = None,
) -> bool:
    user_id = planner_user_id if planner_user_id is not None else settings.planner_bot_user_id
    return any(
        [
            mentions_user(raw_text, user_id),
            contains_trigger_phrase(cleaned_text, settings.planner_trigger_phrase),
        ]
    )


def targets_specialist(
    raw_text: str,
    cleaned_text: str,
    settings: BridgeSettings,
    *,
    specialist_user_id: str | None = None,
) -> bool:
    user_id = (
        specialist_user_id
        if specialist_user_id is not None
        else settings.specialist_bot_user_id
    )
    return any(
        [
            mentions_user(raw_text, user_id),
            contains_trigger_phrase(cleaned_text, settings.specialist_trigger_phrase),
        ]
    )


def thread_has_role(messages: list[SessionMessage], role: str) -> bool:
    return any(message.role == role for message in messages)


def count_role(messages: list[SessionMessage], role: str) -> int:
    return sum(1 for message in messages if message.role == role)


def detect_auto_stop_reason(text: str) -> str | None:
    lowered = text.lower()
    for phrase in AUTO_STOP_PHRASES:
        if phrase in lowered:
            return phrase
    return None


def looks_like_status_request(text: str) -> bool:
    lowered = text.strip().lower()
    return any(
        phrase in lowered
        for phrase in [
            "status",
            "blocker",
            "blockers",
            "what changed",
            "what can you do",
            "where are we",
            "progress",
        ]
    )


def looks_like_planning_request(text: str) -> bool:
    lowered = text.strip().lower()
    return any(
        phrase in lowered
        for phrase in [
            "plan",
            "think",
            "discover",
            "design",
            "options",
            "delegate",
            "how should",
            "what should",
            "investigate",
        ]
    )


def looks_like_conversational_planner_request(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    if looks_like_planning_request(lowered):
        return False
    if any(
        phrase in lowered
        for phrase in [
            "talk with me",
            "as human",
            "human first",
            "speak like human",
            "speak normally",
            "not robot",
            "not robotic",
            "too robotic",
        ]
    ):
        return True
    if lowered.endswith("?"):
        return True
    return any(
        lowered.startswith(prefix)
        for prefix in [
            "hi",
            "hello",
            "hey",
            "what",
            "how",
            "why",
            "can you",
            "could you",
            "do you",
            "are you",
            "where",
            "when",
        ]
    )


def should_auto_continue_thread(
    messages: list[SessionMessage],
    *,
    max_cycles: int,
    latest_text: str,
) -> bool:
    if max_cycles <= 0:
        return False
    if detect_auto_stop_reason(latest_text):
        return False
    return count_role(messages, "executor") < max_cycles


def should_auto_summarize_for_planner(
    messages: list[SessionMessage],
    *,
    threshold: int,
) -> bool:
    if threshold <= 0 or len(messages) < threshold:
        return False
    recent_roles = [message.role for message in messages[-3:]]
    return "specialist" not in recent_roles


def event_author_identity(
    event: dict,
    settings: BridgeSettings,
    *,
    self_bot_user_id: str,
) -> tuple[str, str]:
    user_id = str(event.get("user") or "")
    username = str(
        event.get("username")
        or (event.get("bot_profile") or {}).get("name")
        or ""
    ).strip()
    username_lower = username.lower()

    if user_id and user_id == self_bot_user_id:
        return "self", "Self bot"
    if user_id and user_id == settings.planner_bot_user_id:
        return "planner", f"{settings.planner_display_name} note"
    if user_id and user_id == settings.executor_bot_user_id:
        return "executor", "Codex executor"
    if user_id and user_id == settings.specialist_bot_user_id:
        return "specialist", f"{settings.specialist_display_name} specialist"
    if username_lower == settings.planner_display_name.strip().lower():
        return "planner", f"{settings.planner_display_name} note"
    if username_lower == settings.executor_display_name.strip().lower():
        return "executor", "Codex executor"
    if username_lower == settings.specialist_display_name.strip().lower():
        return "specialist", f"{settings.specialist_display_name} specialist"
    if event.get("bot_id"):
        return "bot", username or "Slack bot"
    return "user", "Human"


def normalize_event_payload(event: dict) -> dict | None:
    subtype = event.get("subtype")
    if subtype in {"message_changed", "message_replied"}:
        nested = event.get("message") or {}
        if not isinstance(nested, dict):
            return None
        merged = dict(nested)
        merged.setdefault("channel", event.get("channel"))
        merged.setdefault("hidden", event.get("hidden"))
        return merged
    return event


def event_dedup_key(event: dict) -> str:
    digest = hashlib.sha1(
        "|".join(
            [
                str(event.get("channel", "")),
                str(event.get("thread_ts") or event.get("ts") or ""),
                str(event.get("ts", "")),
                str(event.get("user") or event.get("bot_id") or ""),
                str(event.get("subtype", "")),
                str(event.get("text", "")),
            ]
        ).encode("utf-8")
    ).hexdigest()
    return digest


def should_trigger_executor(
    *,
    raw_text: str,
    cleaned_text: str,
    settings: BridgeSettings,
    codex_user_id: str,
    planner_user_id: str | None = None,
    history: list[SessionMessage],
) -> bool:
    if targets_codex(raw_text, cleaned_text, settings, codex_user_id=codex_user_id):
        return True

    if thread_has_role(history, "executor") and not targets_planner(
        raw_text,
        cleaned_text,
        settings,
        planner_user_id=planner_user_id,
    ):
        return True

    return False


def should_trigger_planner(
    *,
    raw_text: str,
    cleaned_text: str,
    settings: BridgeSettings,
    planner_user_id: str | None = None,
    codex_user_id: str = "",
    history: list[SessionMessage],
) -> bool:
    if targets_planner(
        raw_text,
        cleaned_text,
        settings,
        planner_user_id=planner_user_id,
    ):
        return True

    if thread_has_role(history, "planner") and not targets_codex(
        raw_text,
        cleaned_text,
        settings,
        codex_user_id=codex_user_id,
    ):
        return True

    return False


def should_trigger_specialist(
    *,
    raw_text: str,
    cleaned_text: str,
    settings: BridgeSettings,
    specialist_user_id: str | None = None,
    planner_user_id: str | None = None,
    codex_user_id: str = "",
    history: list[SessionMessage],
) -> bool:
    if targets_specialist(
        raw_text,
        cleaned_text,
        settings,
        specialist_user_id=specialist_user_id,
    ):
        return True

    if thread_has_role(history, "specialist") and not targets_planner(
        raw_text,
        cleaned_text,
        settings,
        planner_user_id=planner_user_id,
    ) and not targets_codex(
        raw_text,
        cleaned_text,
        settings,
        codex_user_id=codex_user_id,
    ):
        return True

    return False
