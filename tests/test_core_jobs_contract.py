"""The shared job dispatcher must preserve the fixed command contract."""

import subprocess
import sys
from unittest.mock import patch

import pytest

from services.core.jobs import JOBS, JobFailed, run_job
from services.security.scheduled_command_contracts import ScheduledCommandRejected

_LOCATION_ID = "a9aa6466-0754-4b7c-b20c-155a81134eaa"
_DISPATCHES = [
    (job_id, _LOCATION_ID if "location_id" in JOBS[job_id].required_inputs else None)
    for job_id in JOBS
    if job_id != "sensors"
]


@pytest.mark.parametrize(("job_id", "location_id"), _DISPATCHES)
def test_job_dispatch_uses_catalog_interpreter_arguments_and_timeout(job_id, location_id):
    spec = JOBS[job_id]
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="complete", stderr="")
    expected_argv = [sys.executable, "-m", spec.module, *spec.arguments]
    if location_id is not None:
        expected_argv.extend(("--location-id", location_id))

    with patch("services.core.jobs.subprocess.run", return_value=completed) as run:
        result = run_job(job_id, location_id=location_id)

    run.assert_called_once_with(
        expected_argv,
        capture_output=True,
        text=True,
        timeout=spec.timeout_seconds,
    )
    assert result == {"status": "success", "output": "complete"}


def test_climate_dispatch_requires_a_location_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="requires a location"):
            run_job("climate")

    run.assert_not_called()


def test_weather_dispatch_requires_a_location_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="requires a location"):
            run_job("weather")

    run.assert_not_called()


def test_credit_adjustment_dispatch_requires_one_location_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="requires a location"):
            run_job("credit_adjustment")

    run.assert_not_called()


def test_metrics_dispatch_requires_one_location_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="requires a location"):
            run_job("metrics")

    run.assert_not_called()


def test_nonzero_job_exit_retains_return_code_and_bounded_output():
    provider_error = "provider failed " + ("x" * 600)
    completed = subprocess.CompletedProcess(args=[], returncode=7, stdout="ignored", stderr=provider_error)

    with (
        patch("services.core.jobs.subprocess.run", return_value=completed),
        pytest.raises(JobFailed) as error,
    ):
        run_job("weather", location_id=_LOCATION_ID)

    assert error.value.returncode == 7
    assert error.value.output == provider_error[-500:]
    assert len(error.value.output) == 500


def test_source_less_sensor_job_is_rejected_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ScheduledCommandRejected, match="no recurring source contract"):
            run_job("sensors")

    run.assert_not_called()
