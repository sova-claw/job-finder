from app.schemas.job import JobExtraction
from app.services.profile import get_candidate_profile
from app.services.scorer import score_job


def test_score_job_returns_gaps_for_qa_automation_skills() -> None:
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

    score, gaps = score_job(extraction, get_candidate_profile())

    assert 0 < score <= 100
    assert any(gap.skill == "UI automation" for gap in gaps)
    assert any(gap.skill == "Performance testing" for gap in gaps)


def test_score_job_does_not_award_irrelevant_skill_weight() -> None:
    extraction = JobExtraction(
        title="Operations Coordinator",
        company="Example",
        company_type="Service",
        salary_min=1000,
        salary_max=1500,
        requirements_must=["Excel", "Stakeholder communication"],
        requirements_nice=[],
        tags=["Excel"],
        domain="General",
        remote=False,
        location="Kyiv",
    )

    score, gaps = score_job(extraction, get_candidate_profile())

    assert score == 0
    assert gaps == []
