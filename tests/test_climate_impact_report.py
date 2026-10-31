"""Focused contract tests for the climate-impact report's database reads."""

import pytest

from services.export.reports import core


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, query, params=None):
        placeholder_count = query.count("%s")
        parameter_count = len(params or ())
        if placeholder_count != parameter_count:
            raise AssertionError(
                f"query has {placeholder_count} placeholders but received {parameter_count} parameters"
            )

        normalized = " ".join(query.split())
        self.connection.queries.append((normalized, params))
        if "SELECT name FROM location" in normalized:
            self.rows = [{"name": "Kokonut Genesis"}]
        elif "FROM climate_impact_summary" in normalized:
            self.rows = (
                [self.connection.summary_row]
                if self.connection.summary_row is not None
                else []
            )
        elif "FROM framework_phase" in normalized:
            self.rows = []
        elif "FROM operations_protocol" in normalized:
            self.rows = [
                {
                    "title": "Soil Protocol",
                    "section": "soil_management",
                    "version": "1.0",
                }
            ]
        else:
            raise AssertionError(f"unexpected climate-impact query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _Connection:
    def __init__(self, summary_row=None):
        self.queries = []
        self.summary_row = summary_row

    def cursor(self, **_kwargs):
        return _Cursor(self)


@pytest.mark.parametrize(
    "location_id",
    [None, "", "all", "not-a-uuid", "11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222"],
)
def test_climate_impact_rejects_non_location_scope_before_opening_database(location_id):
    class _NoDatabase:
        def cursor(self, **_kwargs):
            raise AssertionError("database must not open without a location scope")

    with pytest.raises(ValueError, match="climate_impact requires an explicit location_id"):
        core.generate_climate_impact(_NoDatabase(), location_id)


def test_climate_impact_uses_shared_protocols_without_location_parameter(monkeypatch):
    from services.analytics import carbon_balance

    monkeypatch.setattr(carbon_balance, "compute_carbon_balance", lambda *_args: {})
    monkeypatch.setattr(carbon_balance, "compute_ghg_emissions", lambda *_args: {})
    monkeypatch.setattr(carbon_balance, "compute_tree_carbon", lambda *_args: {})
    monkeypatch.setattr(carbon_balance, "compute_regenerative_score", lambda *_args: {})
    connection = _Connection()

    result = core.generate_climate_impact(
        connection,
        "11111111-1111-4111-8111-111111111111",
        period_start="2025-01-01",
    )

    protocol_query, protocol_params = next(
        (query, params)
        for query, params in connection.queries
        if "FROM operations_protocol" in query
    )
    assert "WHERE status = 'active'" in protocol_query
    assert protocol_params is None
    assert result["location_name"] == "Kokonut Genesis"
    assert result["operations_protocols"] == [
        {"title": "Soil Protocol", "section": "soil_management", "version": "1.0"}
    ]
    assert result["limitations"] == [
        "Active operations protocols are shared platform reference metadata, not location-specific evidence."
    ]


def test_climate_impact_projects_all_current_stored_summary_columns(monkeypatch):
    from services.analytics import carbon_balance

    monkeypatch.setattr(carbon_balance, "compute_carbon_balance", lambda *_args: {})
    monkeypatch.setattr(carbon_balance, "compute_ghg_emissions", lambda *_args: {})
    monkeypatch.setattr(carbon_balance, "compute_tree_carbon", lambda *_args: {})
    monkeypatch.setattr(carbon_balance, "compute_regenerative_score", lambda *_args: {})
    columns = [
        "id",
        "location_id",
        "reporting_year",
        "above_ground_carbon_tonnes",
        "below_ground_carbon_tonnes",
        "total_sequestration_tonnes_co2e",
        "transport_emissions_tonnes_co2e",
        "machinery_emissions_tonnes_co2e",
        "input_emissions_tonnes_co2e",
        "total_emissions_tonnes_co2e",
        "net_climate_impact_tonnes_co2e",
        "species_count",
        "shannon_index",
        "regenerative_score_total",
        "methodology_version",
        "data_quality_score",
        "status",
        "reviewed_by",
        "reviewed_at",
        "notes",
        "source_system",
        "source_id",
        "created_at",
        "updated_at",
    ]
    summary_row = {column: f"value-{index}" for index, column in enumerate(columns)}
    connection = _Connection(summary_row=summary_row)

    result = core.generate_climate_impact(
        connection,
        "11111111-1111-4111-8111-111111111111",
        period_start="2025-01-01",
    )

    summary_query, summary_params = next(
        (query, params)
        for query, params in connection.queries
        if "FROM climate_impact_summary" in query
    )
    projection = summary_query.split(" FROM ", maxsplit=1)[0]
    assert projection == "SELECT " + ", ".join(columns)
    assert summary_params == ("11111111-1111-4111-8111-111111111111", 2025)
    assert result["stored_summary"] == summary_row
