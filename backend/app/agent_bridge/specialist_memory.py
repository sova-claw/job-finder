from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.agent_bridge.planner_memory import compact_summary, extract_section

AUTO_SECTION_ORDER = [
    "Current Role",
    "Working Modes",
    "Known Strengths",
    "Recent Specialist Notes",
    "Recent Structured Findings",
    "Recommended Handoffs",
    "Last Activity",
]


@dataclass(slots=True)
class SpecialistMemoryUpdate:
    mode: str | None = None
    specialist_note: str | None = None
    finding: str | None = None
    handoff: str | None = None
    last_activity: str | None = None


def build_specialist_update(thread_key: str, content: str) -> SpecialistMemoryUpdate:
    mode = compact_summary(extract_section(content, "Mode"))
    findings = compact_summary(extract_section(content, "Findings"), fallback=content)
    handoff = compact_summary(extract_section(content, "Recommended handoff"))
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return SpecialistMemoryUpdate(
        mode=mode,
        specialist_note=f"{thread_key}: {findings}" if findings else None,
        finding=f"{thread_key}: {findings}" if findings else None,
        handoff=f"{thread_key}: {handoff}" if handoff else None,
        last_activity=f"{timestamp} specialist updated {thread_key}",
    )


class SpecialistMemoryStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_exists(self) -> None:
        if self.path.exists():
            return
        self.path.write_text(self._render({}), encoding="utf-8")

    def record_specialist_reply(self, thread_key: str, content: str) -> None:
        self.ensure_exists()
        self._apply_update(build_specialist_update(thread_key, content))

    def _apply_update(self, update: SpecialistMemoryUpdate) -> None:
        sections = self._parse_sections()
        self._set_single_item(
            sections,
            "Working Modes",
            update.mode,
            prefix="- ",
        )
        self._prepend_item(
            sections,
            "Recent Specialist Notes",
            update.specialist_note,
        )
        self._prepend_item(
            sections,
            "Recent Structured Findings",
            update.finding,
        )
        self._prepend_item(sections, "Recommended Handoffs", update.handoff)
        self._set_single_item(sections, "Last Activity", update.last_activity)
        self.path.write_text(self._render(sections), encoding="utf-8")

    def _parse_sections(self) -> dict[str, list[str]]:
        content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        sections: dict[str, list[str]] = {}
        current: str | None = None
        for line in content.splitlines():
            if line.startswith("# "):
                continue
            if line.startswith("## "):
                current = line[3:].strip()
                sections.setdefault(current, [])
                continue
            if current is not None:
                sections.setdefault(current, []).append(line)
        return sections

    def _prepend_item(
        self,
        sections: dict[str, list[str]],
        title: str,
        item: str | None,
        *,
        max_items: int = 8,
    ) -> None:
        if not item:
            return
        existing = [
            line[2:].strip()
            for line in sections.get(title, [])
            if line.strip().startswith("- ")
            and line[2:].strip() != "(empty)"
        ]
        merged = [entry for entry in [item, *existing] if entry]
        deduped: list[str] = []
        for entry in merged:
            if entry not in deduped:
                deduped.append(entry)
        sections[title] = [f"- {entry}" for entry in deduped[:max_items]]

    def _set_single_item(
        self,
        sections: dict[str, list[str]],
        title: str,
        item: str | None,
        *,
        prefix: str = "- ",
    ) -> None:
        if not item:
            return
        sections[title] = [f"{prefix}{item}"]

    def _render(self, sections: dict[str, list[str]]) -> str:
        lines = ["# Llama Memory", ""]
        seen = set()
        for title in AUTO_SECTION_ORDER:
            seen.add(title)
            lines.append(f"## {title}")
            body = sections.get(title, [])
            if body:
                lines.extend(body)
            else:
                lines.append("- (empty)")
            lines.append("")

        for title, body in sections.items():
            if title in seen:
                continue
            lines.append(f"## {title}")
            lines.extend(body or ["- (empty)"])
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
