from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.agent_bridge.planner_memory import compact_summary, extract_section

AUTO_SECTION_ORDER = [
    "North Star",
    "Current Goal",
    "Success Check",
    "Active Thread Goals",
    "Recent Progress",
    "Open Risks",
    "Last Activity",
]


@dataclass(slots=True)
class GoalUpdate:
    current_goal: str | None = None
    success_check: str | None = None
    active_goal: str | None = None
    progress: str | None = None
    open_risk: str | None = None
    last_activity: str | None = None


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


def _compose_active_goal(thread_key: str, goal: str, task: str, success_check: str) -> str:
    parts = [f"{thread_key}: {goal}"]
    if task:
        parts.append(f"task: {task}")
    if success_check:
        parts.append(f"success: {success_check}")
    return " | ".join(parts)


def build_planner_goal_update(thread_key: str, content: str) -> GoalUpdate:
    goal = compact_summary(
        extract_section(content, "Goal"),
        fallback=extract_section(content, "Decision"),
    )
    task = compact_summary(
        extract_section(content, "Task"),
        fallback=extract_section(content, "Handoff"),
    )
    success_check = compact_summary(extract_section(content, "Success check"))
    decision = compact_summary(
        extract_section(content, "Decision"),
        fallback=content,
    )
    risks = compact_summary(extract_section(content, "Risks"))
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return GoalUpdate(
        current_goal=goal,
        success_check=success_check,
        active_goal=(
            _compose_active_goal(thread_key, goal, task, success_check)
            if goal
            else None
        ),
        progress=f"{thread_key}: {decision}" if decision else None,
        open_risk=f"{thread_key}: {risks}" if risks else None,
        last_activity=f"{timestamp} planner updated {thread_key}",
    )


def build_executor_goal_update(thread_key: str, content: str) -> GoalUpdate:
    goal = compact_summary(extract_section(content, "Goal"))
    changed = compact_summary(
        extract_section(content, "What I changed or found"),
        fallback=content,
    )
    next_check = compact_summary(extract_section(content, "Next check"))
    blockers = compact_summary(extract_section(content, "Blockers or next steps"))
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    next_check_part = f"next check: {next_check}" if next_check else ""
    progress_parts = [part for part in [changed, next_check_part] if part]
    return GoalUpdate(
        current_goal=goal,
        active_goal=f"{thread_key}: {goal}" if goal else None,
        progress=f"{thread_key}: {' | '.join(progress_parts)}" if progress_parts else None,
        open_risk=(
            None if _contains_clear_signal(blockers) else f"{thread_key}: {blockers}"
        ),
        last_activity=f"{timestamp} executor updated {thread_key}",
    )


class GoalBoardStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_exists(self) -> None:
        if self.path.exists():
            return
        self.path.write_text(self._render({}), encoding="utf-8")

    def record_planner_reply(self, thread_key: str, content: str) -> None:
        self.ensure_exists()
        self._apply_update(build_planner_goal_update(thread_key, content))

    def record_executor_reply(self, thread_key: str, content: str) -> None:
        self.ensure_exists()
        self._apply_update(build_executor_goal_update(thread_key, content))

    def _apply_update(self, update: GoalUpdate) -> None:
        sections = self._parse_sections()
        self._set_single_item(sections, "Current Goal", update.current_goal)
        self._set_single_item(sections, "Success Check", update.success_check)
        self._prepend_item(sections, "Active Thread Goals", update.active_goal)
        self._prepend_item(sections, "Recent Progress", update.progress)
        self._prepend_item(sections, "Open Risks", update.open_risk)
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
    ) -> None:
        if not item:
            return
        sections[title] = [f"- {item}"]

    def _render(self, sections: dict[str, list[str]]) -> str:
        lines = ["# Claude Goal Board", ""]
        seen = set()
        for title in AUTO_SECTION_ORDER:
            seen.add(title)
            lines.append(f"## {title}")
            body = sections.get(title, [])
            if body:
                lines.extend(body)
            elif title == "North Star":
                lines.append(
                    "- Find one remote B2B contract in the $6k-$7k range "
                    "through a Slack-first operating system."
                )
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
