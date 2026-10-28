"""Direct-call scope validation for location-scoped scaling reports."""

from uuid import uuid4

import pytest

from services.export.reports.commons.scaling import (
    generate_adoption_barriers,
    generate_perpetual_value_stress,
)

GENERATORS = [
    ("adoption_barriers", generate_adoption_barriers),
    ("perpetual_value_stress", generate_perpetual_value_stress),
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
def test_scaling_reports_reject_invalid_location_before_cursor(
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
def test_scaling_reports_preserve_valid_location_queries(report_type, generator):
    location_id = str(uuid4())
    conn = RecordingConnection()

    result = generator(conn, location_id)

    assert conn.cursor_calls == 1
    assert conn.cursor_instance.closed
    assert result["report_type"] == report_type
    assert result["location_id"] == location_id
    assert conn.cursor_instance.executed
    assert all(location_id in params for _query, params in conn.cursor_instance.executed)
