"""Spreadsheet bridge tests."""

from services.export.spreadsheet_bridge import (
    FARM_ACTIVITY_FIELDS,
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


if __name__ == "__main__":
    test_template_contains_required_fields()
    test_validate_farm_activity_required_fields()
    test_validate_farm_activity_numeric_fields()
