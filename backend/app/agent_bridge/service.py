from __future__ import annotations

import asyncio
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path

from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.session_store import SessionMessage, ThreadSessionStore

PLANNER_INSTRUCTIONS = """You are Claude Code acting as the planner.

Read the Slack thread transcript and produce a compact execution handoff for Codex.
Respond with these sections only:
1. Intent
2. Plan
3. Risks
4. Handoff
Keep it concise and actionable."""

EXECUTOR_INSTRUCTIONS = """You are Codex acting as the executor.

Read the Slack thread transcript plus the planner handoff.
Respond as the execution agent with:
1. What I will do
2. What I changed or found
3. Blockers or next steps
Keep it concise and concrete."""


@dataclass(slots=True)
class AgentResult:
    name: str
    content: str


def build_thread_key(channel: str, thread_ts: str) -> str:
    return f"{channel}:{thread_ts}"


def render_transcript(messages: list[SessionMessage], *, limit: int) -> str:
    trimmed = messages[-limit:]
    chunks = [
        f"{message.created_at} | {message.author} ({message.role})\n{message.content}"
        for message in trimmed
    ]
    return "\n\n".join(chunks)


def build_planner_prompt(messages: list[SessionMessage], *, limit: int) -> str:
    return (
        f"{PLANNER_INSTRUCTIONS}\n\n"
        f"Slack thread transcript:\n{render_transcript(messages, limit=limit)}"
    )


def build_executor_prompt(
    messages: list[SessionMessage],
    planner_output: str,
    *,
    limit: int,
) -> str:
    return (
        f"{EXECUTOR_INSTRUCTIONS}\n\n"
        f"Slack thread transcript:\n{render_transcript(messages, limit=limit)}\n\n"
        f"Planner handoff:\n{planner_output}"
    )


async def run_agent_command(
    command_template: str,
    prompt: str,
    *,
    cwd: Path,
) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as output_file:
        output_path = Path(output_file.name)

    command = shlex.split(
        command_template.format(cwd=str(cwd), output_file=str(output_path))
    )
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
    )
    stdout, stderr = await process.communicate(prompt.encode("utf-8"))
    output_text = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
    output_path.unlink(missing_ok=True)

    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="ignore").strip() or stdout.decode(
            "utf-8", errors="ignore"
        ).strip()
        raise RuntimeError(message or f"Agent command failed: {' '.join(command)}")

    final_text = output_text or stdout.decode("utf-8", errors="ignore").strip()
    return final_text or "(no output)"


async def post_long_message(
    client: AsyncWebClient,
    *,
    channel: str,
    thread_ts: str,
    header: str,
    content: str,
) -> None:
    body = f"*{header}*\n{content}"
    chunks = [body[i : i + 3500] for i in range(0, len(body), 3500)] or [body]
    for chunk in chunks:
        await client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=chunk)


def is_planner_event(event: dict, settings: BridgeSettings) -> bool:
    display_name = settings.planner_display_name.strip().lower()
    username = str(event.get("username", "")).strip().lower()
    bot_name = str(event.get("bot_profile", {}).get("name", "")).strip().lower()
    user_id = str(event.get("user", "")).strip()
    bot_id = str(event.get("bot_id", "")).strip()
    return any(
        [
            settings.planner_bot_user_id and user_id == settings.planner_bot_user_id,
            settings.planner_bot_id and bot_id == settings.planner_bot_id,
            display_name and username == display_name,
            display_name and bot_name == display_name,
        ]
    )


def planner_review_suffix(settings: BridgeSettings) -> str:
    if settings.planner_bot_user_id:
        return f"<@{settings.planner_bot_user_id}> please review and plan the next step."
    return "@Claude please review and plan the next step."


def mentions_user(raw_text: str, user_id: str) -> bool:
    return bool(user_id and f"<@{user_id}>" in raw_text)


def targets_codex(
    raw_text: str,
    cleaned_text: str,
    settings: BridgeSettings,
    *,
    codex_user_id: str,
) -> bool:
    phrase = settings.codex_trigger_phrase.strip().lower()
    cleaned = cleaned_text.strip().lower()
    return any(
        [
            mentions_user(raw_text, codex_user_id),
            phrase and phrase in cleaned,
        ]
    )


def targets_planner(raw_text: str, cleaned_text: str, settings: BridgeSettings) -> bool:
    planner_name = settings.planner_display_name.strip().lower()
    cleaned = cleaned_text.strip().lower()
    return any(
        [
            mentions_user(raw_text, settings.planner_bot_user_id),
            planner_name and f"@{planner_name}" in cleaned,
        ]
    )


def thread_has_executor_activity(messages: list[SessionMessage]) -> bool:
    return any(message.role == "executor" for message in messages)


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


def should_trigger_executor(
    *,
    planner_event: bool,
    raw_text: str,
    cleaned_text: str,
    settings: BridgeSettings,
    codex_user_id: str,
    history: list[SessionMessage],
) -> bool:
    if planner_event:
        return targets_codex(raw_text, cleaned_text, settings, codex_user_id=codex_user_id)

    if targets_codex(raw_text, cleaned_text, settings, codex_user_id=codex_user_id):
        return True

    if thread_has_executor_activity(history) and not targets_planner(
        raw_text, cleaned_text, settings
    ):
        return True

    return False


class SlackAgentBridge:
    def __init__(self, settings: BridgeSettings) -> None:
        self.settings = settings
        self.sessions = ThreadSessionStore(settings.sessions_path)
        self.workdir = Path(settings.bridge_workdir)
        self.app = AsyncApp(token=settings.slack_bot_token)
        self.codex_user_id = ""
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.app.event("app_mention")
        async def handle_app_mention(body: dict, client: AsyncWebClient, logger) -> None:
            await self._handle_event(body.get("event", {}), client=client, logger=logger)

        @self.app.event("message")
        async def handle_message(body: dict, client: AsyncWebClient, logger) -> None:
            await self._handle_event(body.get("event", {}), client=client, logger=logger)

    async def _handle_event(self, event: dict, *, client: AsyncWebClient, logger) -> None:
        normalized = normalize_event_payload(event)
        if normalized is None:
            return
        event = normalized

        if self.settings.bridge_mode == "codex-follower":
            await self._handle_codex_follower_event(event, client=client, logger=logger)
            return

        if event.get("subtype") or event.get("bot_id"):
            return

        channel = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]
        user_text = self._clean_text(event.get("text", ""))
        if not user_text:
            return

        thread_key = build_thread_key(channel, thread_ts)
        self.sessions.append(thread_key, role="user", author="Human", content=user_text)
        history = self.sessions.get(thread_key)

        try:
            planner_reply = await run_agent_command(
                self.settings.planner_command,
                build_planner_prompt(history, limit=self.settings.max_history_messages),
                cwd=self.workdir,
            )
            self.sessions.append(
                thread_key,
                role="planner",
                author="Claude planner",
                content=planner_reply,
            )
            await post_long_message(
                client,
                channel=channel,
                thread_ts=thread_ts,
                header="Claude planner",
                content=planner_reply,
            )

            await self._run_executor_and_post(
                client=client,
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
                planner_output=planner_reply,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Slack agent bridge failed: %s", exc)
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"*Bridge error*\n{exc}",
            )

    async def _handle_codex_follower_event(
        self,
        event: dict,
        *,
        client: AsyncWebClient,
        logger,
    ) -> None:
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        if not channel or not thread_ts:
            return

        raw_text = event.get("text", "")
        text = self._clean_text(raw_text)
        if not text:
            return

        planner_event = is_planner_event(event, self.settings)
        if event.get("bot_id") and not planner_event:
            return
        if event.get("subtype") and not planner_event:
            return

        thread_key = build_thread_key(channel, thread_ts)
        author = "Claude planner" if planner_event else "Human"
        role = "planner" if planner_event else "user"
        self.sessions.append(thread_key, role=role, author=author, content=text)
        history = self.sessions.get(thread_key)

        if not should_trigger_executor(
            planner_event=planner_event,
            raw_text=raw_text,
            cleaned_text=text,
            settings=self.settings,
            codex_user_id=self.codex_user_id,
            history=history,
        ):
            return

        try:
            await self._run_executor_and_post(
                client=client,
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
                planner_output=text,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Codex follower bridge failed: %s", exc)
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"*Bridge error*\n{exc}",
            )

    async def _run_executor_and_post(
        self,
        *,
        client: AsyncWebClient,
        channel: str,
        thread_ts: str,
        thread_key: str,
        planner_output: str,
    ) -> None:
        executor_reply = await run_agent_command(
            self.settings.executor_command,
            build_executor_prompt(
                self.sessions.get(thread_key),
                planner_output,
                limit=self.settings.max_history_messages,
            ),
            cwd=self.workdir,
        )
        if self.settings.bridge_mode == "codex-follower":
            executor_reply = f"{executor_reply}\n\n{planner_review_suffix(self.settings)}"
        self.sessions.append(
            thread_key,
            role="executor",
            author="Codex executor",
            content=executor_reply,
        )
        await post_long_message(
            client,
            channel=channel,
            thread_ts=thread_ts,
            header="Codex executor",
            content=executor_reply,
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(part for part in text.split() if not part.startswith("<@"))

    async def run(self) -> None:
        if not self.settings.slack_bot_token or not self.settings.slack_app_token:
            raise RuntimeError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN are required")
        auth = await self.app.client.auth_test()
        self.codex_user_id = str(auth.get("user_id", ""))
        handler = AsyncSocketModeHandler(self.app, self.settings.slack_app_token)
        await handler.start_async()
