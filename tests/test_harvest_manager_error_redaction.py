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


def test_local_harvest_redacts_missing_path(monkeypatch):
    secret_path = "/private/farm/seed-data/participant-list.json"
    conn = MagicMock()
    monkeypatch.setattr(harvest_manager.os.path, "exists", lambda _path: False)

    result = harvest_manager.harvest_from_file(conn, "location-1", secret_path)

    assert result == {"status": "error", "message": "source file not found"}
    assert secret_path not in repr(result)
    conn.execute.assert_not_called()


def test_local_harvest_redacts_path_and_read_failure_from_log_and_result(monkeypatch):
    secret_path = "/private/farm/seed-data/participant-list.json"
    secret_error = f"permission denied for {secret_path}; credential=private-token"
    conn = MagicMock()
    insert_result = MagicMock()
    insert_result.mappings.return_value.first.return_value = {"id": "harvest-log-2"}
    conn.execute.side_effect = [insert_result, MagicMock()]
    conn.text.side_effect = lambda statement: statement
    monkeypatch.setattr(harvest_manager.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(
        "builtins.open",
        MagicMock(side_effect=OSError(secret_error)),
    )

    result = harvest_manager.harvest_from_file(conn, "location-1", secret_path)

    stored_source = conn.execute.call_args_list[0].args[1]["url"]
    persisted_error = conn.execute.call_args_list[1].args[1]["msg"]
    assert stored_source == "[local file]"
    assert result == {
        "status": "error",
        "message": "file harvest failed (OSError)",
        "log_id": "harvest-log-2",
    }
    assert secret_path not in repr(result)
    assert secret_error not in persisted_error
    assert secret_path not in stored_source
