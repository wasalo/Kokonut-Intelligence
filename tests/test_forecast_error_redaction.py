from unittest.mock import MagicMock

from services.forecast import engine

SECRET = "private crop data and database-password=synthetic"


def test_run_all_scenarios_redacts_failure_from_result_and_logs(monkeypatch, capsys):
    scenario_id = "scenario-1"
    db = MagicMock()
    db.cursor.return_value.__enter__.return_value.fetchall.return_value = [
        {"id": scenario_id, "name": "Confidential farm scenario"}
    ]
    monkeypatch.setattr(engine, "get_db", lambda: db)
    monkeypatch.setattr(
        engine,
        "run_forecast",
        lambda _scenario_id: (_ for _ in ()).throw(RuntimeError(SECRET)),
    )
    logger = MagicMock()
    monkeypatch.setattr(engine, "logger", logger)

    results = engine.run_all_scenarios()
    output = capsys.readouterr()

    assert results == [{
        "scenario_id": scenario_id,
        "error": "forecast scenario failed (RuntimeError)",
    }]
    assert SECRET not in repr(results)
    assert SECRET not in output.out + output.err
    assert SECRET not in repr(logger.warning.call_args)
    db.close.assert_called_once_with()


def test_dashboard_dataset_failure_is_redacted_and_connection_closes(monkeypatch, capsys):
    db = MagicMock()
    db.cursor.return_value.__enter__.return_value.execute.side_effect = RuntimeError(SECRET)
    monkeypatch.setattr(engine, "get_db", lambda: db)
    logger = MagicMock()
    monkeypatch.setattr(engine, "logger", logger)

    engine._write_dashboard_dataset(
        "scenario-1",
        "location-1",
        [{
            "metric_name": "net_operating_income",
            "value": 100,
            "unit": "USD",
            "confidence_low": 80,
            "confidence_high": 120,
        }],
        "synthetic",
    )
    output = capsys.readouterr()

    assert SECRET not in output.out + output.err
    assert SECRET not in repr(logger.warning.call_args)
    assert "RuntimeError" in repr(logger.warning.call_args)
    db.close.assert_called_once_with()
