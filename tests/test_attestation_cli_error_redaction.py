"""Attestation CLI errors should not echo provider or signer diagnostics."""

import sys
import types

import pytest

from services.attestation import cli

DIAGNOSTIC = "synthetic provider diagnostic marker"


def test_command_failure_reports_only_exception_class(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["attestation", "info", "--chain", "celo"])

    def fail(_args):
        raise RuntimeError(DIAGNOSTIC)

    monkeypatch.setattr(cli, "_handle_info", fail)

    with pytest.raises(SystemExit) as error:
        cli.main()

    output = capsys.readouterr()
    assert error.value.code == 1
    assert "Attestation command failed (RuntimeError)" in output.err
    assert DIAGNOSTIC not in output.out + output.err


def test_info_signer_failure_reports_only_exception_class(monkeypatch, capsys):
    config = types.ModuleType("services.attestation.config")
    config.ATTESTER_PRIVATE_KEY = "synthetic-key-marker"
    config.KOKONUT_MULTISIG = "0x0000000000000000000000000000000000000001"
    config.get_chain_config = lambda _chain: {
        "chain_id": 42220,
        "rpc_url": "https://public.example",
        "eas_address": "0x0000000000000000000000000000000000000002",
        "schema_registry_address": "0x0000000000000000000000000000000000000003",
        "explorer": "https://explorer.example",
    }
    signer = types.ModuleType("services.attestation.signer")

    class FailingSigner:
        def __init__(self, _chain):
            raise RuntimeError(DIAGNOSTIC)

    signer.EASSigner = FailingSigner
    monkeypatch.setitem(sys.modules, "services.attestation.config", config)
    monkeypatch.setitem(sys.modules, "services.attestation.signer", signer)

    cli._handle_info(types.SimpleNamespace(chain="celo"))

    output = capsys.readouterr().out
    assert "Attester: unavailable (RuntimeError)" in output
    assert DIAGNOSTIC not in output
    assert "synthetic-key-marker" not in output
