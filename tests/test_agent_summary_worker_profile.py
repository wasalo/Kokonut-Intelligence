"""Compose contract for dedicated AI-summary source-reader identities."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _services():
    compose = yaml.safe_load((ROOT / "docker-compose.worker.yml").read_text())
    return compose["services"]


def _assert_no_shared_database_environment(service):
    environment = service["environment"]
    assert not any(
        key.startswith("PG_")
        or key in {"DATABASE_URL", "POSTGRES_PASSWORD"}
        for key in environment
    )


def test_deterministic_summary_profile_uses_only_its_source_and_draft_identities():
    service = _services()["agent-summary-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.worker_cli",
        "--deterministic-only",
    ]
    assert service["profiles"] == ["agent-summary-worker"]
    _assert_no_shared_database_environment(service)
    assert "KOKONUT_AGENT_SUMMARY_DETERMINISTIC_SOURCE_DATABASE_URL" in service["environment"]
    assert "KOKONUT_AGENT_SUMMARY_DRAFT_DATABASE_URL" in service["environment"]
    assert "KOKONUT_AGENT_SUMMARY_DRAFT_WORKER_CREDENTIAL" in service["environment"]


def test_shared_synthesis_profile_remains_separate_and_source_only():
    service = _services()["agent-synthesis-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.worker_cli",
        "--source-only",
    ]
    assert service["profiles"] == ["agent-synthesis-worker"]
    _assert_no_shared_database_environment(service)
    assert "KOKONUT_AGENT_SUMMARY_SOURCE_DATABASE_URL" in service["environment"]
    assert "KOKONUT_AGENT_SUMMARY_DRAFT_DATABASE_URL" in service["environment"]
