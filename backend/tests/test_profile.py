from app.services.profile import matches_abroad_remote_preference, matches_focus_role


def test_matches_focus_role_requires_qa_signal_in_title() -> None:
    assert matches_focus_role("Senior QA Automation Engineer", "Python pytest playwright")
    assert not matches_focus_role("Senior Python Engineer", "pytest selenium api testing")


def test_matches_abroad_remote_preference_prefers_remote_and_non_ukraine() -> None:
    assert matches_abroad_remote_preference(
        title="Senior QA Automation Engineer",
        location="Poland",
        raw_text="Remote from Poland",
        remote=True,
    )
    assert not matches_abroad_remote_preference(
        title="Senior QA Automation Engineer",
        location="Kyiv",
        raw_text="Office in Kyiv",
        remote=False,
    )
    assert not matches_abroad_remote_preference(
        title="Senior QA Automation Engineer",
        location="Lviv",
        raw_text="Remote Ukraine",
        remote=True,
    )
