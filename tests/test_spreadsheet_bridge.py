"""Spreadsheet bridge tests."""

from services.export.spreadsheet_bridge import (
    EBF_EVIDENCE_FIELDS,
    EBF_SCORECARD_FIELDS,
    FARM_ACTIVITY_FIELDS,
    ebf_evidence_template_rows,
    ebf_scorecard_template_rows,
    validate_ebf_evidence_row,
    validate_ebf_scorecard_row,
    template_rows,
    validate_farm_activity_row,
)


def test_template_contains_required_fields() -> None:
    row = template_rows()[0]
    assert "location_id" in row
    assert "activity_type" in row
    assert set(row.keys()) == set(FARM_ACTIVITY_FIELDS)


def test_validate_farm_activity_required_fields() -> None:
    errors = validate_farm_activity_row({}, 2)
    assert "row 2: missing required field location_id" in errors
    assert "row 2: missing required field activity_type" in errors


def test_validate_farm_activity_numeric_fields() -> None:
    row = {
        "location_id": "a0000000-0000-0000-0000-000000000001",
        "activity_type": "planting",
        "activity_date": "2026-01-01",
        "description": "Planting beds",
        "labor_hours": "not-a-number",
    }
    errors = validate_farm_activity_row(row, 3)
    assert "row 3: labor_hours must be numeric" in errors


def test_ebf_scorecard_template_contains_required_fields() -> None:
    row = ebf_scorecard_template_rows()[0]
    assert "location_id" in row
    assert "rubric_version" in row
    assert set(row.keys()) == set(EBF_SCORECARD_FIELDS)


def test_validate_ebf_scorecard_row() -> None:
    errors = validate_ebf_scorecard_row({"calibration_method": "invalid"}, 2)
    assert "row 2: missing required field location_id" in errors
    assert "row 2: calibration_method must be third_party, team_with_report, or mixed_panel" in errors


def test_ebf_evidence_template_and_validation() -> None:
    row = ebf_evidence_template_rows()[0]
    assert set(row.keys()) == set(EBF_EVIDENCE_FIELDS)
    errors = validate_ebf_evidence_row({"evidence_type": "raw_private_feedback", "evidence_maturity_level": "7"}, 4)
    assert "row 4: evidence_type is not supported" in errors
    assert "row 4: evidence_maturity_level must be between 0 and 6" in errors


if __name__ == "__main__":
    test_template_contains_required_fields()
    test_validate_farm_activity_required_fields()
    test_validate_farm_activity_numeric_fields()
    test_ebf_scorecard_template_contains_required_fields()
    test_validate_ebf_scorecard_row()
    test_ebf_evidence_template_and_validation()
