from __future__ import annotations

import asyncio
import hashlib
import os
import shlex
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.goal_memory import GoalBoardStore
from app.agent_bridge.planner_memory import PlannerMemoryStore
from app.agent_bridge.session_store import SessionMessage, ThreadSessionStore
from app.agent_bridge.specialist_memory import SpecialistMemoryStore

PLANNER_INSTRUCTIONS = """You are Claude Code acting as the planner for this repository.

Use the provided planner context, planner memory, goal board,
repo state, and Slack thread transcript.
You are the driver, not the narrator.
Respond with these sections only:
1. Goal
2. Decision
3. Task
4. Success Check
5. Risks
6. Handoff
Rules:
- keep the full reply under 10 short bullets or lines
- set or refine one concrete goal for the thread
- give exactly one next task unless blocked
- no long explanations, no status recap unless needed for the decision
- success check must be observable
- make the handoff directly runnable by Codex"""

EXECUTOR_INSTRUCTIONS = """You are Codex acting as the executor for this repository.

Use the provided planner handoff, executor context, planner context, planner memory, goal board,
repo state, and Slack thread transcript.
Respond with these sections only:
1. Goal
2. What I will do
3. What I changed or found
4. Next Check
5. Blockers or next steps
Rules:
- keep it concise and concrete
- stay inside the current planner goal
- prefer one bounded move over broad rewrites"""

EXECUTOR_PLANNER_INSTRUCTIONS = """You are Codex acting in technical-planner mode
for this repository.

Use the provided executor context, planner context, planner memory, goal board,
repo state, and Slack thread transcript.
You can think technically, shape implementation steps, ask Claude for product or priority guidance,
and delegate bounded specialist work to Llama.
Do not claim code changes unless they were actually run in this thread.
Respond with these sections only:
1. Goal
2. Technical Plan
3. Claude Question
4. Llama Delegation
5. Next Check
Rules:
- keep it concise and technical
- one bounded technical plan only
- ask Claude only for priority, tradeoff, or acceptance clarification
- delegate to Llama only for summarize, critique, or structured extraction"""

SPECIALIST_INSTRUCTIONS = """You are Llama acting as a specialist support agent for this repository.

Use the provided specialist context, specialist memory, planner context, goal board,
repo state, and Slack thread transcript.
Your role is limited to critique, summarization, and structured extraction.
Your main job is to help Claude stay short and help Codex stay clear.
Do not plan the project or make code changes.
Respond with these sections only:
1. Mode
2. Findings
3. Recommended handoff
Rules:
- keep the reply under 6 short bullets or lines
- compress, do not expand
- prefer blind spots, extracted facts, and cleaner handoffs over commentary"""

AUTO_SPECIALIST_SUMMARY_DIRECTIVE = """Current request:
- Mode: Summarize
- Help Claude set the next goal and task for this thread
- Return at most 4 short bullets
- Focus on goal, blockers, progress, and clean handoff"""

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
    goal_board = read_text_file(settings.planner_goals_path)
    return (
        f"{PLANNER_INSTRUCTIONS}\n\n"
        f"Planner context:\n{planner_context or '(missing)'}\n\n"
        f"Planner memory:\n{planner_memory or '(missing)'}\n\n"
        f"Goal board:\n{goal_board or '(missing)'}\n\n"
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
    planner_mode: bool = False,
) -> str:
    executor_context = read_text_file(settings.executor_context_path)
    planner_context = read_text_file(settings.planner_context_path)
    planner_memory = read_text_file(settings.planner_memory_path)
    goal_board = read_text_file(settings.planner_goals_path)
    instructions = EXECUTOR_PLANNER_INSTRUCTIONS if planner_mode else EXECUTOR_INSTRUCTIONS
    return (
        f"{instructions}\n\n"
        f"Executor context:\n{executor_context or '(missing)'}\n\n"
        f"Planner context:\n{planner_context or '(missing)'}\n\n"
        f"Planner memory:\n{planner_memory or '(missing)'}\n\n"
        f"Goal board:\n{goal_board or '(missing)'}\n\n"
        f"Repo state:\n{repo_state or '(unavailable)'}\n\n"
        f"Slack thread transcript:\n{render_transcript(messages, limit=limit)}\n\n"
        f"Planner handoff:\n{planner_output}"
    )


def build_specialist_prompt(
    messages: list[SessionMessage],
    *,
    settings: BridgeSettings,
    repo_state: str,
    limit: int,
    directive: str | None = None,
) -> str:
    planner_context = read_text_file(settings.planner_context_path)
    goal_board = read_text_file(settings.planner_goals_path)
    specialist_context = read_text_file(settings.specialist_context_path)
    specialist_memory = read_text_file(settings.specialist_memory_path)
    request_block = f"{directive.strip()}\n\n" if directive and directive.strip() else ""
    return (
        f"{SPECIALIST_INSTRUCTIONS}\n\n"
        f"{request_block}"
        f"Specialist context:\n{specialist_context or '(missing)'}\n\n"
        f"Specialist memory:\n{specialist_memory or '(missing)'}\n\n"
        f"Planner context:\n{planner_context or '(missing)'}\n\n"
        f"Goal board:\n{goal_board or '(missing)'}\n\n"
        f"Repo state:\n{repo_state or '(unavailable)'}\n\n"
        f"Slack thread transcript:\n{render_transcript(messages, limit=limit)}"
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


def extract_ollama_model(command_template: str) -> str | None:
    template = command_template.strip()
    if template.startswith("ollama-api:"):
        model = template.split(":", 1)[1].strip()
        return model or None

    parts = shlex.split(template)
    if len(parts) >= 3 and parts[0] == "ollama" and parts[1] == "run":
        return parts[2]
    return None


async def run_specialist_command(
    command_template: str,
    prompt: str,
    *,
    cwd: Path,
    ollama_host: str,
) -> str:
    model = extract_ollama_model(command_template)
    if not model:
        return await run_agent_command(command_template, prompt, cwd=cwd)

    base_url = os.environ.get("OLLAMA_HOST", ollama_host).rstrip("/")
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
    content = str(payload.get("response", "")).strip()
    return content or "(no output)"


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
        return "planner", "Claude planner"
    if user_id and user_id == settings.executor_bot_user_id:
        return "executor", "Codex executor"
    if user_id and user_id == settings.specialist_bot_user_id:
        return "specialist", f"{settings.specialist_display_name} specialist"
    if username_lower == settings.planner_display_name.strip().lower():
        return "planner", "Claude planner"
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


class SlackAgentBridge:
    def __init__(self, settings: BridgeSettings) -> None:
        self.settings = settings
        self.sessions = ThreadSessionStore(settings.sessions_path)
        self.planner_memory = PlannerMemoryStore(settings.planner_memory_path)
        self.goal_board = GoalBoardStore(settings.planner_goals_path)
        self.specialist_memory = SpecialistMemoryStore(settings.specialist_memory_path)
        self.workdir = Path(settings.bridge_workdir)
        self.app = AsyncApp(token=settings.slack_bot_token)
        self.bot_user_id = ""
        self._recent_events: dict[str, float] = {}
        self._register_handlers()

    def _is_current_bot_role_event(self, event: dict, author_role: str) -> bool:
        if not event.get("bot_id"):
            return False
        if self.settings.bridge_role == "planner":
            return author_role == "planner"
        if self.settings.bridge_role == "executor":
            return author_role == "executor"
        if self.settings.bridge_role == "specialist":
            return author_role == "specialist"
        if self.settings.bridge_role == "both":
            return author_role in {"planner", "executor", "specialist"}
        return False

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
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        if not channel or not thread_ts:
            return

        raw_text = event.get("text", "")
        text = self._clean_text(raw_text)
        if not text:
            return

        author_role, author_name = event_author_identity(
            event,
            self.settings,
            self_bot_user_id=self.bot_user_id,
        )
        if author_role == "self" or self._is_current_bot_role_event(event, author_role):
            return

        thread_key = build_thread_key(channel, thread_ts)
        self.sessions.upsert(
            thread_key,
            role="user" if author_role == "bot" else author_role,
            author=author_name,
            content=text,
            message_ts=str(event.get("ts", "")),
        )
        history = self.sessions.get(thread_key)

        try:
            if should_trigger_specialist(
                raw_text=raw_text,
                cleaned_text=text,
                settings=self.settings,
                specialist_user_id=self.settings.specialist_bot_user_id,
                planner_user_id=self.settings.planner_bot_user_id,
                codex_user_id=self.settings.executor_bot_user_id,
                history=history,
            ):
                await self._run_specialist_and_post(
                    client=client,
                    channel=channel,
                    thread_ts=thread_ts,
                    thread_key=thread_key,
                )
                return

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
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        if not channel or not thread_ts:
            return

        raw_text = event.get("text", "")
        text = self._clean_text(raw_text)
        if not text:
            return

        author_role, author_name = event_author_identity(
            event,
            self.settings,
            self_bot_user_id=self.bot_user_id,
        )
        if author_role == "self" or self._is_current_bot_role_event(event, author_role):
            return

        thread_key = build_thread_key(channel, thread_ts)
        self.sessions.upsert(
            thread_key,
            role="user" if author_role == "bot" else author_role,
            author=author_name,
            content=text,
            message_ts=str(event.get("ts", "")),
        )
        history = self.sessions.get(thread_key)

        try:
            if self.settings.bridge_role == "planner":
                if author_role in {"executor", "specialist"}:
                    return
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

            if self.settings.bridge_role == "specialist":
                if not should_trigger_specialist(
                    raw_text=raw_text,
                    cleaned_text=text,
                    settings=self.settings,
                    specialist_user_id=self.bot_user_id,
                    planner_user_id=self.settings.planner_bot_user_id,
                    codex_user_id=self.settings.executor_bot_user_id,
                    history=history,
                ):
                    return
                await self._run_specialist_and_post(
                    client=client,
                    channel=channel,
                    thread_ts=thread_ts,
                    thread_key=thread_key,
                )
                return

            if author_role == "executor" and targets_planner(
                raw_text,
                text,
                self.settings,
                planner_user_id=self.settings.planner_bot_user_id,
            ):
                await self._run_planner_via_peer_token(
                    channel=channel,
                    thread_ts=thread_ts,
                    thread_key=thread_key,
                )
                return

            if author_role == "specialist" and targets_planner(
                raw_text,
                text,
                self.settings,
                planner_user_id=self.settings.planner_bot_user_id,
            ):
                await self._run_planner_via_peer_token(
                    channel=channel,
                    thread_ts=thread_ts,
                    thread_key=thread_key,
                )
                return

            if author_role == "executor" and targets_specialist(
                raw_text,
                text,
                self.settings,
                specialist_user_id=self.settings.specialist_bot_user_id,
            ):
                await self._run_specialist_via_peer_token(
                    channel=channel,
                    thread_ts=thread_ts,
                    thread_key=thread_key,
                )
                return

            if author_role == "planner":
                if not should_auto_continue_thread(
                    history,
                    max_cycles=self.settings.auto_thread_max_cycles,
                    latest_text=text,
                ):
                    return
                await self._run_executor_and_post(
                    client=client,
                    channel=channel,
                    thread_ts=thread_ts,
                    thread_key=thread_key,
                    planner_output=text,
                    continue_with_planner=True,
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
            if looks_like_planning_request(text):
                await self._run_codex_planner_and_post(
                    client=client,
                    channel=channel,
                    thread_ts=thread_ts,
                    thread_key=thread_key,
                    prompt_source=planner_output,
                )
                return
            should_continue = (
                not looks_like_status_request(text)
                and bool(self._last_role_content(thread_key, "planner"))
                and should_auto_continue_thread(
                    history,
                    max_cycles=self.settings.auto_thread_max_cycles,
                    latest_text=text,
                )
            )
            await self._run_executor_and_post(
                client=client,
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
                planner_output=planner_output,
                continue_with_planner=should_continue,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Dedicated role bridge failed: %s", exc)
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"*Bridge error*\n{exc}",
            )

    async def _run_planner_via_peer_token(
        self,
        *,
        channel: str,
        thread_ts: str,
        thread_key: str,
    ) -> None:
        if not self.settings.planner_post_token:
            raise RuntimeError("PLANNER_POST_TOKEN is required for peer planner handoff")
        peer_client = AsyncWebClient(token=self.settings.planner_post_token)
        await self._run_planner_and_post(
            client=peer_client,
            channel=channel,
            thread_ts=thread_ts,
            thread_key=thread_key,
        )

    async def _run_specialist_via_peer_token(
        self,
        *,
        channel: str,
        thread_ts: str,
        thread_key: str,
    ) -> None:
        if not self.settings.specialist_post_token:
            raise RuntimeError("SPECIALIST_POST_TOKEN is required for peer specialist handoff")
        peer_client = AsyncWebClient(token=self.settings.specialist_post_token)
        await self._run_specialist_and_post(
            client=peer_client,
            channel=channel,
            thread_ts=thread_ts,
            thread_key=thread_key,
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
            codex_user_id=self.settings.executor_bot_user_id or self.bot_user_id,
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
        history = self.sessions.get(thread_key)
        if should_auto_summarize_for_planner(
            history,
            threshold=self.settings.auto_specialist_summary_threshold,
        ):
            await self._run_specialist_and_post(
                client=client,
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
                directive=AUTO_SPECIALIST_SUMMARY_DIRECTIVE,
            )
            history = self.sessions.get(thread_key)
        planner_reply = await run_agent_command(
            self.settings.planner_command,
            build_planner_prompt(
                history,
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
        self.goal_board.record_planner_reply(thread_key, planner_reply)
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
        continue_with_planner: bool = False,
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
        self.goal_board.record_executor_reply(thread_key, executor_reply)
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
        if (
            continue_with_planner
            and self.settings.bridge_role == "executor"
            and self.settings.planner_post_token
            and not detect_auto_stop_reason(executor_reply)
        ):
            await self._run_planner_via_peer_token(
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
            )
        if (
            self.settings.bridge_role == "executor"
            and self.settings.specialist_post_token
            and text_targets_specialist(executor_reply, self.settings)
        ):
            await self._run_specialist_via_peer_token(
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
            )

    async def _run_codex_planner_and_post(
        self,
        *,
        client: AsyncWebClient,
        channel: str,
        thread_ts: str,
        thread_key: str,
        prompt_source: str,
    ) -> None:
        repo_state = await collect_repo_state(self.workdir)
        planner_reply = await run_agent_command(
            self.settings.executor_command,
            build_executor_prompt(
                self.sessions.get(thread_key),
                prompt_source,
                settings=self.settings,
                repo_state=repo_state,
                limit=self.settings.max_history_messages,
                planner_mode=True,
            ),
            cwd=self.workdir,
        )
        planner_reply = inject_known_mentions(planner_reply, self.settings)
        self.sessions.append(
            thread_key,
            role="executor",
            author="Codex planner mode",
            content=planner_reply,
        )
        await post_long_message(
            client,
            channel=channel,
            thread_ts=thread_ts,
            header="Codex planner mode",
            content=planner_reply,
        )
        if self.settings.planner_post_token and text_targets_planner(planner_reply, self.settings):
            await self._run_planner_via_peer_token(
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
            )
        if (
            self.settings.specialist_post_token
            and text_targets_specialist(planner_reply, self.settings)
        ):
            await self._run_specialist_via_peer_token(
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
            )

    async def _run_specialist_and_post(
        self,
        *,
        client: AsyncWebClient,
        channel: str,
        thread_ts: str,
        thread_key: str,
        directive: str | None = None,
    ) -> None:
        repo_state = await collect_repo_state(self.workdir)
        specialist_prompt = build_specialist_prompt(
            self.sessions.get(thread_key),
            settings=self.settings,
            repo_state=repo_state,
            limit=self.settings.max_history_messages,
            directive=directive,
        )
        specialist_reply = await run_specialist_command(
            self.settings.specialist_command,
            specialist_prompt,
            cwd=self.workdir,
            ollama_host=self.settings.specialist_ollama_host,
        )
        specialist_reply = inject_known_mentions(specialist_reply, self.settings)
        self.specialist_memory.record_specialist_reply(thread_key, specialist_reply)
        self.sessions.append(
            thread_key,
            role="specialist",
            author=f"{self.settings.specialist_display_name} specialist",
            content=specialist_reply,
        )
        await post_long_message(
            client,
            channel=channel,
            thread_ts=thread_ts,
            header=f"{self.settings.specialist_display_name} specialist",
            content=specialist_reply,
        )
        if (
            self.settings.bridge_role == "specialist"
            and self.settings.planner_post_token
            and text_targets_planner(specialist_reply, self.settings)
        ):
            await self._run_planner_via_peer_token(
                channel=channel,
                thread_ts=thread_ts,
                thread_key=thread_key,
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
