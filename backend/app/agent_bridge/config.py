from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BridgeSettings(BaseSettings):
    slack_bot_token: str = ""
    slack_app_token: str = ""
    planner_command: str = "claude -p --permission-mode bypassPermissions --model sonnet"
    executor_command: str = (
        "codex exec --dangerously-bypass-approvals-and-sandbox --cd {cwd} -o {output_file}"
    )
    bridge_workdir: str = str(Path(__file__).resolve().parents[3])
    sessions_path: str = str(
        Path(__file__).resolve().parents[3] / ".codex" / "agent_bridge_sessions.json"
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
