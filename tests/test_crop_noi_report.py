"""Crop NOI reports must use the shared verified-input formula."""

from datetime import date
from decimal import Decimal

from services.export.reports.core import generate_crop_noi


class CropNoiCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None
        self.closed = False

    def execute(self, sql, params):
        self.query = " ".join(sql.split())
        self.params = params

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class CropNoiConnection:
    def __init__(self, rows):
        self.cursor_instance = CropNoiCursor(rows)

    def cursor(self, **_kwargs):
        return self.cursor_instance


def test_crop_noi_report_projects_canonical_view_components_and_period_scope():
    connection = CropNoiConnection(
        [
            {
                "cycle_id": "cycle-1",
                "cycle_name": "Wet season",
                "crop_name": "Plantain",
                "plot_name": "North plot",
                "status": "completed",
                "planting_date": date(2026, 1, 1),
                "actual_harvest_date": date(2026, 6, 1),
                "expected_yield": Decimal("100"),
                "actual_yield": Decimal("90"),
                "expected_revenue": Decimal("1400"),
                "gross_revenue": Decimal("1200"),
                "returns_and_discounts": Decimal("50"),
                "net_revenue": Decimal("1150"),
                "direct_crop_costs": Decimal("300"),
                "allocated_shared_costs": Decimal("100"),
                "total_costs": Decimal("400"),
                "noi": Decimal("750"),
                "operating_margin_pct": Decimal("65.2174"),
                "loss_rate_pct": Decimal("5"),
            }
        ]
    )

    report = generate_crop_noi(
        connection,
        "location-1",
        period_start="2026-01-01",
        period_end="2026-06-30",
    )

    cycle = report["crop_cycles"][0]
    assert cycle["actual_revenue"] == 1150.0
    assert cycle["allocated_cost"] == 400.0
    assert cycle["gross_revenue"] == 1200.0
    assert cycle["returns_and_discounts"] == 50.0
    assert cycle["net_revenue"] == 1150.0
    assert cycle["direct_crop_costs"] == 300.0
    assert cycle["allocated_shared_costs"] == 100.0
    assert cycle["total_costs"] == 400.0
    assert cycle["crop_noi"] == 750.0
    assert cycle["operating_margin_pct"] == 65.2174
    assert cycle["loss_rate_pct"] == 5.0
    assert report["summary"] == {
        "total_revenue": 1150.0,
        "total_gross_revenue": 1200.0,
        "total_returns_and_discounts": 50.0,
        "total_direct_crop_costs": 300.0,
        "total_allocated_shared_costs": 100.0,
        "total_cost": 400.0,
        "total_noi": 750.0,
        "overall_margin_pct": 750 / 1150 * 100,
    }

    query = connection.cursor_instance.query.lower()
    assert "from v_crop_cycle_noi v" in query
    assert "v.location_id = %s" in query
    assert "cc.planting_date >= %s::date" in query
    assert "coalesce(cc.actual_harvest_date, cc.expected_harvest_date) <= %s::date" in query
    assert "from crop_cost_allocation" not in query
    assert "from financial_transaction" not in query
    assert connection.cursor_instance.params == (
        "location-1",
        "2026-01-01",
        "2026-01-01",
        "2026-06-30",
        "2026-06-30",
    )
    assert connection.cursor_instance.closed is True


def test_crop_noi_report_returns_zero_summary_for_empty_view():
    report = generate_crop_noi(CropNoiConnection([]), "location-1")

    assert report["crop_cycles"] == []
    assert report["summary"] == {
        "total_revenue": 0,
        "total_gross_revenue": 0,
        "total_returns_and_discounts": 0,
        "total_direct_crop_costs": 0,
        "total_allocated_shared_costs": 0,
        "total_cost": 0,
        "total_noi": 0,
        "overall_margin_pct": 0,
    }
