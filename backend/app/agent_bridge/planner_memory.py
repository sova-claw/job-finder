from __future__ import annotations

import re

HEADING_NAMES = {
    "goal",
    "decision",
    "task",
    "success check",
    "intent",
    "plan",
    "risks",
    "handoff",
    "what i will do",
    "what i changed or found",
    "next check",
    "blockers or next steps",
    "mode",
    "findings",
    "recommended handoff",
}


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
