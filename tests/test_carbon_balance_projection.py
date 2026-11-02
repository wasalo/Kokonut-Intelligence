"""Migration-backed projection checks for annual carbon-balance summaries."""

import re

from services.analytics import carbon_balance

SUMMARY_COLUMNS = (
    "above_ground_carbon_tonnes, below_ground_carbon_tonnes, "
    "total_sequestration_tonnes_co2e, total_emissions_tonnes_co2e, "
    "net_climate_impact_tonnes_co2e, reporting_year"
)


class _Cursor:
    def __init__(self, *, one=None, many=None):
        self.one = list(one or [])
        self.many = list(many or [])
        self.operations = []
        self.closed = False

    def execute(self, query, params=()):
        self.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.one.pop(0)

    def fetchall(self):
        return self.many.pop(0)

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.cursor_factory = None

    def cursor(self, *, cursor_factory=None):
        self.cursor_factory = cursor_factory
        return self._cursor


def _summary_projection(query):
    return re.search(r"SELECT (.*?) FROM climate_impact_summary", query).group(1)


def test_carbon_balance_year_query_uses_exact_projection_and_preserves_payload():
    cursor = _Cursor(one=[{
        "above_ground_carbon_tonnes": 2.5,
        "below_ground_carbon_tonnes": 3.0,
        "total_sequestration_tonnes_co2e": 5.5,
        "total_emissions_tonnes_co2e": 1.2,
        "net_climate_impact_tonnes_co2e": 4.3,
        "reporting_year": 2025,
    }])
    connection = _Connection(cursor)

    result = carbon_balance.compute_carbon_balance(connection, "location-1", 2025)

    query, params = cursor.operations[0]
    assert _summary_projection(query) == SUMMARY_COLUMNS
    assert "WHERE location_id = %s AND reporting_year = %s LIMIT 1" in query
    assert params == ("location-1", 2025)
    assert len(cursor.operations) == 1
    assert result == {
        "location_id": "location-1",
        "reporting_year": 2025,
        "above_ground_carbon_tonnes": 2.5,
        "below_ground_carbon_tonnes": 3.0,
        "total_sequestration_tonnes_co2e": 5.5,
        "total_emissions_tonnes_co2e": 1.2,
        "net_climate_impact_tonnes_co2e": 4.3,
        "carbon_position": "net_sequester",
    }
    assert cursor.closed


def test_carbon_balance_latest_query_keeps_location_bind_and_year_order():
    cursor = _Cursor(one=[{
        "above_ground_carbon_tonnes": 1.25,
        "below_ground_carbon_tonnes": 0.5,
        "total_sequestration_tonnes_co2e": 1.75,
        "total_emissions_tonnes_co2e": 2.0,
        "net_climate_impact_tonnes_co2e": -0.25,
        "reporting_year": 2024,
    }])
    connection = _Connection(cursor)

    result = carbon_balance.compute_carbon_balance(connection, "location-2")

    query, params = cursor.operations[0]
    assert _summary_projection(query) == SUMMARY_COLUMNS
    assert "WHERE location_id = %s ORDER BY reporting_year DESC LIMIT 1" in query
    assert params == ("location-2",)
    assert result == {
        "location_id": "location-2",
        "reporting_year": 2024,
        "above_ground_carbon_tonnes": 1.25,
        "below_ground_carbon_tonnes": 0.5,
        "total_sequestration_tonnes_co2e": 1.75,
        "total_emissions_tonnes_co2e": 2.0,
        "net_climate_impact_tonnes_co2e": -0.25,
        "carbon_position": "net_emitter",
    }
    assert cursor.closed


def test_carbon_balance_missing_summary_keeps_existing_live_data_fallback():
    cursor = _Cursor(
        one=[None, {"total_co2e": 2.0}, {"total_emissions": 1.0}],
        many=[[{"plot_id": "plot-1", "carbon_tonnes_per_ha": 5.0},
               {"plot_id": "plot-1", "carbon_tonnes_per_ha": 6.0}]],
    )
    connection = _Connection(cursor)

    result = carbon_balance.compute_carbon_balance(connection, "location-3", 2023)

    first_query, first_params = cursor.operations[0]
    assert _summary_projection(first_query) == SUMMARY_COLUMNS
    assert "WHERE location_id = %s AND reporting_year = %s LIMIT 1" in first_query
    assert first_params == ("location-3", 2023)
    assert "FROM tree_inventory" in cursor.operations[1][0]
    assert cursor.operations[1][1] == ("location-3",)
    assert "FROM soil_carbon_measurement" in cursor.operations[2][0]
    assert cursor.operations[2][1] == ("location-3",)
    assert "FROM ghg_emissions_inventory" in cursor.operations[3][0]
    assert cursor.operations[3][1] == ("location-3",)
    assert result == {
        "location_id": "location-3",
        "reporting_year": 2023,
        "above_ground_carbon_tonnes": 2.0,
        "below_ground_carbon_tonnes": 3.67,
        "total_sequestration_tonnes_co2e": 5.67,
        "total_emissions_tonnes_co2e": 1.0,
        "net_climate_impact_tonnes_co2e": 4.67,
        "carbon_position": "net_sequester",
    }
    assert cursor.closed
