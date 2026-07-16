"""Tests for strategic control variance calculations."""

from services.analytics.strategy_execution import calculate_variance


def test_variance_status_bands():
    assert calculate_variance(100, 105)["status"] == "within_tolerance"
    assert calculate_variance(100, 120)["status"] == "warning"
    assert calculate_variance(100, 140)["status"] == "breach"
    assert calculate_variance(None, 10)["status"] == "not_measurable"
