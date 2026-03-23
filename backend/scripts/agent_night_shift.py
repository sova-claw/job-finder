from __future__ import annotations

import argparse
import asyncio

from app.agent_bridge.config import BridgeSettings, get_bridge_settings
from app.agent_bridge.overnight import run_overnight_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a bounded overnight planner/executor loop")
    parser.add_argument(
        "--env-file",
        default="",
        help="Optional env file path for the bot/runtime configuration.",
    )
    parser.add_argument(
        "--channel-id",
        default="",
        help="Slack channel id. Falls back to DEFAULT_AGENT_CHANNEL_ID from env.",
    )
    parser.add_argument(
        "--goal",
        default="",
        help="Night shift goal. Falls back to OVERNIGHT_GOAL from env.",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=0,
        help="Max planner/executor cycles. Falls back to OVERNIGHT_MAX_CYCLES from env.",
    )
    return parser


async def _main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = BridgeSettings(_env_file=args.env_file) if args.env_file else get_bridge_settings()

    channel_id = args.channel_id or settings.default_agent_channel_id
    if not channel_id:
        raise SystemExit("Missing Slack channel id. Set --channel-id or DEFAULT_AGENT_CHANNEL_ID.")

    goal = args.goal or settings.overnight_goal
    max_cycles = args.cycles or settings.overnight_max_cycles

    result = await run_overnight_loop(
        settings=settings,
        channel_id=channel_id,
        goal=goal,
        max_cycles=max_cycles,
    )
    print(
        f"Night shift thread={result.thread_ts} cycles={result.cycles_completed} "
        f"stop={result.stopped_reason}"
    )


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
