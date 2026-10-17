import sys
from unittest.mock import MagicMock

import pytest

from services.export import report_generator

SECRET = "database password=private-token and farm row"


def _connection():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn, cursor


def test_auto_report_persists_bounded_failure_and_continues(monkeypatch, capsys):
    conn, cursor = _connection()
    monkeypatch.setattr(report_generator, "get_pg", lambda: conn)
    monkeypatch.setattr(report_generator, "REPORT_GENERATORS", {"synthetic": object()})
    monkeypatch.setattr(
        report_generator,
        "generate_report_data_read_only",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(SECRET)),
    )
    monkeypatch.setattr(
        sys, "argv", ["report_generator", "--auto", "--location-id", "location-1"]
    )

    with pytest.raises(SystemExit) as error:
        report_generator.main()
    assert error.value.code == 1

    output = capsys.readouterr()
    failed_update = next(
        call
        for call in cursor.execute.call_args_list
        if "SET status = 'failed'" in call.args[0]
    )
    assert failed_update.args[1][0] == "report generation failed (RuntimeError)"
    assert SECRET not in repr(cursor.execute.call_args_list)
    assert SECRET not in output.out + output.err
    assert "1 failed" in output.out
    conn.rollback.assert_called_once_with()
    conn.close.assert_called_once_with()


def test_single_report_failure_does_not_print_or_raise_raw_exception(monkeypatch, capsys):
    conn, _cursor = _connection()
    monkeypatch.setattr(report_generator, "get_pg", lambda: conn)
    monkeypatch.setattr(
        report_generator,
        "generate_report_data_read_only",
        lambda *_args: (_ for _ in ()).throw(ValueError(SECRET)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["report_generator", "--type", "farm_summary", "--location-id", "location-1"],
    )

    with pytest.raises(RuntimeError, match=r"report generation failed \(ValueError\)") as error:
        report_generator.main()

    output = capsys.readouterr()
    assert SECRET not in str(error.value)
    assert SECRET not in output.out + output.err
    conn.close.assert_called_once_with()
