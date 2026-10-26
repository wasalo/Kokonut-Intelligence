"""Provider errors in reconciliation results must not expose diagnostics."""

import sys
import types

import pytest

from services.attestation.reconciliation import _verify_onchain

DIAGNOSTIC = "synthetic provider diagnostic marker"


class _Result:
    def mappings(self):
        return self

    def all(self):
        return [
            {
                "request_id": "request-1",
                "attestation_uid": "uid-1",
                "tx_hash": "tx-1",
                "subject_id": "post-1",
                "title": "Synthetic post",
            }
        ]


class _Connection:
    def text(self, statement):
        return statement

    def execute(self, _statement, _params):
        return _Result()


@pytest.mark.parametrize("failing_method", ["get_attestation", "is_valid_attestation"])
def test_onchain_reconciliation_redacts_provider_exception(monkeypatch, failing_method):
    config = types.ModuleType("services.attestation.config")
    config.get_chain_config = lambda _chain: {"chain_id": 42220}
    eas_client = types.ModuleType("services.attestation.eas_client")

    class FailingEASClient:
        def __init__(self, _chain):
            pass

        def is_connected(self):
            return True

        def get_attestation(self, _uid):
            if failing_method == "get_attestation":
                raise RuntimeError(DIAGNOSTIC)
            return object()

        def is_valid_attestation(self, _uid):
            if failing_method == "is_valid_attestation":
                raise RuntimeError(DIAGNOSTIC)
            return True

    eas_client.EASClient = FailingEASClient
    monkeypatch.setitem(sys.modules, "services.attestation.config", config)
    monkeypatch.setitem(sys.modules, "services.attestation.eas_client", eas_client)

    verified, discrepancies = _verify_onchain(_Connection(), "celo")

    assert verified == 0
    assert discrepancies == [
        {
            "request_id": "request-1",
            "attestation_uid": "uid-1",
            "title": "Synthetic post",
            "issue": "attestation_not_found",
            "detail": "Attestation verification failed (RuntimeError)",
        }
    ]
    assert DIAGNOSTIC not in repr(discrepancies)
