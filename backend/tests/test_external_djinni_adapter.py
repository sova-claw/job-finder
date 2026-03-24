from __future__ import annotations

import json

import pytest

from app.services import external_djinni_adapter as adapter


class _FakeProcess:
    def __init__(self, *, returncode: int, stdout: bytes, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_run_external_djinni_cli_invokes_uv(monkeypatch, tmp_path) -> None:
    calls: list[dict[str, object]] = []

    async def fake_create_subprocess_exec(*command, **kwargs):
        calls.append({"command": command, "cwd": kwargs.get("cwd")})
        return _FakeProcess(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "title": "Senior QA Automation Engineer",
                        "company": "Bolt",
                        "listing_url": "https://djinni.co/jobs/111/",
                        "posted_at": "2026-03-20T00:00:00+00:00",
                        "description_text": "Python pytest playwright",
                    }
                ]
            ).encode("utf-8"),
        )

    settings = adapter.get_settings()
    monkeypatch.setattr(settings, "external_djinni_repo_path", str(tmp_path))
    monkeypatch.setattr(
        settings,
        "external_djinni_start_urls_csv",
        "https://djinni.co/jobs/?primary_keyword=QA%20Automation",
    )
    monkeypatch.setattr(settings, "external_djinni_max_pages", 2)
    monkeypatch.setattr(settings, "external_djinni_max_items", 25)
    monkeypatch.setattr(settings, "djinni_cookie_header", "session=1")
    monkeypatch.setattr(adapter.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    rows = await adapter._run_external_djinni_cli()

    assert rows[0]["company"] == "Bolt"
    assert calls[0]["command"][0:4] == (
        "uv",
        "run",
        "python",
        "-m",
    )
    assert "scraper_djinni_market_data.cli" in calls[0]["command"]
    assert calls[0]["cwd"] == str(tmp_path)


def test_posting_from_row_maps_description_text() -> None:
    posting = adapter._posting_from_row(
        {
            "title": "Senior QA Automation Engineer",
            "company": "Bolt",
            "listing_url": "https://djinni.co/jobs/111/",
            "posted_at": "2026-03-20T00:00:00+00:00",
            "description_text": "Python pytest playwright",
            "salary_raw": "$6000-$8000",
        }
    )

    assert posting.title == "Senior QA Automation Engineer"
    assert posting.company == "Bolt"
    assert posting.raw_text == "Python pytest playwright"
    assert posting.posted_at is not None
