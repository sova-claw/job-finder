from __future__ import annotations

import asyncio
import hashlib
import shlex
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.planner_memory import PlannerMemoryStore
from app.agent_bridge.session_store import SessionMessage, ThreadSessionStore

PLANNER_INSTRUCTIONS = """You are Claude Code acting as the planner for this repository.

Use the provided planner context, planner memory, repo state, and Slack thread transcript.
Respond with these sections only:
1. Intent
2. Plan
3. Risks
4. Handoff
Keep it concise, continuous with prior work, and execution-ready."""

EXECUTOR_INSTRUCTIONS = """You are Codex acting as the executor for this repository.

Use the provided planner handoff, planner context, planner memory,
repo state, and Slack thread transcript.
Respond with these sections only:
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


def read_text_file(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8").strip()


async def run_text_command(command: str, *, cwd: Path) -> str:
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        return stderr.decode("utf-8", errors="ignore").strip()
    return stdout.decode("utf-8", errors="ignore").strip()


async def collect_repo_state(cwd: Path) -> str:
    branch = await run_text_command("git rev-parse --abbrev-ref HEAD", cwd=cwd)
    status = await run_text_command("git status --short", cwd=cwd)
    commits = await run_text_command("git log -3 --oneline", cwd=cwd)
    chunks = [f"Branch: {branch or 'unknown'}"]
    if commits:
        chunks.append(f"Recent commits:\n{commits}")
    if status:
        chunks.append(f"Working tree:\n{status}")
    else:
        chunks.append("Working tree: clean")
    return "\n\n".join(chunks)


def build_planner_prompt(
    messages: list[SessionMessage],
    *,
    settings: BridgeSettings,
    repo_state: str,
    limit: int,
) -> str:
    planner_context = read_text_file(settings.planner_context_path)
    planner_memory = read_text_file(settings.planner_memory_path)
    return (
        f"{PLANNER_INSTRUCTIONS}\n\n"
        f"Planner context:\n{planner_context or '(missing)'}\n\n"
        f"Planner memory:\n{planner_memory or '(missing)'}\n\n"
        f"Repo state:\n{repo_state or '(unavailable)'}\n\n"
        f"Slack thread transcript:\n{render_transcript(messages, limit=limit)}"
    )


def build_executor_prompt(
    messages: list[SessionMessage],
    planner_output: str,
    *,
    settings: BridgeSettings,
    repo_state: str,
    limit: int,
) -> str:
    planner_context = read_text_file(settings.planner_context_path)
    planner_memory = read_text_file(settings.planner_memory_path)
    return (
        f"{EXECUTOR_INSTRUCTIONS}\n\n"
        f"Planner context:\n{planner_context or '(missing)'}\n\n"
        f"Planner memory:\n{planner_memory or '(missing)'}\n\n"
        f"Repo state:\n{repo_state or '(unavailable)'}\n\n"
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
    output_text = (
        output_path.read_text(encoding="utf-8").strip()
        if output_path.exists()
        else ""
    )
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


def planner_review_suffix(settings: BridgeSettings) -> str:
    planner_mention = (
        f"<@{settings.planner_bot_user_id}>"
        if settings.planner_bot_user_id
        else settings.planner_trigger_phrase
    )
    return f"{planner_mention} please review and plan the next step."


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


def thread_has_role(messages: list[SessionMessage], role: str) -> bool:
    return any(message.role == role for message in messages)


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


class SlackAgentBridge:
    def __init__(self, settings: BridgeSettings) -> None:
        self.settings = settings
        self.sessions = ThreadSessionStore(settings.sessions_path)
        self.planner_memory = PlannerMemoryStore(settings.planner_memory_path)
        self.workdir = Path(settings.bridge_workdir)
        self.app = AsyncApp(token=settings.slack_bot_token)
        self.bot_user_id = ""
        self._recent_events: dict[str, float] = {}
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

        if self._is_duplicate_event(event):
            return

        if self.settings.bridge_mode == "local-roles" and self.settings.bridge_role != "both":
            await self._handle_dedicated_role_event(event, client=client, logger=logger)
            return

        if self.settings.bridge_mode == "local-roles":
            await self._handle_local_roles_event(event, client=client, logger=logger)
            return

        if self.settings.bridge_mode == "codex-follower":
            await self._handle_codex_follower_event(event, client=client, logger=logger)
            return

        await self._handle_orchestrator_event(event, client=client, logger=logger)

    async def _handle_orchestrator_event(
        self,
        event: dict,
        *,
        client: AsyncWebClient,
        logger,
    ) -> None:
        if event.get("subtype") or event.get("bot_id"):
            return

        channel = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]
        user_text = self._clean_text(event.get("text", ""))
        if not user_text:
            return

        thread_key = build_thread_key(channel, thread_ts)
        self.sessions.upsert(
            thread_key,
            role="user",
            author="Human",
            content=user_text,
            message_ts=str(event.get("ts", "")),
        )

        try:
            await self._run_planner_and_post(
                client=client,
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
            )
            planner_output = self._last_role_content(thread_key, "planner")
            await self._run_executor_and_post(
                client=client,
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
                planner_output=planner_output,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Slack agent bridge failed: %s", exc)
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"*Bridge error*\n{exc}",
            )

    async def _handle_local_roles_event(
        self,
        event: dict,
        *,
        client: AsyncWebClient,
        logger,
    ) -> None:
        if event.get("bot_id") or event.get("subtype"):
            return

        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        if not channel or not thread_ts:
            return

        raw_text = event.get("text", "")
        text = self._clean_text(raw_text)
        if not text:
            return

        thread_key = build_thread_key(channel, thread_ts)
        self.sessions.upsert(
            thread_key,
            role="user",
            author="Human",
            content=text,
            message_ts=str(event.get("ts", "")),
        )
        history = self.sessions.get(thread_key)

        try:
            if should_trigger_planner(
                raw_text=raw_text,
                cleaned_text=text,
                settings=self.settings,
                planner_user_id=self.settings.planner_bot_user_id,
                codex_user_id=self.settings.executor_bot_user_id,
                history=history,
            ):
                await self._run_planner_and_post(
                    client=client,
                    channel=channel,
                    thread_ts=thread_ts,
                    thread_key=thread_key,
                )
                return

            if should_trigger_executor(
                raw_text=raw_text,
                cleaned_text=text,
                settings=self.settings,
                codex_user_id=self.bot_user_id,
                planner_user_id=self.settings.planner_bot_user_id,
                history=history,
            ):
                planner_output = self._last_role_content(thread_key, "planner") or text
                await self._run_executor_and_post(
                    client=client,
                    channel=channel,
                    thread_ts=thread_ts,
                    thread_key=thread_key,
                    planner_output=planner_output,
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Local roles bridge failed: %s", exc)
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"*Bridge error*\n{exc}",
            )

    async def _handle_dedicated_role_event(
        self,
        event: dict,
        *,
        client: AsyncWebClient,
        logger,
    ) -> None:
        if event.get("bot_id") or event.get("subtype"):
            return

        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        if not channel or not thread_ts:
            return

        raw_text = event.get("text", "")
        text = self._clean_text(raw_text)
        if not text:
            return

        thread_key = build_thread_key(channel, thread_ts)
        self.sessions.upsert(
            thread_key,
            role="user",
            author="Human",
            content=text,
            message_ts=str(event.get("ts", "")),
        )
        history = self.sessions.get(thread_key)

        try:
            if self.settings.bridge_role == "planner":
                if not should_trigger_planner(
                    raw_text=raw_text,
                    cleaned_text=text,
                    settings=self.settings,
                    planner_user_id=self.bot_user_id,
                    codex_user_id=self.settings.executor_bot_user_id,
                    history=history,
                ):
                    return
                await self._run_planner_and_post(
                    client=client,
                    channel=channel,
                    thread_ts=thread_ts,
                    thread_key=thread_key,
                )
                return

            if not should_trigger_executor(
                raw_text=raw_text,
                cleaned_text=text,
                settings=self.settings,
                codex_user_id=self.bot_user_id,
                planner_user_id=self.settings.planner_bot_user_id,
                history=history,
            ):
                return

            planner_output = self._last_role_content(thread_key, "planner") or text
            await self._run_executor_and_post(
                client=client,
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
                planner_output=planner_output,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Dedicated role bridge failed: %s", exc)
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

        planner_event = (
            event.get("bot_id") == self.settings.planner_bot_id
            or mentions_user(raw_text, self.settings.planner_bot_user_id)
            or str(event.get("username", "")).strip().lower()
            == self.settings.planner_display_name.strip().lower()
        )
        if event.get("bot_id") and not planner_event:
            return
        if event.get("subtype") and not planner_event:
            return

        thread_key = build_thread_key(channel, thread_ts)
        author = "Claude planner" if planner_event else "Human"
        role = "planner" if planner_event else "user"
        self.sessions.upsert(
            thread_key,
            role=role,
            author=author,
            content=text,
            message_ts=str(event.get("ts", "")),
        )
        history = self.sessions.get(thread_key)

        if not should_trigger_executor(
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

    async def _run_planner_and_post(
        self,
        *,
        client: AsyncWebClient,
        channel: str,
        thread_ts: str,
        thread_key: str,
    ) -> None:
        repo_state = await collect_repo_state(self.workdir)
        planner_reply = await run_agent_command(
            self.settings.planner_command,
            build_planner_prompt(
                self.sessions.get(thread_key),
                settings=self.settings,
                repo_state=repo_state,
                limit=self.settings.max_history_messages,
            ),
            cwd=self.workdir,
        )
        planner_reply = inject_known_mentions(planner_reply, self.settings)
        self.sessions.append(
            thread_key,
            role="planner",
            author="Claude planner",
            content=planner_reply,
        )
        self.planner_memory.record_planner_reply(thread_key, planner_reply)
        await post_long_message(
            client,
            channel=channel,
            thread_ts=thread_ts,
            header="Claude planner",
            content=planner_reply,
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
        repo_state = await collect_repo_state(self.workdir)
        executor_reply = await run_agent_command(
            self.settings.executor_command,
            build_executor_prompt(
                self.sessions.get(thread_key),
                planner_output,
                settings=self.settings,
                repo_state=repo_state,
                limit=self.settings.max_history_messages,
            ),
            cwd=self.workdir,
        )
        executor_reply = inject_known_mentions(executor_reply, self.settings)
        self.planner_memory.record_executor_reply(thread_key, executor_reply)
        if self.settings.bridge_mode in {"codex-follower", "local-roles"}:
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

    def _last_role_content(self, thread_key: str, role: str) -> str:
        messages = self.sessions.get(thread_key)
        for message in reversed(messages):
            if message.role == role:
                return message.content
        return ""

    def _is_duplicate_event(self, event: dict) -> bool:
        now = time.monotonic()
        expiry = now - 120
        self._recent_events = {
            key: seen_at for key, seen_at in self._recent_events.items() if seen_at >= expiry
        }
        key = event_dedup_key(event)
        if key in self._recent_events:
            return True
        self._recent_events[key] = now
        return False

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(part for part in text.split() if not part.startswith("<@"))

    async def run(self) -> None:
        if not self.settings.slack_bot_token or not self.settings.slack_app_token:
            raise RuntimeError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN are required")
        auth = await self.app.client.auth_test()
        self.bot_user_id = str(auth.get("user_id", ""))
        handler = AsyncSocketModeHandler(self.app, self.settings.slack_app_token)
        await handler.start_async()
