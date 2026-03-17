from app.services.market import build_market_insight


def test_build_market_insight_prefers_normalized_tags() -> None:
    insight = build_market_insight(
        [
            (["Hands-on experience with pytest"], ["Python", "Pytest"], 5000, 6500, True),
            (["API automation"], ["Python", "API Testing"], 4500, 5500, False),
            (["Fallback requirement"], None, None, None, True),
        ]
    )

    assert insight.top_skills[0].skill == "Python"
    assert insight.top_skills[0].count == 2
    assert any(skill.skill == "Pytest" for skill in insight.top_skills)
    assert any(skill.skill == "Fallback requirement" for skill in insight.top_skills)
    assert insight.remote_ratio == 66.7
