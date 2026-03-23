from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class BridgeSettings(BaseSettings):
    slack_bot_token: str = ""
    slack_app_token: str = ""
    bridge_mode: Literal["orchestrator", "codex-follower", "local-roles"] = "local-roles"
    bridge_role: Literal["planner", "executor", "specialist", "both"] = "both"
    planner_command: str = "claude -p --permission-mode bypassPermissions --model sonnet"
    executor_command: str = (
        "codex exec --dangerously-bypass-approvals-and-sandbox --cd {cwd} -o {output_file}"
    )
    specialist_command: str = "ollama-api:qwen3.5:9b"
    specialist_ollama_host: str = "http://127.0.0.1:11434"
    bridge_workdir: str = str(ROOT)
    sessions_path: str = str(
        ROOT / ".codex" / "agent_bridge_sessions.json"
    )
    planner_context_path: str = str(
        ROOT / "agents" / "claude" / "CONTEXT.md"
    )
    planner_memory_path: str = str(
        ROOT / "agents" / "claude" / "MEMORY.md"
    )
    planner_goals_path: str = str(
        ROOT / "agents" / "claude" / "GOALS.md"
    )
    executor_context_path: str = str(
        ROOT / "agents" / "codex" / "CONTEXT.md"
    )
    specialist_context_path: str = str(
        ROOT / "agents" / "llama" / "CONTEXT.md"
    )
    specialist_memory_path: str = str(
        ROOT / "agents" / "llama" / "MEMORY.md"
    )
    planner_bot_user_id: str = ""
    planner_bot_id: str = ""
    planner_post_token: str = ""
    executor_bot_user_id: str = ""
    specialist_bot_user_id: str = ""
    specialist_post_token: str = ""
    planner_display_name: str = "Claude"
    executor_display_name: str = "Codex"
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
    auto_thread_max_cycles: int = Field(default=2, ge=0, le=6)
    auto_specialist_summary_threshold: int = Field(default=10, ge=0, le=64)
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
