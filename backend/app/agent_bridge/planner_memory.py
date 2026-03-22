from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

HEADING_NAMES = {
    "intent",
    "plan",
    "risks",
    "handoff",
    "what i will do",
    "what i changed or found",
    "blockers or next steps",
}

AUTO_SECTION_ORDER = [
    "Current Focus",
    "Known Working Integrations",
    "Known Gaps",
    "Active Decisions",
    "Recent Planner Notes",
    "Recent Execution Notes",
    "Recent Risks or Blockers",
    "Next Suggested Tasks",
    "Last Activity",
]


@dataclass(slots=True)
class MemoryUpdate:
    planner_note: str | None = None
    execution_note: str | None = None
    risk_or_blocker: str | None = None
    next_task: str | None = None
    last_activity: str | None = None


def _canonical_heading(line: str) -> str:
    cleaned = re.sub(r"^[#*\-\d\.\)\s]+", "", line.strip())
    return cleaned.rstrip(":").strip().lower()


def extract_section(text: str, heading: str) -> str:
    target = heading.strip().lower()
    lines = text.splitlines()
    start_index: int | None = None
    for index, line in enumerate(lines):
        if _canonical_heading(line) == target:
            start_index = index + 1
            break

    if start_index is None:
        return ""

    collected: list[str] = []
    for line in lines[start_index:]:
        if _canonical_heading(line) in HEADING_NAMES:
            break
        collected.append(line)

    return "\n".join(collected).strip()


def compact_summary(text: str, *, fallback: str = "", limit: int = 180) -> str:
    source = text.strip() or fallback.strip()
    if not source:
        return ""

    first_line = next((line.strip() for line in source.splitlines() if line.strip()), "")
    if not first_line:
        return ""

    normalized = re.sub(r"\s+", " ", first_line).strip(" -*")
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _contains_clear_signal(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return True
    return any(
        phrase in lowered
        for phrase in [
            "none",
            "no blocker",
            "no blockers",
            "nothing blocking",
            "clear",
        ]
    )


def build_planner_update(thread_key: str, content: str) -> MemoryUpdate:
    intent = compact_summary(extract_section(content, "Intent"), fallback=content)
    risks = compact_summary(extract_section(content, "Risks"))
    handoff = compact_summary(extract_section(content, "Handoff"))
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return MemoryUpdate(
        planner_note=f"{thread_key}: {intent}" if intent else None,
        risk_or_blocker=f"{thread_key}: {risks}" if risks else None,
        next_task=f"{thread_key}: {handoff}" if handoff else None,
        last_activity=f"{timestamp} planner updated {thread_key}",
    )


def build_executor_update(thread_key: str, content: str) -> MemoryUpdate:
    changed = compact_summary(
        extract_section(content, "What I changed or found"),
        fallback=content,
    )
    blockers = compact_summary(extract_section(content, "Blockers or next steps"))
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return MemoryUpdate(
        execution_note=f"{thread_key}: {changed}" if changed else None,
        risk_or_blocker=(
            None if _contains_clear_signal(blockers) else f"{thread_key}: {blockers}"
        ),
        last_activity=f"{timestamp} executor updated {thread_key}",
    )


class PlannerMemoryStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_exists(self) -> None:
        if self.path.exists():
            return
        self.path.write_text(self._render({}), encoding="utf-8")

    def record_planner_reply(self, thread_key: str, content: str) -> None:
        self.ensure_exists()
        self._apply_update(build_planner_update(thread_key, content))

    def record_executor_reply(self, thread_key: str, content: str) -> None:
        self.ensure_exists()
        self._apply_update(build_executor_update(thread_key, content))

    def _apply_update(self, update: MemoryUpdate) -> None:
        sections = self._parse_sections()
        self._prepend_item(sections, "Recent Planner Notes", update.planner_note)
        self._prepend_item(sections, "Recent Execution Notes", update.execution_note)
        self._prepend_item(
            sections,
            "Recent Risks or Blockers",
            update.risk_or_blocker,
        )
        self._prepend_item(sections, "Next Suggested Tasks", update.next_task)
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
    ) -> None:
        if not item:
            return
        sections[title] = [f"- {item}"]

    def _render(self, sections: dict[str, list[str]]) -> str:
        lines = ["# Planner Memory", ""]
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
