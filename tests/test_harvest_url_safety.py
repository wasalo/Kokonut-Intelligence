"""Regression tests for external harvest URL validation."""

import pytest

from services.ingestion.harvest_manager import _validate_external_url


def test_harvest_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        _validate_external_url("http://example.com/data.json")


def test_harvest_rejects_local_targets() -> None:
    with pytest.raises(ValueError):
        _validate_external_url("https://localhost/data.json")


def test_harvest_rejects_embedded_credentials() -> None:
    with pytest.raises(ValueError, match="credentials"):
        _validate_external_url("https://user:password@example.com/data.json")
