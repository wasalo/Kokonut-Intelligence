"""Direct-call scope validation for liberation reports."""

from uuid import uuid4

import pytest

from services.export.reports.commons.liberation import (
    generate_capital_alignment,
    generate_governance_inclusion,
    generate_land_stewardship,
    generate_time_liberation,
)

GENERATORS = [
    ("time_liberation", generate_time_liberation),
    ("capital_alignment", generate_capital_alignment),
    ("governance_inclusion", generate_governance_inclusion),
    ("land_stewardship", generate_land_stewardship),
]


class NoDatabase:
    def cursor(self, **_kwargs):
        raise AssertionError("database access must not occur for invalid location scope")


@pytest.mark.parametrize("report_type,generator", GENERATORS)
@pytest.mark.parametrize(
    "location_id",
    [
        None,
        "",
        "all",
        "not-a-uuid",
        "11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222",
    ],
)
def test_liberation_reports_reject_invalid_location_before_cursor(
    report_type, generator, location_id
):
    with pytest.raises(ValueError, match=f"{report_type} requires an explicit location_id"):
        generator(NoDatabase(), location_id)


class RecordingCursor:
    def __init__(self):
        self.executed = []
        self.closed = False

    def execute(self, query, params):
        self.executed.append((query, params))

    def fetchone(self):
        return {"name": "Synthetic location"}

    def fetchall(self):
        return []

    def close(self):
        self.closed = True


class RecordingConnection:
    def __init__(self):
        self.cursor_instance = RecordingCursor()
        self.cursor_calls = 0

    def cursor(self, **_kwargs):
        self.cursor_calls += 1
        return self.cursor_instance


@pytest.mark.parametrize("report_type,generator", GENERATORS)
def test_liberation_reports_preserve_valid_location_queries(report_type, generator):
    location_id = str(uuid4())
    conn = RecordingConnection()

    result = generator(conn, location_id)

    assert conn.cursor_calls == 1
    assert conn.cursor_instance.closed
    assert result["report_type"] == report_type
    assert result["location_id"] == location_id
    assert conn.cursor_instance.executed
    assert all(location_id in params for _query, params in conn.cursor_instance.executed)
