from __future__ import annotations

from pathlib import Path

from app.agent_bridge.config import BridgeSettings
from app.agent_bridge.session_store import SessionMessage

PLANNER_INSTRUCTIONS = """You are the planning assistant for this repository.

Use the provided planner context,
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

PLANNER_CONVERSATION_INSTRUCTIONS = """You are the planning assistant
for this repository.

Use the provided planner context,
repo state, and Slack thread transcript.
The latest Slack message is a direct human conversation or coaching message.
Reply like a strong human teammate first.
Rules:
- answer the person's actual question directly
- sound natural, warm, and clear
- no rigid Goal/Decision/Task template unless the thread explicitly asks for planning
- keep it short enough to scan quickly in Slack
- if useful, end with one concrete next move or offer"""

EXECUTOR_INSTRUCTIONS = """You are Codex acting as the executor for this repository.

Use the provided planner handoff, executor context, planner context,
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

Use the provided executor context, planner context,
repo state, and Slack thread transcript.
You can think technically, shape implementation steps, ask for product or priority guidance,
and delegate bounded specialist work to Llama.
Do not claim code changes unless they were actually run in this thread.
Respond with these sections only:
1. Goal
2. Technical Plan
3. Plan Note
4. Llama Delegation
5. Next Check
Rules:
- keep it concise and technical
- one bounded technical plan only
- ask for plan clarification only when priority, tradeoff, or acceptance is unclear
- delegate to Llama only for summarize, critique, or structured extraction"""

SPECIALIST_INSTRUCTIONS = """You are Llama acting as a specialist support agent for this repository.

Use the provided specialist context, specialist memory, planner context,
repo state, and Slack thread transcript.
Your role is limited to critique, summarization, and structured extraction.
Your main job is to help planning stay short and help Codex stay clear.
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
- Help define the next goal and task for this thread
- Return at most 4 short bullets
- Focus on goal, blockers, progress, and clean handoff"""


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


def build_planner_prompt(
    messages: list[SessionMessage],
    *,
    settings: BridgeSettings,
    repo_state: str,
    limit: int,
    conversation_mode: bool = False,
) -> str:
    planner_context = read_text_file(settings.planner_context_path)
    instructions = (
        PLANNER_CONVERSATION_INSTRUCTIONS if conversation_mode else PLANNER_INSTRUCTIONS
    )
    return (
        f"{instructions}\n\n"
        f"Planner context:\n{planner_context or '(missing)'}\n\n"
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
    instructions = EXECUTOR_PLANNER_INSTRUCTIONS if planner_mode else EXECUTOR_INSTRUCTIONS
    return (
        f"{instructions}\n\n"
        f"Executor context:\n{executor_context or '(missing)'}\n\n"
        f"Planner context:\n{planner_context or '(missing)'}\n\n"
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
    specialist_context = read_text_file(settings.specialist_context_path)
    specialist_memory = read_text_file(settings.specialist_memory_path)
    request_block = f"{directive.strip()}\n\n" if directive and directive.strip() else ""
    return (
        f"{SPECIALIST_INSTRUCTIONS}\n\n"
        f"{request_block}"
        f"Specialist context:\n{specialist_context or '(missing)'}\n\n"
        f"Specialist memory:\n{specialist_memory or '(missing)'}\n\n"
        f"Planner context:\n{planner_context or '(missing)'}\n\n"
        f"Repo state:\n{repo_state or '(unavailable)'}\n\n"
        f"Slack thread transcript:\n{render_transcript(messages, limit=limit)}"
    )
