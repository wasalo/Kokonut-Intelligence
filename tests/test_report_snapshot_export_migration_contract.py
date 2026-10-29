import importlib.util
from pathlib import Path
from types import SimpleNamespace

import yaml

from services.migration import runtime_role

ROOT = Path(__file__).resolve().parents[1]
_CHECKER_SPEC = importlib.util.spec_from_file_location(
    "check_report_snapshot_export_disposable",
    ROOT / "scripts/check-report-snapshot-export-disposable.py",
)
assert _CHECKER_SPEC is not None and _CHECKER_SPEC.loader is not None
_CHECKER = importlib.util.module_from_spec(_CHECKER_SPEC)
_CHECKER_SPEC.loader.exec_module(_CHECKER)


def test_disposable_readiness_probe_survives_postgres_initdb_handoff(monkeypatch):
    calls = []
    results = [
        SimpleNamespace(returncode=1, stdout="", stderr="temporary server stopped"),
        SimpleNamespace(returncode=0, stdout="1\n", stderr=""),
    ]

    def run(command, **_kwargs):
        calls.append(command)
        return results.pop(0)

    monkeypatch.setattr(_CHECKER.subprocess, "run", run)
    monkeypatch.setattr(_CHECKER.time, "sleep", lambda _seconds: None)

    _CHECKER.wait_ready("docker", "synthetic-postgres")

    assert len(calls) == 2
    assert calls[0][-1] == "SELECT pg_sleep(2); SELECT 1"
    assert calls[1][-1] == calls[0][-1]


def test_report_snapshot_export_role_function_allowlists_are_separate():
    assert runtime_role._REPORT_SNAPSHOT_EXPORT_RUNTIME_FUNCTIONS == (
        "kokonut_security.request_report_snapshot_export(uuid,uuid,uuid)",
        "kokonut_security.list_report_snapshot_exports(uuid,integer)",
        "kokonut_security.get_report_snapshot_export(uuid,uuid)",
        "kokonut_security.authorize_report_snapshot_export_download(uuid,uuid)",
    )
    assert runtime_role._REPORT_SNAPSHOT_EXPORT_WORKER_FUNCTIONS == (
        "kokonut_security.claim_report_snapshot_export_batch(text,integer,integer)",
        "kokonut_security.read_report_snapshot_export_source(uuid,text,uuid)",
        "kokonut_security.finish_report_snapshot_export_attempt(uuid,text,uuid,boolean,text,integer,uuid,text,bigint)",
    )
    assert set(runtime_role._REPORT_SNAPSHOT_EXPORT_RUNTIME_FUNCTIONS).isdisjoint(
        runtime_role._REPORT_SNAPSHOT_EXPORT_WORKER_FUNCTIONS
    )


def test_runtime_role_reapplies_user_grants_and_worker_login_allowlist():
    source = (ROOT / "services/migration/runtime_role.py").read_text()
    assert "report_snapshot_export_user: str | None = None" in source
    assert "report_snapshot_export_password: str | None = None" in source
    assert "KOKONUT_REPORT_SNAPSHOT_EXPORT_USER" in source
    assert "KOKONUT_REPORT_SNAPSHOT_EXPORT_PASSWORD" in source
    assert "migration 683 report snapshot export functions must be applied" in source
    assert "_verify_bounded_indexer_login(" in source
    assert "_REPORT_SNAPSHOT_EXPORT_WORKER_FUNCTIONS" in source

    runtime_grant = source.index(
        "for function in _REPORT_SNAPSHOT_EXPORT_RUNTIME_FUNCTIONS:"
    )
    runtime_worker_revoke = source.index(
        "for function in _REPORT_SNAPSHOT_EXPORT_WORKER_FUNCTIONS:", runtime_grant
    )
    assert runtime_grant < runtime_worker_revoke
    assert "report snapshot export login must connect only to its configured database" in source


def test_runtime_role_compose_keeps_export_worker_password_optional():
    compose = yaml.safe_load((ROOT / "docker-compose.kernel-runtime-role.yml").read_text())
    environment = compose["services"]["runtime-role-bootstrap"]["environment"]
    assert environment["KOKONUT_REPORT_SNAPSHOT_EXPORT_USER"] == (
        "${KOKONUT_REPORT_SNAPSHOT_EXPORT_USER:-kokonut_report_snapshot_export_login}"
    )
    assert environment["KOKONUT_REPORT_SNAPSHOT_EXPORT_PASSWORD"] == (
        "${KOKONUT_REPORT_SNAPSHOT_EXPORT_PASSWORD:-}"
    )
