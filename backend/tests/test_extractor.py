import pytest

from app.services.extractor import extract_job_details, strip_json_fences


@pytest.mark.asyncio
async def test_extract_job_details_heuristic() -> None:
    raw_text = """
    Senior Python QA Automation Engineer at Example Labs
    Remote, Europe
    Salary $5000-7000
    - Python
    - Pytest
    - Playwright
    - API testing
    - AWS
    """

    extraction = await extract_job_details(
        raw_text,
        url="https://example.com/jobs/1",
        source="Example Labs",
    )

    assert extraction.title == "Senior Python QA Automation Engineer"
    assert extraction.company == "Example Labs"
    assert extraction.salary_min == 5000
    assert extraction.salary_max == 7000
    assert "Python" in extraction.tags
    assert "Pytest" in extraction.tags
    assert extraction.remote is True


def test_strip_json_fences() -> None:
    payload = """```json
    {"title":"Engineer"}
    ```"""

    assert strip_json_fences(payload) == '{"title":"Engineer"}'
