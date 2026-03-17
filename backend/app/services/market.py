from collections import Counter
from collections.abc import Iterable

from app.schemas.job import MarketInsight


def build_market_insight(
    rows: Iterable[
        tuple[list[str] | None, list[str] | None, int | None, int | None, bool | None]
    ],
) -> MarketInsight:
    skill_counter: Counter[str] = Counter()
    salary_counter: Counter[str] = Counter()
    remote_count = 0
    total = 0

    for requirements_must, tags, salary_min, salary_max, remote in rows:
        total += 1
        if tags:
            for tag in tags:
                skill_counter[tag] += 1
        else:
            for requirement in requirements_must or []:
                skill_counter[requirement] += 1
        if remote:
            remote_count += 1

        salary = salary_max or salary_min
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
        remote_ratio=round((remote_count / total) * 100, 1) if total else 0.0,
    )
