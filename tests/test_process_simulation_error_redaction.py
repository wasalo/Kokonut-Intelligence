from unittest.mock import MagicMock

from services.analytics import process_simulation


def test_run_simulation_redacts_calculation_exception_and_cancels_record(monkeypatch):
    secret = "database password and private row value"
    simulation_id = "00000000-0000-0000-0000-000000000001"
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": simulation_id,
        "scenario_params": {},
        "process_key": "farm_operations",
    }
    conn = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(
        process_simulation,
        "_compute_actual",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(secret)),
    )

    result = process_simulation.run_simulation(conn, simulation_id)

    assert result == {
        "simulation_id": simulation_id,
        "status": "failed",
        "error": "simulation failed (RuntimeError)",
    }
    assert secret not in str(result)
    conn.rollback.assert_called_once_with()
    assert conn.commit.call_count == 2
    assert any(
        "status = 'cancelled'" in call.args[0]
        for call in cursor.execute.call_args_list
    )
