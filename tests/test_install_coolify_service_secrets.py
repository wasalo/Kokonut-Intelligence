"""Contracts for service-scoped Coolify secrets sourced from SOPS."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "install_coolify_service_secrets",
    ROOT / "scripts" / "install-coolify-service-secrets.py",
)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def test_legacy_copernicus_credentials_map_only_to_remote_sensing_worker_keys():
    values = {
        "COPERNICUS_EMAIL": "legacy@example.invalid",
        "COPERNICUS_PASSWORD": "synthetic-password",
        "COPERNICUS_CLIENT_ID": "synthetic-client-id",
        "COPERNICUS_CLIENT_SECRET": "synthetic-client-secret",
    }

    mappings = {
        "KOKONUT_REMOTE_SENSING_COPERNICUS_EMAIL": "COPERNICUS_EMAIL",
        "KOKONUT_REMOTE_SENSING_COPERNICUS_PASSWORD": "COPERNICUS_PASSWORD",
        "KOKONUT_REMOTE_SENSING_COPERNICUS_CLIENT_ID": "COPERNICUS_CLIENT_ID",
        "KOKONUT_REMOTE_SENSING_COPERNICUS_CLIENT_SECRET": "COPERNICUS_CLIENT_SECRET",
    }

    for target, source in mappings.items():
        assert installer._resolve_secret("worker", target, values) == values[source]


def test_copernicus_account_identifiers_are_private_service_env_keys():
    email_key = ("worker", "KOKONUT_REMOTE_SENSING_COPERNICUS_EMAIL")
    client_id_key = ("worker", "KOKONUT_REMOTE_SENSING_COPERNICUS_CLIENT_ID")

    assert installer.SERVICE_KEY_ALIASES[email_key] == "COPERNICUS_EMAIL"
    assert installer.SERVICE_KEY_ALIASES[client_id_key] == "COPERNICUS_CLIENT_ID"
