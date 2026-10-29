"""Prefect adapter fan-out uses only the owner-confirmed operating tenant."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.core.jobs import kokonut_network_location_ids, run_job_for_kokonut_network_locations


def test_location_inventory_uses_readonly_connection_and_canonical_owner_filter():
    first_id, second_id = uuid4(), uuid4()
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.__exit__.return_value = False
    connection.execute.return_value.all.return_value = [{"id": first_id}, {"id": second_id}]

    with patch("services.common.database.get_connection", return_value=connection) as get_connection:
        assert kokonut_network_location_ids() == [str(first_id), str(second_id)]

    get_connection.assert_called_once_with(readonly=True)
    sql, params = connection.execute.call_args.args
    assert "organization.org_key = :org_key" in sql
    assert "location.status = 'active'" in sql
    assert "organization.status = 'active'" in sql
    assert params == {"org_key": "kokonut-network"}


def test_location_fanout_runs_one_required_scope_per_location():
    locations = [str(uuid4()), str(uuid4())]

    with (
        patch("services.core.jobs.kokonut_network_location_ids", return_value=locations),
        patch("services.core.jobs.run_job", side_effect=[{"status": "success", "output": "one"}, {"status": "success", "output": "two"}]) as run_job,
    ):
        result = run_job_for_kokonut_network_locations("metrics")

    assert result["status"] == "success"
    assert result["locations_processed"] == 2
    assert [item["location_id"] for item in result["results"]] == locations
    assert [item["output"] for item in result["results"]] == ["one", "two"]
    assert run_job.call_args_list == [
        (("metrics",), {"location_id": location_id}) for location_id in locations
    ]


def test_empty_owner_inventory_skips_without_spawning_jobs():
    with (
        patch("services.core.jobs.kokonut_network_location_ids", return_value=[]),
        patch("services.core.jobs.run_job") as run_job,
    ):
        result = run_job_for_kokonut_network_locations("credit_adjustment")

    assert result == {
        "status": "skipped",
        "reason": "No active Kokonut Network locations are assigned",
    }
    run_job.assert_not_called()


def test_fanout_refuses_a_global_job_without_location_input_contract():
    with pytest.raises(ValueError, match="is not location-scoped"):
        run_job_for_kokonut_network_locations("dashboards")


def test_fanout_rejects_additional_required_inputs_before_location_lookup():
    with (
        patch(
            "services.core.jobs.kokonut_network_location_ids",
            side_effect=AssertionError("unsupported fan-out must fail before inventory lookup"),
        ) as location_ids,
        patch(
            "services.core.jobs.run_job",
            side_effect=AssertionError("unsupported fan-out must not start jobs"),
        ) as run_job,
    ):
        with pytest.raises(ValueError, match="driver_instance_id"):
            run_job_for_kokonut_network_locations("sensors")

    location_ids.assert_not_called()
    run_job.assert_not_called()


def test_weather_flow_without_argument_uses_owner_scoped_fanout():
    from services.flows.weather import weather_ingestion_flow

    with patch(
        "services.flows.weather.run_job_for_kokonut_network_locations",
        return_value={"status": "success"},
    ) as fanout:
        result = weather_ingestion_flow.fn()

    assert result == {"status": "success"}
    fanout.assert_called_once_with("weather")


def test_climate_refresh_uses_owner_scoped_locations():
    from services.core.climate_jobs import refresh_active_locations

    location_id = str(uuid4())
    with (
        patch("services.core.climate_jobs.kokonut_network_location_ids", return_value=[location_id]),
        patch("services.core.climate_jobs.run_job", return_value={"output": "refreshed"}) as run_job,
    ):
        result = refresh_active_locations()

    assert result == {
        "status": "success",
        "locations": 1,
        "failed": 0,
        "results": [{"location_id": location_id, "returncode": 0, "output": "refreshed"}],
    }
    run_job.assert_called_once_with("climate", location_id=location_id)
