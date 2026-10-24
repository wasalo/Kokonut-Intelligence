"""Sandbox module input failures stay bounded and fail closed."""

import logging

import pytest

from services.sandbox.environment import AnalysisEnvironment


@pytest.mark.parametrize(
    ("module_path", "expected_error"),
    [
        ("/private/var/folders/secret_module.py", "Invalid module path format"),
        (None, "Invalid module path format"),
        (42, "Invalid module path format"),
        ("services.private.synthetic_module", "Module not allowed"),
    ],
)
def test_rejected_module_input_is_not_echoed_or_executed(module_path, expected_error, caplog):
    environment = AnalysisEnvironment()

    with caplog.at_level(logging.WARNING):
        result = environment.run("environment-1", module_path)

    assert result == {"error": expected_error}
    assert str(module_path) not in caplog.text
    assert "Traceback" not in caplog.text


def test_registered_module_still_fails_closed_without_restricted_worker(caplog):
    environment = AnalysisEnvironment()

    with caplog.at_level(logging.ERROR):
        result = environment.run("environment-1", "services.analytics.yield_monitoring")

    assert result["error"] == (
        "Sandbox executor is not configured. Configure a restricted "
        "worker; direct process execution is disabled."
    )
    assert "services.analytics.yield_monitoring" not in caplog.text
