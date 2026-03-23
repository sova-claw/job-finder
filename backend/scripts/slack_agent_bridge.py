from __future__ import annotations

import argparse
import asyncio

from app.agent_bridge import BridgeSettings, SlackAgentBridge, get_bridge_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Slack agent bridge")
    parser.add_argument(
        "--env-file",
        default="",
        help="Optional env file path for a dedicated bot runtime.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = (
        BridgeSettings(_env_file=args.env_file)
        if args.env_file
        else get_bridge_settings()
    )
    bridge = SlackAgentBridge(settings)
    asyncio.run(bridge.run())


if __name__ == "__main__":
    main()
