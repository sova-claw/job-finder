from __future__ import annotations

from slack_sdk.web.async_client import AsyncWebClient


async def post_long_message(
    client: AsyncWebClient,
    *,
    channel: str,
    thread_ts: str,
    header: str,
    content: str,
) -> None:
    body = f"*{header}*\n{content}"
    chunks = [body[i : i + 3500] for i in range(0, len(body), 3500)] or [body]
    for chunk in chunks:
        await client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=chunk)
