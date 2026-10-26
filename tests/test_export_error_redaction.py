"""Export failures and audit-log warnings must not disclose raw details."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.export import exporter as exporter_module
from services.export.exporter import Exporter

SECRET = "database password=private-token and confidential row"


def test_export_failure_redacts_error_and_removes_temporary_file(
    monkeypatch, tmp_path, capsys
):
    exporter = Exporter()
    monkeypatch.setattr(
        exporter,
        "_iter_postgres",
        lambda *_args, **_kwargs: (iter([{"id": "row-1"}]), ["id"]),
    )

    def fail_write(*_args):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(exporter, "_write_csv", fail_write)
    logged = []
    monkeypatch.setattr(exporter, "_log_export", lambda *args: logged.append(args))

    with pytest.raises(RuntimeError, match=r"export failed \(RuntimeError\)") as error:
        exporter.export("harvest_event", output_dir=str(tmp_path))

    assert SECRET not in str(error.value)
    assert SECRET not in capsys.readouterr().out
    assert logged[0][7] == "failed"
    assert list(Path(tmp_path).iterdir()) == []


def test_export_log_connection_failure_is_class_only(monkeypatch, capsys):
    monkeypatch.setattr(
        exporter_module,
        "get_pg",
        lambda: (_ for _ in ()).throw(RuntimeError(SECRET)),
    )

    Exporter()._log_export("harvest_event", "csv", None, 0, 0, "out.csv", None)

    output = capsys.readouterr().out
    assert "WARNING: Failed to log export (RuntimeError)" in output
    assert SECRET not in output


def test_export_log_and_cleanup_failures_are_redacted(monkeypatch, capsys):
    conn = MagicMock()
    cur = conn.cursor.return_value
    cur.execute.side_effect = ValueError(SECRET)
    cur.close.side_effect = RuntimeError(SECRET)
    conn.close.side_effect = OSError(SECRET)
    monkeypatch.setattr(exporter_module, "get_pg", lambda: conn)

    Exporter()._log_export("harvest_event", "csv", None, 0, 0, "out.csv", None)

    output = capsys.readouterr().out
    assert "Failed to log export (ValueError)" in output
    assert "Failed to close export log cursor (RuntimeError)" in output
    assert "Failed to close export log connection (OSError)" in output
    assert SECRET not in output
