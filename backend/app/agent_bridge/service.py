from __future__ import annotations

import json
import re
import time
from pathlib import Path

from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.prompting import (
    AUTO_SPECIALIST_SUMMARY_DIRECTIVE,
    build_executor_prompt,
    build_planner_prompt,
    build_specialist_prompt,
    build_thread_key,
)
from app.agent_bridge.routing import (
    contains_trigger_phrase,
    count_role,
    detect_auto_stop_reason,
    event_author_identity,
    event_dedup_key,
    inject_known_mentions,
    looks_like_conversational_planner_request,
    looks_like_planning_request,
    looks_like_status_request,
    mentions_user,
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
    text_targets_specialist,
)
from app.agent_bridge.runtime import (
    collect_repo_state,
    extract_ollama_model,
    run_agent_command,
    run_specialist_command,
)
from app.agent_bridge.session_store import ThreadSessionStore
from app.agent_bridge.slack_io import post_long_message
from app.agent_bridge.specialist_memory import SpecialistMemoryStore
from app.database import SessionLocal
from app.services.plan_tasks import start_plan_task_from_selection

__all__ = [
    "SlackAgentBridge",
    "build_executor_prompt",
    "build_planner_prompt",
    "build_specialist_prompt",
    "build_thread_key",
    "contains_trigger_phrase",
    "count_role",
    "detect_auto_stop_reason",
    "event_author_identity",
    "event_dedup_key",
    "extract_ollama_model",
    "inject_known_mentions",
    "looks_like_conversational_planner_request",
    "looks_like_planning_request",
    "looks_like_status_request",
    "normalize_event_payload",
    "planner_review_suffix",
    "should_auto_continue_thread",
    "should_auto_summarize_for_planner",
    "should_trigger_executor",
    "should_trigger_planner",
    "should_trigger_specialist",
    "targets_codex",
    "targets_planner",
    "targets_specialist",
]


class SlackAgentBridge:
    def __init__(self, settings: BridgeSettings) -> None:
        self.settings = settings
        self.sessions = ThreadSessionStore(settings.sessions_path)
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

        @self.app.action(re.compile(r"^plan_pick_task_\d+$"))
        async def handle_plan_pick_action(ack, body: dict, logger) -> None:
            await ack()
            await self._handle_plan_pick_action(body, logger=logger)

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
        author = self.settings.planner_display_name if planner_event else "Human"
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
        latest_message = history[-1] if history else None
        conversation_mode = bool(
            latest_message
            and latest_message.role == "user"
            and looks_like_conversational_planner_request(latest_message.content)
        )
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
                conversation_mode=conversation_mode,
            ),
            cwd=self.workdir,
        )
        planner_reply = inject_known_mentions(planner_reply, self.settings)
        self.sessions.append(
            thread_key,
            role="planner",
            author=self.settings.planner_display_name,
            content=planner_reply,
        )
        await post_long_message(
            client,
            channel=channel,
            thread_ts=thread_ts,
            header=self.settings.planner_display_name,
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
        review_suffix = planner_review_suffix(self.settings)
        if (
            self.settings.bridge_mode in {"codex-follower", "local-roles"}
            and review_suffix
        ):
            executor_reply = f"{executor_reply}\n\n{review_suffix}"
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
            header="Codex",
            content=executor_reply,
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
            header="Codex",
            content=planner_reply,
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
            header=self.settings.specialist_display_name,
            content=specialist_reply,
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

    async def _handle_plan_pick_action(self, body: dict, *, logger) -> None:
        action = (body.get("actions") or [{}])[0]
        value = str(action.get("value", "")).strip()
        if not value:
            return

        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            logger.warning("Invalid plan task button payload: %s", value)
            return

        title = str(payload.get("title", "")).strip()
        if not title:
            return

        story_points_raw = payload.get("story_points")
        story_points = int(story_points_raw) if story_points_raw is not None else None
        message_ts = str((body.get("message") or {}).get("ts", "")).strip() or None

        async with SessionLocal() as session:
            await start_plan_task_from_selection(
                session,
                title=title,
                story_points=story_points,
                default_thread_ts=message_ts,
            )

    async def run(self) -> None:
        if not self.settings.slack_bot_token or not self.settings.slack_app_token:
            raise RuntimeError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN are required")
        auth = await self.app.client.auth_test()
        self.bot_user_id = str(auth.get("user_id", ""))
        handler = AsyncSocketModeHandler(self.app, self.settings.slack_app_token)
        await handler.start_async()
