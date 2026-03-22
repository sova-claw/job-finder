import pytest

from app.schemas.job import JobExtraction
from app.services.profile import get_candidate_profile
from app.services.scorer import score_job


@pytest.mark.asyncio
async def test_score_job_returns_matches_and_gaps_for_qa_automation_role() -> None:
    extraction = JobExtraction(
        title="Senior QA Automation Engineer",
        company="Example",
        company_type="Product",
        salary_min=6000,
        salary_max=9000,
        requirements_must=[
            "Python",
            "QA automation",
            "Pytest",
            "Playwright",
            "Performance testing with k6",
        ],
        requirements_nice=["AWS"],
        tags=["Python", "QA Automation", "Pytest", "Playwright", "k6"],
        domain="FinTech",
        remote=True,
        location="Remote",
    )

    scored = await score_job(
        extraction,
        get_candidate_profile(),
        raw_text=(
            "Senior QA Automation Engineer with Python, Playwright, API testing, "
            "Docker, AWS, GitHub Actions, and fintech platform experience."
        ),
    )

    assert scored.score == 100
    assert scored.hard_matches == ["Python", "QA Automation", "API Testing"]
    assert "UI Automation" in scored.soft_matches
    assert "Cloud" in scored.soft_matches
    assert any(gap.skill == "UI automation" for gap in scored.gaps)
    assert any(gap.skill == "Performance testing" for gap in scored.gaps)
    assert scored.dealbreaker is False


@pytest.mark.asyncio
async def test_score_job_flags_manual_only_role_as_dealbreaker() -> None:
    extraction = JobExtraction(
        title="Manual QA Engineer",
        company="Example",
        company_type="Service",
        salary_min=2000,
        salary_max=3000,
        requirements_must=["Manual testing only", "Regression test execution"],
        requirements_nice=[],
        tags=["Manual QA"],
        domain="General",
        remote=True,
        location="Remote",
    )

    scored = await score_job(
        extraction,
        get_candidate_profile(),
        raw_text="Manual QA only role. No automation. Regression test execution.",
    )

    assert scored.score == 0
    assert scored.dealbreaker is True
