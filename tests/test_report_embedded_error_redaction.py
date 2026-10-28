"""Nested report failures omit raw exception details from returned payloads."""

from unittest.mock import MagicMock

from services.export import business_plan
from services.export.reports import operations, strategy

SECRET = "database password=private-token and confidential farm row"


def test_business_plan_section_error_is_class_only():
    conn = MagicMock()

    def fail():
        raise RuntimeError(SECRET)

    result = business_plan._section(conn, fail)

    assert result["available"] is False
    assert result["error"] == "business-plan section failed (RuntimeError)"
    assert SECRET not in repr(result)
    conn.rollback.assert_called_once_with()


def test_business_plan_reference_class_error_is_class_only(monkeypatch):
    from services.forecast import reference_class

    def fail(*_args):
        raise ValueError(SECRET)

    monkeypatch.setattr(reference_class, "apply_reference_class", fail)
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = None

    result = business_plan._financial(conn, None, "location-1")

    assert result["reference_class"] == {
        "available": False,
        "error": "reference-class analysis failed (ValueError)",
    }
    assert SECRET not in repr(result)


def test_reward_calibration_advisory_error_is_class_only(monkeypatch):
    from services.analytics import reward_calibration

    def fail(*_args):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(reward_calibration, "detect_overjustification_risk", fail)
    conn = MagicMock()
    cur = conn.cursor.return_value
    cur.fetchone.return_value = {"name": "Synthetic location"}
    cur.fetchall.return_value = []

    result = operations.generate_reward_calibration(conn, "location-1")

    assert result["overjustification_risk"] == {
        "error": "overjustification analysis failed (RuntimeError)"
    }
    assert SECRET not in repr(result)


def test_simulation_reserve_clash_error_is_class_only(monkeypatch):
    from services.analytics import digital_twin
    from services.simulation import clash_examples

    monkeypatch.setattr(digital_twin, "list_twins", lambda *_args: [])

    def fail(*_args):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(clash_examples, "stress_reserve", fail)

    result = strategy.generate_simulation_wargame(
        object(), "a0000000-0000-0000-0000-000000000001"
    )

    assert result["reserve_clash"] == {"error": "reserve clash failed (RuntimeError)"}
    assert SECRET not in repr(result)
