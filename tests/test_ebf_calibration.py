"""EBF annual calibration lifecycle tests."""

from pathlib import Path


SCHEMA = Path("schemas/postgres/033_ebf_p1_operations.sql")


def test_calibration_lifecycle_and_frequency_are_constrained() -> None:
    text = SCHEMA.read_text().lower()
    assert "chk_ebf_calibration_session_lifecycle" in text
    for status in ["draft", "submitted", "verified", "published", "rejected"]:
        assert f"'{status}'" in text
    assert "'annual'" in text
    assert "'semi_annual'" in text


def test_team_calibration_requires_report() -> None:
    text = SCHEMA.read_text().lower()
    assert "chk_ebf_calibration_session_report" in text
    assert "team_with_report" in text
    assert "report_url" in text
    assert "report_hash" in text


def test_calibration_frequency_includes_semi_annual() -> None:
    text = SCHEMA.read_text()
    assert "semi_annual" in text.lower()


def test_calibration_decision_table_has_status_constraint() -> None:
    text = SCHEMA.read_text().lower()
    assert "ebf_calibration_decision" in text
    assert "chk_ebf_calibration_decision" in text or "decision_status" in text


if __name__ == "__main__":
    test_calibration_lifecycle_and_frequency_are_constrained()
    test_team_calibration_requires_report()
