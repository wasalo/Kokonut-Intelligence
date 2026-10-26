"""Credential selection for the optional Python gRPC SDK helper."""

from __future__ import annotations

import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import grpc
import pytest

SDK_PATH = Path(__file__).resolve().parent.parent / "sdk" / "python"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

create_channel = import_module("kokonut.grpc").create_channel


def test_importing_optional_grpc_channel_helper_does_not_import_grpc():
    script = "\n".join(
        [
            "import builtins, sys",
            "real_import = builtins.__import__",
            "def guarded_import(name, *args, **kwargs):",
            "    if name == 'grpc' or name.startswith('grpc.'):",
            "        raise AssertionError('optional grpc runtime imported eagerly')",
            "    return real_import(name, *args, **kwargs)",
            "builtins.__import__ = guarded_import",
            "from kokonut.grpc import create_channel",
            "assert callable(create_channel)",
            "assert not any(name == 'grpc' or name.startswith('grpc.') for name in sys.modules)",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=SDK_PATH.parent.parent,
        env={**os.environ, "PYTHONPATH": str(SDK_PATH)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "target",
    [
        "localhost:50051",
        "dns:///localhost:50051",
        "127.0.0.1:50051",
        "ipv4:127.0.0.1:50051",
        "[::1]:50051",
        "ipv6:[::1]:50051",
    ],
)
def test_loopback_targets_use_insecure_channel_by_default(monkeypatch, target):
    channel = object()
    insecure_channel = Mock(return_value=channel)
    secure_channel = Mock()
    monkeypatch.setattr(grpc, "insecure_channel", insecure_channel)
    monkeypatch.setattr(grpc, "secure_channel", secure_channel)

    result = create_channel(target)

    assert result is channel
    insecure_channel.assert_called_once_with(target)
    secure_channel.assert_not_called()


@pytest.mark.parametrize("target", ["grpc.internal:50051", "hub.kokonut.network:443"])
def test_remote_targets_use_system_trusted_tls_by_default(monkeypatch, target):
    channel = object()
    credentials = object()
    tls_credentials = Mock(return_value=credentials)
    secure_channel = Mock(return_value=channel)
    insecure_channel = Mock()
    monkeypatch.setattr(grpc, "ssl_channel_credentials", tls_credentials)
    monkeypatch.setattr(grpc, "secure_channel", secure_channel)
    monkeypatch.setattr(grpc, "insecure_channel", insecure_channel)

    result = create_channel(target)

    assert result is channel
    tls_credentials.assert_called_once_with(root_certificates=None)
    secure_channel.assert_called_once_with(target, credentials)
    insecure_channel.assert_not_called()


def test_private_ca_uses_secure_channel_even_for_loopback(monkeypatch):
    credentials = object()
    channel = object()
    tls_credentials = Mock(return_value=credentials)
    secure_channel = Mock(return_value=channel)
    monkeypatch.setattr(grpc, "ssl_channel_credentials", tls_credentials)
    monkeypatch.setattr(grpc, "secure_channel", secure_channel)

    result = create_channel("localhost:50051", root_certificates=b"test CA")

    assert result is channel
    tls_credentials.assert_called_once_with(root_certificates=b"test CA")
    secure_channel.assert_called_once_with("localhost:50051", credentials)


def test_remote_plaintext_requires_explicit_opt_in(monkeypatch):
    channel = object()
    insecure_channel = Mock(return_value=channel)
    secure_channel = Mock()
    monkeypatch.setattr(grpc, "insecure_channel", insecure_channel)
    monkeypatch.setattr(grpc, "secure_channel", secure_channel)

    assert create_channel("grpc.internal:50051", allow_insecure=True) is channel
    insecure_channel.assert_called_once_with("grpc.internal:50051")
    secure_channel.assert_not_called()


@pytest.mark.parametrize(
    ("target", "kwargs", "message"),
    [
        (" ", {}, "non-empty string"),
        ("localhost:50051", {"allow_insecure": 1}, "allow_insecure must be a boolean"),
        ("localhost:50051", {"root_certificates": "pem"}, "root_certificates must be bytes"),
        ("localhost:50051", {"root_certificates": b""}, "root_certificates must not be empty"),
        (
            "localhost:50051",
            {"root_certificates": b"ca", "allow_insecure": True},
            "cannot be combined",
        ),
    ],
)
def test_invalid_configuration_fails_before_channel_creation(
    monkeypatch, target, kwargs, message
):
    channel = Mock()
    monkeypatch.setattr(grpc, "insecure_channel", channel)
    monkeypatch.setattr(grpc, "secure_channel", channel)

    with pytest.raises(ValueError, match=message):
        create_channel(target, **kwargs)

    channel.assert_not_called()
