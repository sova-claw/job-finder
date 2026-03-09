from app.schemas.job import JobExtraction
from app.services.profile import get_candidate_profile
from app.services.scorer import score_job


def test_score_job_returns_gaps_for_ai_skills() -> None:
    extraction = JobExtraction(
        title="AI Engineer",
        company="Example",
        company_type="Product",
        salary_min=6000,
        salary_max=9000,
        requirements_must=[
            "Python",
            "LangChain",
            "RAG",
            "FastAPI",
            "Production ML",
        ],
        requirements_nice=["AWS"],
        tags=["Python", "LangChain", "RAG", "FastAPI", "ML"],
        domain="FinTech",
        remote=True,
        location="Remote",
    )

    score, gaps = score_job(extraction, get_candidate_profile())

    assert 0 < score <= 100
    assert any(gap.skill == "LangChain / agents" for gap in gaps)
    assert any(gap.skill == "RAG + Vector DB" for gap in gaps)
