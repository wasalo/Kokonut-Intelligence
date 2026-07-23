"""Tests for strategic control variance calculations."""

from services.analytics.strategy_execution import calculate_variance


def test_variance_status_bands():
    assert calculate_variance(100, 105)["status"] == "within_tolerance"
    assert calculate_variance(100, 120)["status"] == "warning"
    assert calculate_variance(100, 140)["status"] == "breach"
    assert calculate_variance(None, 10)["status"] == "not_measurable"


def test_variance_both_none():
    result = calculate_variance(None, None)
    assert result["status"] == "not_measurable"
    assert result["variance_value"] is None
    assert result["variance_pct"] is None


def test_variance_exact_zero_planned():
    result = calculate_variance(0, 10)
    assert result["status"] == "breach"
    assert result["variance_pct"] is None


def test_variance_negative_planned():
    result = calculate_variance(-100, -110)
    assert result["status"] == "within_tolerance"
    assert result["variance_value"] == -10.0
    assert result["variance_pct"] == -10.0


def test_variance_negative_planned_breach():
    result = calculate_variance(-100, -130)
    assert result["status"] == "breach"
    assert result["variance_pct"] == -30.0
