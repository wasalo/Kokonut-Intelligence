"""Protect harvest logs and results from source URL credentials and errors."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.ingestion import harvest_manager


def test_remote_harvest_redacts_url_credentials_and_provider_error(monkeypatch):
    secret_url = "https://operator:password@farms.example.invalid/api/v1?token=private#fragment"
    provider_secret = "request failed for https://farms.example.invalid/api/v1?token=private"
    conn = MagicMock()
    insert_result = MagicMock()
    insert_result.mappings.return_value.first.return_value = {"id": "harvest-log-1"}
    conn.execute.side_effect = [insert_result, MagicMock()]
    conn.text.side_effect = lambda statement: statement
    request = MagicMock(side_effect=RuntimeError(provider_secret))
    from services.common.http import http

    monkeypatch.setattr(harvest_manager, "_validate_external_url", lambda _url: None)
    monkeypatch.setattr(http, "get", request)

    result = harvest_manager.harvest_from_url(conn, "location-1", secret_url)

    assert request.call_args.args[0] == secret_url
    stored_source_url = conn.execute.call_args_list[0].args[1]["url"]
    persisted_error = conn.execute.call_args_list[1].args[1]["msg"]
    assert stored_source_url == "https://farms.example.invalid/api/v1"
    assert result == {
        "status": "error",
        "message": "harvest failed (RuntimeError)",
        "log_id": "harvest-log-1",
    }
    assert provider_secret not in repr(result)
    assert "password" not in stored_source_url
    assert "private" not in stored_source_url
    assert provider_secret not in persisted_error


def test_url_validation_errors_keep_safe_guidance_without_network_access():
    with pytest.raises(ValueError, match="without embedded credentials") as error:
        harvest_manager._validate_external_url("https://operator:password@farms.example.invalid/data")

    assert harvest_manager._harvest_error_summary(error.value) == (
        "source_url must be an HTTPS URL without embedded credentials"
    )
