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


if __name__ == "__main__":
    test_common_foundations_checklist_covers_required_steps()
