"""EBF CSV import validation tests."""

from services.export.spreadsheet_bridge import import_ebf_scorecard_csv, validate_ebf_evidence_row, validate_ebf_scorecard_row


def test_scorecard_csv_validation() -> None:
    errors = validate_ebf_scorecard_row({}, 2)
    assert "row 2: missing required field location_id" in errors
    assert "row 2: missing required field period_start" in errors


def test_evidence_csv_validation() -> None:
    errors = validate_ebf_evidence_row({"evidence_type": "private_raw", "evidence_maturity_level": "x"}, 3)
    assert "row 3: evidence_type is not supported" in errors
    assert "row 3: evidence_maturity_level must be an integer" in errors


def test_scorecard_csv_dry_run_validates_rows(tmp_path) -> None:
    path = tmp_path / "ebf_scorecard.csv"
    path.write_text("location_id,farm_id,period_start,period_end,rubric_version,calibration_method,calibration_report_url\na0000000-0000-0000-0000-000000000001,,2026-01-01,2026-12-31,2026.1,third_party,\n")
    result = import_ebf_scorecard_csv(None, str(path), dry_run=True)
    assert result["validated"] == 1
    assert result["inserted"] == 0
    assert result["template_type"] == "ebf_scorecard"


if __name__ == "__main__":
    test_scorecard_csv_validation()
    test_evidence_csv_validation()
    from tempfile import TemporaryDirectory
    from pathlib import Path
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "ebf_scorecard.csv"
        path.write_text("location_id,farm_id,period_start,period_end,rubric_version,calibration_method,calibration_report_url\na0000000-0000-0000-0000-000000000001,,2026-01-01,2026-12-31,2026.1,third_party,\n")
        result = import_ebf_scorecard_csv(None, str(path), dry_run=True)
        assert result["validated"] == 1
