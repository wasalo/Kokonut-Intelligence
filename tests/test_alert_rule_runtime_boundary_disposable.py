from pathlib import Path


def test_alert_rule_disposable_checker_is_network_isolated_and_covers_seed_and_roles():
    root = Path(__file__).resolve().parents[1]
    checker = (
        root / "scripts/check-alert-rule-runtime-boundary-disposable.py"
    ).read_text(encoding="utf-8")

    assert '"--network", "none"' in checker
    assert '"--pull=never"' in checker
    assert "ASSERT_ROLE_ABSENT" in checker
    assert "PROVISIONER_REAPPLICATION" in checker
    assert "kokonut_anomaly_event_owner" in checker
    assert "kokonut_sensor_baseline_owner" in checker
    assert "pilot_alert_rule_insert" in checker
    assert "ensure_default_alert_rules" in checker
