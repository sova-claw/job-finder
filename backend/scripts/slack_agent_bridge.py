from __future__ import annotations

import asyncio

from app.agent_bridge import SlackAgentBridge, get_bridge_settings


def main() -> None:
    settings = get_bridge_settings()
    bridge = SlackAgentBridge(settings)
    asyncio.run(bridge.run())


if __name__ == "__main__":
    main()
