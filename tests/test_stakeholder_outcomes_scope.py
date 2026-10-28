"""Location-scope guarantees for stakeholder outcome reports."""

from unittest.mock import MagicMock

import pytest

from services.export.reports.strategy import generate_stakeholder_outcomes

LOCATION_ID = "a0000000-0000-0000-0000-000000000001"


def _connection(fetches):
    cursor = MagicMock()
    cursor.__enter__ = lambda self: cursor
    cursor.__exit__ = lambda self, *_args: None
    cursor.fetchall.side_effect = fetches
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def test_location_report_reads_only_selected_location_outcomes():
    conn, cursor = _connection([[{"id": "outcome-a"}]])

    report = generate_stakeholder_outcomes(conn, LOCATION_ID)

    assert report["outcomes"] == [{"id": "outcome-a"}]
    assert report["capability_and_value_stream_links"] == []
    assert report["outcome_count"] == 1
    assert cursor.execute.call_count == 1
    query, params = cursor.execute.call_args.args
    assert "status IN ('verified', 'published') AND location_id = %s::uuid" in query
    assert params == [LOCATION_ID]


@pytest.mark.parametrize("location_id", [None, ""])
def test_missing_location_fails_before_opening_cursor(location_id):
    conn, _cursor = _connection([])

    with pytest.raises(ValueError, match="stakeholder_outcomes requires an explicit location_id"):
        generate_stakeholder_outcomes(conn, location_id)

    conn.cursor.assert_not_called()
