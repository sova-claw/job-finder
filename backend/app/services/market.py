from collections import Counter

from app.models.job import Job
from app.schemas.job import MarketInsight


def build_market_insight(jobs: list[Job]) -> MarketInsight:
    skill_counter: Counter[str] = Counter()
    salary_counter: Counter[str] = Counter()
    remote_count = 0

    for job in jobs:
        for requirement in job.requirements_must or []:
            skill_counter[requirement] += 1
        if job.remote:
            remote_count += 1

        salary = job.salary_max or job.salary_min
        if salary is None:
            salary_counter["Undisclosed"] += 1
        elif salary < 4000:
            salary_counter["<4k"] += 1
        elif salary < 7000:
            salary_counter["4k-7k"] += 1
        elif salary < 10000:
            salary_counter["7k-10k"] += 1
        else:
            salary_counter["10k+"] += 1

    return MarketInsight(
        top_skills=[
            {"skill": skill, "count": count}
            for skill, count in skill_counter.most_common(10)
        ],
        salary_distribution=[
            {"band": band, "count": count}
            for band, count in salary_counter.items()
        ],
        remote_ratio=round((remote_count / len(jobs)) * 100, 1) if jobs else 0.0,
    )
