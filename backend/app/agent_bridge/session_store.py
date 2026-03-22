from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class SessionMessage:
    role: str
    author: str
    content: str
    created_at: str
    message_ts: str = ""


class ThreadSessionStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, list[SessionMessage]]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            key: [SessionMessage(**message) for message in messages]
            for key, messages in payload.items()
        }

    def get(self, thread_key: str) -> list[SessionMessage]:
        return self.load().get(thread_key, [])

    def append(
        self,
        thread_key: str,
        *,
        role: str,
        author: str,
        content: str,
        message_ts: str = "",
    ) -> None:
        sessions = self.load()
        sessions.setdefault(thread_key, []).append(
            SessionMessage(
                role=role,
                author=author,
                content=content,
                created_at=datetime.now(UTC).isoformat(),
                message_ts=message_ts,
            )
        )
        self._write(sessions)

    def upsert(
        self,
        thread_key: str,
        *,
        role: str,
        author: str,
        content: str,
        message_ts: str = "",
    ) -> None:
        sessions = self.load()
        thread = sessions.setdefault(thread_key, [])
        if message_ts:
            for index, message in enumerate(thread):
                if message.message_ts == message_ts and message.role == role:
                    if message.author == author and message.content == content:
                        return
                    thread[index] = SessionMessage(
                        role=role,
                        author=author,
                        content=content,
                        created_at=message.created_at,
                        message_ts=message_ts,
                    )
                    self._write(sessions)
                    return

        thread.append(
            SessionMessage(
                role=role,
                author=author,
                content=content,
                created_at=datetime.now(UTC).isoformat(),
                message_ts=message_ts,
            )
        )
        self._write(sessions)

    def _write(self, sessions: dict[str, list[SessionMessage]]) -> None:
        self.path.write_text(
            json.dumps(
                {
                    key: [asdict(message) for message in messages]
                    for key, messages in sessions.items()
                },
                indent=2,
            ),
            encoding="utf-8",
        )
