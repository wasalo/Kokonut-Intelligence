"""Exercise the optional Prefect adapter against its local test runtime only."""

from __future__ import annotations

from dataclasses import replace
from importlib import import_module
from pathlib import Path
from threading import Barrier, BrokenBarrierError, Event, Lock, Thread
from time import sleep
from typing import Iterator

import pytest


@pytest.fixture(scope="module", autouse=True)
def prefect_test_backend() -> Iterator[None]:
    pytest.importorskip("prefect")
    from prefect.testing.utilities import prefect_test_harness

    with prefect_test_harness(server_startup_timeout=60):
        yield


def test_monitoring_pipeline_submits_parallel_tasks_to_prefect_runner(monkeypatch) -> None:
    from services.flows import pipelines

    barrier = Barrier(2)
    lock = Lock()
    started: list[str] = []

    def execute(job_id: str) -> dict[str, str]:
        with lock:
            started.append(job_id)
        try:
            barrier.wait(timeout=10)
        except BrokenBarrierError as exc:
            raise AssertionError("monitoring tasks did not run concurrently") from exc
        return {"job_id": job_id}

    monkeypatch.setattr(pipelines, "_dispatch_catalog_job", execute)

    assert pipelines.monitoring_pipeline() == {
        "status": "success",
        "monitoring": "complete",
    }
    assert set(started) == {"anomaly", "freshness"}


def test_analytics_pipeline_waits_for_metrics_before_dependent_tasks(monkeypatch) -> None:
    from services.flows import pipelines

    metrics_started = Event()
    allow_metrics_to_finish = Event()
    metrics_finished = Event()
    started: list[str] = []
    lock = Lock()

    def execute(job_id: str) -> dict[str, str]:
        if job_id == "metrics":
            with lock:
                started.append(job_id)
            metrics_started.set()
            assert allow_metrics_to_finish.wait(timeout=10)
            metrics_finished.set()
        else:
            with lock:
                started.append(job_id)
            assert metrics_finished.is_set()
        return {"job_id": job_id}

    monkeypatch.setattr(pipelines, "is_enabled", lambda feature: feature == "legacy_dataset_sql")
    monkeypatch.setattr(pipelines, "_dispatch_catalog_job", execute)

    def release_metrics_after_started() -> None:
        assert metrics_started.wait(timeout=10)
        sleep(0.1)
        allow_metrics_to_finish.set()

    release = Thread(target=release_metrics_after_started, daemon=True)
    release.start()
    assert pipelines.analytics_pipeline() == {
        "status": "success",
        "analytics": "complete",
        "dashboard_refresh": {"job_id": "dashboards"},
    }
    release.join(timeout=1)
    assert started[0] == "metrics"
    assert set(started[1:]) == {"dashboards", "credit_adjustment"}


def test_analytics_pipeline_skips_default_off_dashboard_and_continues_credit(monkeypatch) -> None:
    from services.flows import pipelines

    started: list[str] = []

    def execute(job_id: str) -> dict[str, str]:
        started.append(job_id)
        return {"job_id": job_id}

    monkeypatch.setattr(pipelines, "is_enabled", lambda _feature: False)
    monkeypatch.setattr(pipelines, "_dispatch_catalog_job", execute)

    assert pipelines.analytics_pipeline() == {
        "status": "success",
        "analytics": "complete",
        "dashboard_refresh": {
            "status": "skipped",
            "reason": "legacy_dataset_sql_disabled",
        },
    }
    assert started == ["metrics", "credit_adjustment"]


def test_prefect_task_retry_and_failure_propagation_match_job_spec(monkeypatch) -> None:
    from prefect import flow

    from services.core.jobs import JOBS
    from services.flows import pipelines

    jobs = dict(JOBS)
    jobs["weather"] = replace(JOBS["weather"], retries=1, retry_delay_seconds=0)
    monkeypatch.setattr(pipelines, "JOBS", jobs)
    attempts = 0

    def retry_once(_job_id: str) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("synthetic first-attempt failure")
        return "completed-after-retry"

    monkeypatch.setattr(pipelines, "_dispatch_catalog_job", retry_once)

    @flow(name="kernel-runtime-retry-probe")
    def retry_probe() -> str:
        return pipelines._submit_job("weather").result()

    assert retry_probe() == "completed-after-retry"
    assert attempts == 2

    jobs["anomaly"] = replace(JOBS["anomaly"], retries=0, retry_delay_seconds=0)
    jobs["freshness"] = replace(JOBS["freshness"], retries=0, retry_delay_seconds=0)

    def fail_anomaly(job_id: str) -> str:
        if job_id == "anomaly":
            raise RuntimeError("synthetic terminal failure")
        return job_id

    monkeypatch.setattr(pipelines, "_dispatch_catalog_job", fail_anomaly)
    with pytest.raises(RuntimeError, match="synthetic terminal failure"):
        pipelines.monitoring_pipeline()


def test_deployment_names_resolve_to_the_checked_in_prefect_flows() -> None:
    import yaml

    deployment_path = Path("config/prefect/deployment.yaml")
    config = yaml.safe_load(deployment_path.read_text(encoding="utf-8"))

    for deployment in config["deployments"]:
        module_name, attribute = deployment["flow"].split(":", 1)
        flow_object = getattr(import_module(module_name), attribute)
        assert flow_object.name == deployment["name"]

    schedules = {
        deployment["name"]: deployment["schedule"]["cron"]
        for deployment in config["deployments"]
        if "schedule" in deployment
    }
    assert schedules == {
        "scheduled-hourly": "0 * * * *",
        "scheduled-every-6h": "0 */6 * * *",
        "scheduled-daily": "0 6 * * *",
        "scheduled-weekly": "0 3 * * 0",
    }
