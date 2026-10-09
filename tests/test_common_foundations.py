"""Common Foundations checklist documentation tests."""

from pathlib import Path


CHECKLIST = Path("docs/common-foundations-checklist.md")


def test_common_foundations_checklist_covers_required_steps() -> None:
    text = CHECKLIST.read_text().lower()
    for phrase in [
        "useful questions",
        "stakeholder involvement",
        "feasible data",
        "sense-making",
        "reporting",
        "learning",
    ]:
        assert phrase in text


def test_checklist_file_exists() -> None:
    assert CHECKLIST.exists(), f"Checklist file not found at {CHECKLIST}"


def test_checklist_has_minimum_length() -> None:
    text = CHECKLIST.read_text()
    assert len(text) > 500, "Checklist appears too short to be comprehensive"
