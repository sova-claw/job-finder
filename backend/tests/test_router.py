from app.models.job import Job
from app.services.router import route_channels_for_job


def _job(**overrides: object) -> Job:
    payload = {
        "id": "job-1",
        "url": "https://example.com/jobs/1",
        "source": "BigCo",
        "source_group": "BigCo",
        "title": "Senior QA Automation Engineer",
        "company": "Example",
        "match_score": 60,
        "location": "Remote",
        "dealbreaker": False,
        "is_active": True,
    }
    payload.update(overrides)
    return Job(**payload)


def test_route_channels_for_priority_job() -> None:
    assert route_channels_for_job(_job(match_score=90, location="Tel Aviv, Israel")) == [
        "#jobs-priority"
    ]


def test_route_channels_for_strong_job() -> None:
    assert route_channels_for_job(_job(match_score=80, location="London, UK")) == ["#jobs-priority"]


def test_route_channels_for_backlog_job() -> None:
    assert route_channels_for_job(_job(match_score=60, source="Sentry", source_group="BigCo")) == [
        "#jobs-inbox"
    ]


def test_route_channels_for_dealbreaker_job() -> None:
    job = _job(match_score=90, location="Warsaw, Poland", dealbreaker=True)
    assert route_channels_for_job(job) == []
