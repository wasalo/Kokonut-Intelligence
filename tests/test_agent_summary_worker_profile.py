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
    assert "KOKONUT_AGENT_SUMMARY_DETERMINISTIC_SOURCE_WORKER_CREDENTIAL" in service["environment"]
    assert "KOKONUT_AGENT_SUMMARY_DRAFT_DATABASE_URL" in service["environment"]
    assert "KOKONUT_AGENT_SUMMARY_DRAFT_WORKER_CREDENTIAL" in service["environment"]


def test_summary_inspection_profile_uses_only_its_signed_source_identity():
    service = _services()["ai-summary-inspection-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.ai_summary",
    ]
    assert service["profiles"] == ["ai-summary-inspection-worker"]
    _assert_no_shared_database_environment(service)
    assert set(service["environment"]) == {
        "KOKONUT_ENV",
        "KOKONUT_AGENT_SUMMARY_INSPECTION_SOURCE_DATABASE_URL",
        "KOKONUT_AGENT_SUMMARY_INSPECTION_SOURCE_WORKER_CREDENTIAL",
        "PYTHONDONTWRITEBYTECODE",
    }


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
    assert "KOKONUT_AGENT_SUMMARY_SOURCE_WORKER_CREDENTIAL" in service["environment"]
    assert "KOKONUT_AGENT_SUMMARY_DRAFT_DATABASE_URL" in service["environment"]


def test_organic_readiness_profile_uses_only_its_source_and_draft_identities():
    service = _services()["agent-organic-readiness-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.worker_cli",
        "--source-only",
        "--task-key",
        "organic_readiness_synthesis",
    ]
    assert service["profiles"] == ["organic-readiness-worker"]
    _assert_no_shared_database_environment(service)
    assert set(service["environment"]) == {
        "KOKONUT_ENV",
        "KOKONUT_AGENT_ORGANIC_READINESS_SOURCE_DATABASE_URL",
        "KOKONUT_AGENT_ORGANIC_READINESS_SOURCE_WORKER_CREDENTIAL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_DATABASE_URL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_WORKER_CREDENTIAL",
        "PYTHONDONTWRITEBYTECODE",
    }


def test_ecological_modeling_profile_uses_only_its_source_and_draft_identities():
    service = _services()["agent-ecological-modeling-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.worker_cli",
        "--source-only",
        "--task-key",
        "ecological_modeling_synthesis",
    ]
    assert service["profiles"] == ["ecological-modeling-worker"]
    _assert_no_shared_database_environment(service)
    assert set(service["environment"]) == {
        "KOKONUT_ENV",
        "KOKONUT_AGENT_ECOLOGICAL_MODELING_SOURCE_DATABASE_URL",
        "KOKONUT_AGENT_ECOLOGICAL_MODELING_SOURCE_WORKER_CREDENTIAL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_DATABASE_URL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_WORKER_CREDENTIAL",
        "PYTHONDONTWRITEBYTECODE",
    }


def test_holistic_wellbeing_profile_uses_only_its_source_and_draft_identities():
    service = _services()["agent-holistic-wellbeing-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.worker_cli",
        "--source-only",
        "--task-key",
        "holistic_wellbeing_synthesis",
    ]
    assert service["profiles"] == ["holistic-wellbeing-worker"]
    _assert_no_shared_database_environment(service)
    assert set(service["environment"]) == {
        "KOKONUT_ENV",
        "KOKONUT_AGENT_HOLISTIC_WELLBEING_SOURCE_DATABASE_URL",
        "KOKONUT_AGENT_HOLISTIC_WELLBEING_SOURCE_WORKER_CREDENTIAL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_DATABASE_URL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_WORKER_CREDENTIAL",
        "PYTHONDONTWRITEBYTECODE",
    }


def test_feedback_profile_uses_only_its_source_and_draft_identities():
    service = _services()["agent-feedback-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.worker_cli",
        "--source-only",
        "--task-key",
        "feedback_synthesis",
    ]
    assert service["profiles"] == ["feedback-worker"]
    _assert_no_shared_database_environment(service)
    assert set(service["environment"]) == {
        "KOKONUT_ENV",
        "KOKONUT_AGENT_FEEDBACK_SOURCE_DATABASE_URL",
        "KOKONUT_AGENT_FEEDBACK_SOURCE_WORKER_CREDENTIAL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_DATABASE_URL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_WORKER_CREDENTIAL",
        "PYTHONDONTWRITEBYTECODE",
    }


def test_commons_liberation_profile_uses_only_its_source_and_draft_identities():
    service = _services()["agent-commons-liberation-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.worker_cli",
        "--source-only",
        "--task-key",
        "commons_liberation_synthesis",
    ]
    assert service["profiles"] == ["commons-liberation-worker"]
    _assert_no_shared_database_environment(service)
    assert set(service["environment"]) == {
        "KOKONUT_ENV",
        "KOKONUT_AGENT_COMMONS_LIBERATION_SOURCE_DATABASE_URL",
        "KOKONUT_AGENT_COMMONS_LIBERATION_SOURCE_WORKER_CREDENTIAL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_DATABASE_URL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_WORKER_CREDENTIAL",
        "PYTHONDONTWRITEBYTECODE",
    }


def test_gnh_alignment_profile_uses_only_its_source_and_draft_identities():
    service = _services()["agent-gnh-alignment-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.worker_cli",
        "--source-only",
        "--task-key",
        "gnh_alignment_synthesis",
    ]
    assert service["profiles"] == ["gnh-alignment-worker"]
    _assert_no_shared_database_environment(service)
    assert set(service["environment"]) == {
        "KOKONUT_ENV",
        "KOKONUT_AGENT_GNH_ALIGNMENT_SOURCE_DATABASE_URL",
        "KOKONUT_AGENT_GNH_ALIGNMENT_SOURCE_WORKER_CREDENTIAL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_DATABASE_URL",
        "KOKONUT_AGENT_SUMMARY_DRAFT_WORKER_CREDENTIAL",
        "PYTHONDONTWRITEBYTECODE",
    }


def test_ebf_evidence_gap_profile_uses_only_its_signed_source_identity():
    service = _services()["ebf-evidence-gap-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.ebf_evidence_gap_agent",
    ]
    assert service["profiles"] == ["ebf-evidence-gap-worker"]
    _assert_no_shared_database_environment(service)
    assert set(service["environment"]) == {
        "KOKONUT_ENV",
        "KOKONUT_AGENT_EBF_SOURCE_DATABASE_URL",
        "KOKONUT_AGENT_EBF_SOURCE_WORKER_CREDENTIAL",
        "PYTHONDONTWRITEBYTECODE",
    }


def test_delphi_agent_profile_uses_only_its_signed_source_identity():
    service = _services()["delphi-agent-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.delphi_facilitator_agent",
    ]
    assert service["profiles"] == ["delphi-agent-worker"]
    _assert_no_shared_database_environment(service)
    assert set(service["environment"]) == {
        "KOKONUT_ENV",
        "KOKONUT_AGENT_DELPHI_SOURCE_DATABASE_URL",
        "KOKONUT_AGENT_DELPHI_SOURCE_WORKER_CREDENTIAL",
        "PYTHONDONTWRITEBYTECODE",
    }


def test_cids_export_profile_uses_only_its_signed_source_identity():
    service = _services()["cids-export-worker"]

    assert service["entrypoint"] == [
        "python3",
        "-m",
        "services.agents.cids_agent",
    ]
    assert service["profiles"] == ["cids-export-worker"]
    _assert_no_shared_database_environment(service)
    assert set(service["environment"]) == {
        "KOKONUT_ENV",
        "KOKONUT_AGENT_CIDS_SOURCE_DATABASE_URL",
        "KOKONUT_AGENT_CIDS_SOURCE_WORKER_CREDENTIAL",
        "PYTHONDONTWRITEBYTECODE",
    }
