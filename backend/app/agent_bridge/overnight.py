from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from slack_sdk.web.async_client import AsyncWebClient

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.prompting import (
    build_executor_prompt,
    build_planner_prompt,
    build_thread_key,
)
from app.agent_bridge.runtime import (
    collect_repo_state,
    run_agent_command,
)
from app.agent_bridge.session_store import ThreadSessionStore
from app.agent_bridge.slack_io import post_long_message

STOP_PHRASES = [
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
class OvernightLoopResult:
    thread_ts: str
    cycles_completed: int
    stopped_reason: str


@dataclass(slots=True)
class OvernightClients:
    kickoff: AsyncWebClient
    planner: AsyncWebClient
    executor: AsyncWebClient
    specialist: AsyncWebClient | None = None


@dataclass(slots=True)
class TimedAgentResult:
    content: str
    timed_out: bool = False


def build_kickoff_message(goal: str, *, max_cycles: int) -> str:
    return (
        "*Night shift started*\n"
        f"Goal: {goal}\n"
        f"Max cycles: {max_cycles}\n\n"
        "Role model:\n"
        "- Nazar = CEO\n"
        "- Planning = product direction and review\n"
        "- Codex = Tech Lead / Super Senior executor\n\n"
        "This thread is autonomous until a blocker or decision is needed."
    )


def planner_night_suffix() -> str:
    return (
        "\n\nNight shift rules:\n"
        "- Choose one bounded next task only.\n"
        "- Prefer highest-leverage, low-risk progress.\n"
        "- If a real product decision is needed, say so clearly in Risks.\n"
        "- Keep the handoff directly executable by Codex."
    )


def executor_night_suffix() -> str:
    return (
        "\n\nNight shift rules:\n"
        "- Execute one bounded task from the planner handoff.\n"
        "- Run validation when code changes are made.\n"
        "- Commit and push if the task is completed safely.\n"
        "- If blocked or a decision is required, say so clearly in "
        "'Blockers or next steps'."
    )


def detect_stop_reason(text: str) -> str | None:
    lowered = text.lower()
    for phrase in STOP_PHRASES:
        if phrase in lowered:
            return phrase
    return None


def build_cycle_summary(
    *,
    cycle: int,
    max_cycles: int,
    status: str,
    executor_reply: str,
) -> str:
    compact = " ".join(line.strip() for line in executor_reply.splitlines() if line.strip())
    if len(compact) > 80:
        compact = compact[:79].rstrip() + "…"
    return f"Cycle {cycle}/{max_cycles}: {status} - {compact or '(no executor output)'}"


def build_overnight_clients(settings: BridgeSettings) -> OvernightClients:
    if not settings.slack_bot_token:
        raise RuntimeError("SLACK_BOT_TOKEN is required for overnight Slack runs")

    executor_client = AsyncWebClient(token=settings.slack_bot_token)
    planner_client = (
        AsyncWebClient(token=settings.planner_post_token)
        if settings.planner_post_token
        else executor_client
    )
    specialist_client = (
        AsyncWebClient(token=settings.specialist_post_token)
        if settings.specialist_post_token
        else None
    )
    return OvernightClients(
        kickoff=executor_client,
        planner=planner_client,
        executor=executor_client,
        specialist=specialist_client,
    )


async def run_timed_agent_command(
    command: str,
    prompt: str,
    *,
    cwd: Path,
    timeout_seconds: int,
) -> TimedAgentResult:
    try:
        content = await asyncio.wait_for(
            run_agent_command(command, prompt, cwd=cwd),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        return TimedAgentResult(
            content=(
                "Blockers or next steps\n"
                f"- Timed out after {timeout_seconds}s while waiting for the agent command."
            ),
            timed_out=True,
        )
    return TimedAgentResult(content=content)


async def run_overnight_loop(
    *,
    settings: BridgeSettings,
    channel_id: str,
    goal: str,
    max_cycles: int,
) -> OvernightLoopResult:
    clients = build_overnight_clients(settings)
    sessions = ThreadSessionStore(settings.sessions_path)
    workdir = Path(settings.bridge_workdir)

    kickoff = await clients.kickoff.chat_postMessage(
        channel=channel_id,
        text=build_kickoff_message(goal, max_cycles=max_cycles),
    )
    thread_ts = str(kickoff["ts"])
    thread_key = build_thread_key(channel_id, thread_ts)
    sessions.upsert(
        thread_key,
        role="user",
        author="Nazar CEO",
        content=goal,
        message_ts=thread_ts,
    )

    cycles_completed = 0
    stopped_reason = "max_cycles_reached"

    for cycle in range(1, max_cycles + 1):
        repo_state = await collect_repo_state(workdir)
        planner_result = await run_timed_agent_command(
            settings.planner_command,
            build_planner_prompt(
                sessions.get(thread_key),
                settings=settings,
                repo_state=repo_state,
                limit=settings.max_history_messages,
            )
            + planner_night_suffix(),
            cwd=workdir,
            timeout_seconds=settings.overnight_planner_timeout_seconds,
        )
        planner_reply = planner_result.content
        sessions.append(
            thread_key,
            role="planner",
            author=settings.planner_display_name,
            content=planner_reply,
        )
        await post_long_message(
            clients.planner,
            channel=channel_id,
            thread_ts=thread_ts,
            header=f"{settings.planner_display_name} · cycle {cycle}",
            content=planner_reply,
        )

        planner_stop = detect_stop_reason(planner_reply)
        if planner_result.timed_out:
            stopped_reason = "planner:timeout"
            break
        if planner_stop:
            stopped_reason = f"planner:{planner_stop}"
            break

        repo_state = await collect_repo_state(workdir)
        executor_result = await run_timed_agent_command(
            settings.executor_command,
            build_executor_prompt(
                sessions.get(thread_key),
                planner_reply,
                settings=settings,
                repo_state=repo_state,
                limit=settings.max_history_messages,
            )
            + executor_night_suffix(),
            cwd=workdir,
            timeout_seconds=settings.overnight_executor_timeout_seconds,
        )
        executor_reply = executor_result.content
        sessions.append(
            thread_key,
            role="executor",
            author="Codex executor",
            content=executor_reply,
        )
        await post_long_message(
            clients.executor,
            channel=channel_id,
            thread_ts=thread_ts,
            header=f"Codex · cycle {cycle}",
            content=executor_reply,
        )

        cycles_completed = cycle
        executor_stop = detect_stop_reason(executor_reply)
        await clients.executor.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=build_cycle_summary(
                cycle=cycle,
                max_cycles=max_cycles,
                status=executor_stop or "continuing",
                executor_reply=executor_reply,
            ),
        )
        if executor_result.timed_out:
            stopped_reason = "executor:timeout"
            break
        if executor_stop:
            stopped_reason = f"executor:{executor_stop}"
            break

    await clients.kickoff.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=(
            "*Night shift finished*\n"
            f"Cycles completed: {cycles_completed}\n"
            f"Stop reason: {stopped_reason}"
        ),
    )

    return OvernightLoopResult(
        thread_ts=thread_ts,
        cycles_completed=cycles_completed,
        stopped_reason=stopped_reason,
    )
