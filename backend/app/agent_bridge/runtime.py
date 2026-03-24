from __future__ import annotations

import asyncio
import os
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass(slots=True)
class AgentResult:
    name: str
    content: str


async def run_text_command(command: str, *, cwd: Path) -> str:
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        return stderr.decode("utf-8", errors="ignore").strip()
    return stdout.decode("utf-8", errors="ignore").strip()


async def collect_repo_state(cwd: Path) -> str:
    branch = await run_text_command("git rev-parse --abbrev-ref HEAD", cwd=cwd)
    status = await run_text_command("git status --short", cwd=cwd)
    commits = await run_text_command("git log -3 --oneline", cwd=cwd)
    chunks = [f"Branch: {branch or 'unknown'}"]
    if commits:
        chunks.append(f"Recent commits:\n{commits}")
    if status:
        chunks.append(f"Working tree:\n{status}")
    else:
        chunks.append("Working tree: clean")
    return "\n\n".join(chunks)


async def run_agent_command(
    command_template: str,
    prompt: str,
    *,
    cwd: Path,
) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as output_file:
        output_path = Path(output_file.name)

    command = shlex.split(
        command_template.format(cwd=str(cwd), output_file=str(output_path))
    )
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
    )
    stdout, stderr = await process.communicate(prompt.encode("utf-8"))
    output_text = (
        output_path.read_text(encoding="utf-8").strip()
        if output_path.exists()
        else ""
    )
    output_path.unlink(missing_ok=True)

    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="ignore").strip() or stdout.decode(
            "utf-8", errors="ignore"
        ).strip()
        raise RuntimeError(message or f"Agent command failed: {' '.join(command)}")

    final_text = output_text or stdout.decode("utf-8", errors="ignore").strip()
    return final_text or "(no output)"


def extract_ollama_model(command_template: str) -> str | None:
    template = command_template.strip()
    if template.startswith("ollama-api:"):
        model = template.split(":", 1)[1].strip()
        return model or None

    parts = shlex.split(template)
    if len(parts) >= 3 and parts[0] == "ollama" and parts[1] == "run":
        return parts[2]
    return None


async def run_specialist_command(
    command_template: str,
    prompt: str,
    *,
    cwd: Path,
    ollama_host: str,
) -> str:
    model = extract_ollama_model(command_template)
    if not model:
        return await run_agent_command(command_template, prompt, cwd=cwd)

    base_url = os.environ.get("OLLAMA_HOST", ollama_host).rstrip("/")
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
    content = str(payload.get("response", "")).strip()
    return content or "(no output)"
