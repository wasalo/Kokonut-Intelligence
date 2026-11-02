"""The credit issuer reads the annual migration-028 climate summary contract."""

from unittest.mock import Mock

from services.analytics.carbon_credits import _query_climate_impact


def test_climate_impact_lookup_uses_annual_location_vintage_projection():
    location_id = "00000000-0000-4000-8000-000000000001"
    row = {
        "id": "00000000-0000-4000-8000-000000000002",
        "location_id": location_id,
        "reporting_year": 2026,
        "total_sequestration_tonnes_co2e": 42.5,
        "status": "verified",
    }
    cursor = Mock()
    cursor.fetchone.return_value = row
    connection = Mock()
    connection.cursor.return_value = cursor

    result = _query_climate_impact(connection, location_id, 2026)

    sql = " ".join(cursor.execute.call_args.args[0].split())
    assert sql.startswith(
        "SELECT id, location_id, reporting_year, "
        "total_sequestration_tonnes_co2e, status FROM climate_impact_summary"
    )
    assert "location_id = %s AND reporting_year = %s" in sql
    assert "status IN ('verified', 'published')" in sql
    assert "period_start" not in sql and "period_end" not in sql
    assert "ORDER BY" not in sql
    assert cursor.execute.call_args.args[1] == (location_id, 2026)
    assert result == row
    cursor.close.assert_called_once_with()
