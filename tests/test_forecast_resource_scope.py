"""Location lineage guards for forecast and resource-efficiency queries."""

from __future__ import annotations

from datetime import datetime, timezone

from services.analytics.resource_efficiency import compute_resource_consumption_by_crop
from services.export.reports.core import generate_forecast_summary


class _ForecastCursor:
    def __init__(self):
        self.statements: list[str] = []
        self.statement_index = 0

    def execute(self, statement, _params=()):
        self.statements.append(statement)
        self.statement_index += 1

    def fetchall(self):
        return [
            {
                "scenario_id": "22222222-2222-4222-8222-222222222222",
                "scenario_name": "Target scenario",
                "scenario_type": "yield",
                "metric_name": "forecast_yield",
                "value": 7,
                "unit": "tonne",
                "confidence_low": 6,
                "confidence_high": 8,
                "inputs": {},
                "period_start": None,
                "period_end": None,
                "calculated_at": datetime(2026, 10, 30, tzinfo=timezone.utc),
            }
        ]

    def fetchone(self):
        return {"name": "Target location"}

    def close(self):
        pass


class _ForecastConnection:
    def __init__(self):
        self.cursor_instance = _ForecastCursor()

    def cursor(self, **_kwargs):
        return self.cursor_instance


def test_forecast_output_join_requires_scenario_and_output_location_match():
    conn = _ForecastConnection()

    result = generate_forecast_summary(
        conn, "11111111-1111-4111-8111-111111111111"
    )

    output_query = conn.cursor_instance.statements[1]
    assert "fs.location_id = fo.location_id" in output_query
    assert result["scenario_count"] == 1
    assert list(result["scenarios"].values())[0]["metrics"]["forecast_yield"]["value"] == 7


class _ResourceCursor:
    def __init__(self):
        self.statement = ""

    def execute(self, statement, _params=()):
        self.statement = statement

    def fetchall(self):
        return [("water", "liter", "cycle-target", "Corn", 12)]

    def close(self):
        pass


class _ResourceConnection:
    def __init__(self):
        self.cursor_instance = _ResourceCursor()

    def cursor(self):
        return self.cursor_instance


def test_resource_consumption_crop_cycle_join_requires_same_location():
    conn = _ResourceConnection()

    result = compute_resource_consumption_by_crop(
        conn, "11111111-1111-4111-8111-111111111111"
    )

    assert "cc.location_id = rc.location_id" in conn.cursor_instance.statement
    assert result["by_crop"] == [
        {
            "resource_type": "water",
            "unit": "liter",
            "crop_name": "Corn",
            "total_quantity": 12.0,
        }
    ]
