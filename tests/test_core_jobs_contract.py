"""The shared job dispatcher must preserve the fixed command contract."""

import subprocess
import sys
from unittest.mock import patch

import pytest

from services.core.jobs import (
    JOBS,
    JobFailed,
    run_job,
    run_job_for_eas_chains,
    run_job_for_indexing_chains,
    run_job_for_rpc_chains,
)

_LOCATION_ID = "a9aa6466-0754-4b7c-b20c-155a81134eaa"


def _job_inputs(job_id):
    required = JOBS[job_id].required_inputs
    inputs = {}
    if "location_id" in required:
        inputs["location_id"] = _LOCATION_ID
    if "chain" in required:
        inputs["chain"] = "celo"
    return inputs


_DISPATCHES = [(job_id, _job_inputs(job_id)) for job_id in JOBS if job_id != "sensors"]


@pytest.mark.parametrize(("job_id", "job_inputs"), _DISPATCHES)
def test_job_dispatch_uses_catalog_interpreter_arguments_and_timeout(job_id, job_inputs):
    spec = JOBS[job_id]
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="complete", stderr="")
    expected_argv = [sys.executable, "-m", spec.module, *spec.arguments]
    if "location_id" in job_inputs:
        expected_argv.extend(("--location-id", job_inputs["location_id"]))
    if "chain" in job_inputs:
        expected_argv.extend(("--chain", job_inputs["chain"]))

    child_env = {"PATH": "/synthetic/bin"}
    with (
        patch("services.core.jobs.worker_subprocess_environment", return_value=child_env),
        patch("services.core.jobs.subprocess.run", return_value=completed) as run,
    ):
        result = run_job(job_id, **job_inputs)

    run.assert_called_once_with(
        expected_argv,
        capture_output=True,
        text=True,
        timeout=spec.timeout_seconds,
        env=child_env,
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


def test_weather_dispatch_uses_signed_worker_and_exact_environment_allowlist():
    spec = JOBS["weather"]
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
    with patch("services.core.jobs.worker_subprocess_environment", return_value={"PATH": "/bin"}) as env, \
            patch("services.core.jobs.subprocess.run", return_value=completed) as run:
        assert run_job("weather", location_id=_LOCATION_ID)["status"] == "success"

    run.assert_called_once()
    assert run.call_args.args[0] == [
        sys.executable, "-m", "services.ingestion.weather_worker",
        "--location-id", _LOCATION_ID,
    ]
    env.assert_called_once_with(
        allowed_worker_keys=("weather",), isolated_database_credentials=True
    )
    assert spec.module == "services.ingestion.weather_worker"


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


def test_remote_sensing_dispatch_requires_one_location_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="requires a location"):
            run_job("remote_sensing")

    run.assert_not_called()


def test_eas_dispatch_requires_one_explicit_chain_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="EAS indexing refresh requires a chain"):
            run_job("eas")

    run.assert_not_called()


def test_eas_dispatch_rejects_unsupported_chain_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="EAS chain is not supported"):
            run_job("eas", chain="ethereum")

    run.assert_not_called()


def test_rpc_dispatch_requires_one_explicit_chain_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="RPC indexing refresh requires a chain"):
            run_job("rpc")

    run.assert_not_called()


def test_rpc_dispatch_rejects_unsupported_chain_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="RPC chain is not supported"):
            run_job("rpc", chain="polygon")

    run.assert_not_called()


def test_eas_multi_chain_adapter_runs_celo_first_with_explicit_scope():
    from unittest.mock import call

    results = [
        {"status": "success", "output": chain}
        for chain in ("celo", "optimism", "base")
    ]
    with patch("services.core.jobs.run_job", side_effect=results) as run:
        result = run_job_for_eas_chains()

    assert run.call_args_list == [
        call("eas", chain="celo"),
        call("eas", chain="optimism"),
        call("eas", chain="base"),
    ]
    assert result == {
        "status": "success",
        "chains_processed": 3,
        "results": [
            {"chain": "celo", **results[0]},
            {"chain": "optimism", **results[1]},
            {"chain": "base", **results[2]},
        ],
    }


def test_eas_chain_adapter_rejects_unrelated_job():
    with pytest.raises(ValueError, match="not chain-scoped"):
        run_job_for_indexing_chains("weather")


def test_rpc_multi_chain_adapter_preserves_all_configured_networks():
    from unittest.mock import call

    chains = ("ethereum", "optimism", "base", "arbitrum", "celo", "celo-alfajores", "gnosis")
    results = [{"status": "success", "output": chain} for chain in chains]
    with patch("services.core.jobs.run_job", side_effect=results) as run:
        result = run_job_for_rpc_chains()

    assert run.call_args_list == [call("rpc", chain=chain) for chain in chains]
    assert result["status"] == "success"
    assert result["chains_processed"] == len(chains)
    assert [item["chain"] for item in result["results"]] == list(chains)


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


def test_sensor_job_requires_a_location_and_driver_before_subprocess():
    with patch("services.core.jobs.subprocess.run") as run:
        with pytest.raises(ValueError, match="requires a location and a driver instance"):
            run_job("sensors")

    run.assert_not_called()
