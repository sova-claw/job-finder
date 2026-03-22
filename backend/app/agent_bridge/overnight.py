from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from slack_sdk.web.async_client import AsyncWebClient

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.service import (
    build_executor_prompt,
    build_planner_prompt,
    build_thread_key,
    collect_repo_state,
    post_long_message,
    run_agent_command,
)
from app.agent_bridge.session_store import ThreadSessionStore

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


def build_kickoff_message(goal: str, *, max_cycles: int) -> str:
    return (
        "*Night shift started*\n"
        f"Goal: {goal}\n"
        f"Max cycles: {max_cycles}\n\n"
        "Role model:\n"
        "- Nazar = CEO\n"
        "- Claude = Product Owner / PM / BA / Scrum Master\n"
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


async def run_overnight_loop(
    *,
    settings: BridgeSettings,
    channel_id: str,
    goal: str,
    max_cycles: int,
) -> OvernightLoopResult:
    if not settings.slack_bot_token:
        raise RuntimeError("SLACK_BOT_TOKEN is required for overnight Slack runs")

    client = AsyncWebClient(token=settings.slack_bot_token)
    sessions = ThreadSessionStore(settings.sessions_path)
    workdir = Path(settings.bridge_workdir)

    kickoff = await client.chat_postMessage(
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

    from app.agent_bridge.planner_memory import PlannerMemoryStore

    planner_memory = PlannerMemoryStore(settings.planner_memory_path)

    for cycle in range(1, max_cycles + 1):
        repo_state = await collect_repo_state(workdir)
        planner_reply = await run_agent_command(
            settings.planner_command,
            build_planner_prompt(
                sessions.get(thread_key),
                settings=settings,
                repo_state=repo_state,
                limit=settings.max_history_messages,
            )
            + planner_night_suffix(),
            cwd=workdir,
        )
        sessions.append(
            thread_key,
            role="planner",
            author="Claude planner",
            content=planner_reply,
        )
        planner_memory.record_planner_reply(thread_key, planner_reply)
        await post_long_message(
            client,
            channel=channel_id,
            thread_ts=thread_ts,
            header=f"Claude planner · cycle {cycle}",
            content=planner_reply,
        )

        planner_stop = detect_stop_reason(planner_reply)
        if planner_stop:
            stopped_reason = f"planner:{planner_stop}"
            break

        repo_state = await collect_repo_state(workdir)
        executor_reply = await run_agent_command(
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
        )
        sessions.append(
            thread_key,
            role="executor",
            author="Codex executor",
            content=executor_reply,
        )
        planner_memory.record_executor_reply(thread_key, executor_reply)
        await post_long_message(
            client,
            channel=channel_id,
            thread_ts=thread_ts,
            header=f"Codex executor · cycle {cycle}",
            content=executor_reply,
        )

        cycles_completed = cycle
        executor_stop = detect_stop_reason(executor_reply)
        if executor_stop:
            stopped_reason = f"executor:{executor_stop}"
            break

    await client.chat_postMessage(
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
