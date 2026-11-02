"""Migration-601 currency grouping contract for nutrient input summaries."""

from services.analytics.nutrient_budget import get_input_summary


class _Cursor:
    description = [
        ("input_type",),
        ("event_count",),
        ("total_nitrogen_kg",),
        ("total_phosphorus_kg",),
        ("total_potassium_kg",),
        ("total_cost",),
        ("avg_application_rate",),
        ("rate_unit",),
        ("cost_currency_code",),
        ("unclassified_cost_count",),
    ]

    def __init__(self, rows):
        self.rows = rows
        self.operation = None
        self.closed = False

    def execute(self, query, params):
        self.operation = (" ".join(query.split()), params)

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def test_get_input_summary_preserves_currency_and_unit_groups_in_stable_order():
    cursor = _Cursor([
        (
            "fertilizer", 1, 1, 0, 0, 40, None, "L/ha", "EUR", 1,
        ),
        (
            "fertilizer", 2, 10, 2, 3, 100, 20, "kg/ha", "USD", 0,
        ),
    ])

    result = get_input_summary(_Connection(cursor), "budget-1")

    query, params = cursor.operation
    assert query.startswith(
        "SELECT input_type, event_count, total_nitrogen_kg, "
        "total_phosphorus_kg, total_potassium_kg, total_cost, "
        "avg_application_rate, rate_unit, cost_currency_code, "
        "unclassified_cost_count FROM v_nutrient_input_summary"
    )
    assert "WHERE budget_id = %s ORDER BY input_type, rate_unit, cost_currency_code" in query
    assert params == ("budget-1",)
    assert result == {
        "budget_id": "budget-1",
        "summary": [
            {
                "input_type": "fertilizer",
                "event_count": 1,
                "nitrogen_kg": 1.0,
                "phosphorus_kg": 0.0,
                "potassium_kg": 0.0,
                "total_cost": 40.0,
                "cost_currency_code": "EUR",
                "unclassified_cost_count": 1,
                "avg_application_rate": None,
                "rate_unit": "L/ha",
            },
            {
                "input_type": "fertilizer",
                "event_count": 2,
                "nitrogen_kg": 10.0,
                "phosphorus_kg": 2.0,
                "potassium_kg": 3.0,
                "total_cost": 100.0,
                "cost_currency_code": "USD",
                "unclassified_cost_count": 0,
                "avg_application_rate": 20.0,
                "rate_unit": "kg/ha",
            },
        ],
    }
    assert cursor.closed
