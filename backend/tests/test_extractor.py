import pytest

from app.services.extractor import extract_job_details


@pytest.mark.asyncio
async def test_extract_job_details_heuristic() -> None:
    raw_text = """
    Senior Python AI Engineer at Example Labs
    Remote, Europe
    Salary $5000-7000
    - Python
    - FastAPI
    - LangChain
    - RAG pipelines
    - AWS
    """

    extraction = await extract_job_details(
        raw_text,
        url="https://example.com/jobs/1",
        source="Example Labs",
    )

    assert extraction.title == "Senior Python AI Engineer"
    assert extraction.company == "Example Labs"
    assert extraction.salary_min == 5000
    assert extraction.salary_max == 7000
    assert "Python" in extraction.tags
    assert extraction.remote is True
