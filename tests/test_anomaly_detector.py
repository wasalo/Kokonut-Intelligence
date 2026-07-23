"""Tests for services.ingestion.anomaly_detector — sensor alert engine."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_anomaly_detector_evaluate_rule_gt():
    from services.ingestion.anomaly_detector import evaluate_rule

    assert evaluate_rule(50.0, "gt", 40.0) is True
    assert evaluate_rule(30.0, "gt", 40.0) is False


def test_anomaly_detector_evaluate_rule_lt():
    from services.ingestion.anomaly_detector import evaluate_rule

    assert evaluate_rule(5.0, "lt", 15.0) is True
    assert evaluate_rule(20.0, "lt", 15.0) is False


def test_anomaly_detector_evaluate_rule_eq():
    from services.ingestion.anomaly_detector import evaluate_rule

    assert evaluate_rule(10.0, "eq", 10.0) is True
    assert evaluate_rule(10.1, "eq", 10.0) is False


def test_anomaly_detector_evaluate_rule_outside_range():
    from services.ingestion.anomaly_detector import evaluate_rule

    assert evaluate_rule(3.0, "outside_range", 5.0, threshold_max=95.0) is True
    assert evaluate_rule(50.0, "outside_range", 5.0, threshold_max=95.0) is False
    assert evaluate_rule(96.0, "outside_range", 5.0, threshold_max=95.0) is True


def test_anomaly_detector_evaluate_rule_unknown_operator():
    from services.ingestion.anomaly_detector import evaluate_rule

    assert evaluate_rule(10.0, "bogus_op", 5.0) is False


def test_anomaly_detector_default_rules_have_required_keys():
    from services.ingestion.anomaly_detector import DEFAULT_ALERT_RULES

    for rule in DEFAULT_ALERT_RULES:
        assert "name" in rule
        assert "sensor_type_name" in rule
        assert "metric" in rule
        assert "operator" in rule
        assert "threshold_value" in rule
        assert "severity" in rule


def test_anomaly_detector_evaluate_metric_value_type():
    from services.ingestion.anomaly_detector import evaluate_metric

    db = MagicMock()
    rule = {"operator": "gt", "threshold_value": 40.0}
    result = evaluate_metric("value", 50.0, rule, db, "sensor-1", "air_temperature")
    assert result is True


def test_anomaly_detector_evaluate_metric_rate_returns_false_on_no_history():
    from services.ingestion.anomaly_detector import evaluate_metric

    db = MagicMock()
    rule = {"operator": "lt", "threshold_value": -5.0}

    with patch("services.ingestion.anomaly_detector.compute_rate_of_change", return_value=None):
        result = evaluate_metric("rate_of_change", 25.0, rule, db, "sensor-1", "soil_moisture")
    assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
