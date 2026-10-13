"""Published farm activity lifecycle metric provenance checks."""

from uuid import UUID

from services.metrics.calculators.rework_rate import compute_rework_rate

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
PUBLISHED_ID = UUID("10101010-1010-4010-8010-101010101010")
REWORKED_ID = UUID("20202020-2020-4020-8020-202020202020")


class MetricCursor:
    def __init__(self, row):
        self.row = row
        self.sql = ""
        self.params = None
        self.closed = False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class MetricConnection:
    def __init__(self, row):
        self.cursor_instance = MetricCursor(row)

    def cursor(self, **_kwargs):
        return self.cursor_instance


def test_rework_rate_tracks_published_source_and_reworked_subset():
    connection = MetricConnection(
        {
            "total": 2,
            "reworked": 1,
            "source_ids": [PUBLISHED_ID, REWORKED_ID],
            "reworked_source_ids": [REWORKED_ID],
        }
    )

    result = compute_rework_rate(
        connection,
        LOCATION_ID,
        period_start="2026-10-01",
        period_end="2026-10-31",
    )

    assert result["value"] == 50.0
    assert result["unit"] == "percent"
    assert result["source_record_ids"] == [str(PUBLISHED_ID), str(REWORKED_ID)]
    assert result["metadata"]["reworked_source_record_ids"] == [str(REWORKED_ID)]
    assert result["metadata"]["published_count"] == 2
    assert result["metadata"]["reworked_count"] == 1
    assert result["metadata"]["period_start"] == "2026-10-01"
    assert result["metadata"]["period_end"] == "2026-10-31"

    sql = " ".join(connection.cursor_instance.sql.split())
    assert "'farm_activity'" in sql
    assert "lt.to_status = 'published'" in sql
    assert "WHERE to_status = 'rejected'" in sql
    assert "< (%(pe)s::date + INTERVAL '1 day')" in sql
    assert sql.count("LIMIT 101") == 2
    assert connection.cursor_instance.params == {
        "loc": LOCATION_ID,
        "ps": "2026-10-01",
        "pe": "2026-10-31",
    }
    assert connection.cursor_instance.closed is True


def test_rework_rate_keeps_empty_period_undefined_with_no_source_records():
    result = compute_rework_rate(
        MetricConnection(
            {
                "total": 0,
                "reworked": 0,
                "source_ids": [],
                "reworked_source_ids": [],
            }
        ),
        LOCATION_ID,
    )

    assert result["value"] is None
    assert result["source_record_ids"] == []
    assert result["metadata"]["published_count"] == 0


def test_rework_rate_parses_unregistered_postgres_array_literals():
    result = compute_rework_rate(
        MetricConnection(
            {
                "total": 2,
                "reworked": 1,
                "source_ids": f"{{{PUBLISHED_ID},{REWORKED_ID}}}",
                "reworked_source_ids": f"{{{REWORKED_ID}}}",
            }
        ),
        LOCATION_ID,
    )

    assert result["source_record_ids"] == [str(PUBLISHED_ID), str(REWORKED_ID)]
    assert result["metadata"]["reworked_source_record_ids"] == [str(REWORKED_ID)]
