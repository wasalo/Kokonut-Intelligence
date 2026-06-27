"""EBF CSV import validation tests."""

from services.export.spreadsheet_bridge import validate_ebf_evidence_row, validate_ebf_scorecard_row


def test_scorecard_csv_validation() -> None:
    errors = validate_ebf_scorecard_row({}, 2)
    assert "row 2: missing required field location_id" in errors
    assert "row 2: missing required field period_start" in errors


def test_evidence_csv_validation() -> None:
    errors = validate_ebf_evidence_row({"evidence_type": "private_raw", "evidence_maturity_level": "x"}, 3)
    assert "row 3: evidence_type is not supported" in errors
    assert "row 3: evidence_maturity_level must be an integer" in errors


if __name__ == "__main__":
    test_scorecard_csv_validation()
    test_evidence_csv_validation()
