from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BridgeSettings(BaseSettings):
    slack_bot_token: str = ""
    slack_app_token: str = ""
    bridge_mode: Literal["orchestrator", "codex-follower", "local-roles"] = "local-roles"
    bridge_role: Literal["planner", "executor", "specialist", "both"] = "both"
    planner_command: str = "claude -p --permission-mode bypassPermissions --model sonnet"
    executor_command: str = (
        "codex exec --dangerously-bypass-approvals-and-sandbox --cd {cwd} -o {output_file}"
    )
    specialist_command: str = "ollama run llama3.2:3b"
    bridge_workdir: str = str(Path(__file__).resolve().parents[3])
    sessions_path: str = str(
        Path(__file__).resolve().parents[3] / ".codex" / "agent_bridge_sessions.json"
    )
    planner_context_path: str = str(
        Path(__file__).resolve().parents[3] / "PLANNER_CONTEXT.md"
    )
    planner_memory_path: str = str(
        Path(__file__).resolve().parents[3] / "PLANNER_MEMORY.md"
    )
    specialist_context_path: str = str(
        Path(__file__).resolve().parents[3] / "LLAMA_CONTEXT.md"
    )
    specialist_memory_path: str = str(
        Path(__file__).resolve().parents[3] / "LLAMA_MEMORY.md"
    )
    planner_bot_user_id: str = ""
    planner_bot_id: str = ""
    executor_bot_user_id: str = ""
    specialist_bot_user_id: str = ""
    planner_display_name: str = "Claude"
    specialist_display_name: str = "Llama"
    planner_trigger_phrase: str = "@Claude"
    codex_trigger_phrase: str = "@Codex"
    specialist_trigger_phrase: str = "@Llama"
    default_agent_channel_id: str = ""
    overnight_max_cycles: int = Field(default=3, ge=1, le=12)
    overnight_goal: str = (
        "Work the highest-priority unblocked task in the repo, keep tasks bounded, "
        "post progress in Slack, and stop when a real blocker or decision is needed."
    )
    max_history_messages: int = Field(default=16, ge=4, le=64)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_bridge_settings() -> BridgeSettings:
    return BridgeSettings()
