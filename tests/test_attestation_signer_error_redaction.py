"""EAS signer failures must not persist or return raw provider details."""

from unittest.mock import MagicMock

from services.attestation import eas_client, signer_service

SECRET = "eas-rpc-provider-secret"
REQUEST_ID = "attestation-request-id"


def test_pending_request_failure_is_redacted_in_database_result_and_log(monkeypatch):
    connection = MagicMock()
    connection.text.side_effect = lambda sql: sql
    result = MagicMock()
    result.mappings.return_value.all.return_value = [{
        "id": REQUEST_ID,
        "subject_type": "data_stream_post",
        "subject_id": "post-id",
        "schema_name": "test-schema",
        "chain": "celo",
        "metadata": "{}",
    }]
    connection.execute.return_value = result
    client = MagicMock()
    client.is_connected.return_value = True
    monkeypatch.setattr(eas_client, "EASClient", lambda *_args: client)
    monkeypatch.setattr(signer_service, "_submit_attestation", lambda *_args: (_ for _ in ()).throw(RuntimeError(f"RPC URL contained {SECRET}")))
    logger = MagicMock()
    monkeypatch.setattr(signer_service, "logger", logger)

    summary = signer_service.process_pending_requests(connection)

    safe_error = "attestation submission failed (RuntimeError)"
    assert summary["failed"] == 1
    assert summary["results"][0]["error"] == safe_error
    assert SECRET not in str(summary)
    update_call = connection.execute.call_args_list[-1]
    assert "execution_status = 'failed'" in update_call.args[0]
    assert "signing_attempts = signing_attempts + 1" in update_call.args[0]
    assert update_call.args[1]["err"] == safe_error
    assert SECRET not in str(update_call)
    assert SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)
