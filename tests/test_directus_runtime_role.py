"""Directus role bootstrap input and privilege-contract checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.migration.directus_role import provision_directus_role


class UnusedConnection:
    """Fail if invalid arguments reach database operations."""

    @property
    def autocommit(self):
        return False

    @autocommit.setter
    def autocommit(self, value):
        raise AssertionError("invalid configuration must fail before opening a transaction")


@pytest.mark.parametrize(
    ("directus_user", "password", "message"),
    [
        ("kokonut", "a-distinct-password-that-is-long-enough", "must be distinct"),
        ("BadRole", "a-distinct-password-that-is-long-enough", "lowercase PostgreSQL role"),
        ("kokonut_directus_runtime", "replace-with-a-long-placeholder-password", "non-placeholder"),
        ("kokonut_directus_runtime", "short", "at least 24 characters"),
    ],
)
def test_role_bootstrap_rejects_unsafe_configuration_before_database_access(
    directus_user: str, password: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        provision_directus_role(
            UnusedConnection(),
            database="kokonut_intelligence",
            admin_user="kokonut",
            directus_user=directus_user,
            directus_password=password,
        )


def test_compose_runtime_uses_non_owner_role_and_localhost_binding() -> None:
    source = (Path(__file__).resolve().parents[1] / "docker-compose.kernel-directus.yml").read_text()
    runtime = source.split("  directus:\n", 1)[1].split("\nvolumes:", 1)[0]

    assert 'command: ["cli.js", "start"]' in runtime
    assert "KOKONUT_DIRECTUS_RUNTIME_PASSWORD" in runtime
    assert "KOKONUT_KERNEL_DIRECTUS_BIND:-127.0.0.1" in runtime
    assert "KOKONUT_KERNEL_DIRECTUS_PORT:-18055" in runtime
    assert "ADMIN_PASSWORD" not in runtime
    assert "POSTGRES_PASSWORD" not in runtime
    assert "127.0.0.1" in runtime
    assert "POSTGRES_PASSWORD" not in runtime


def test_role_provisioner_restricts_database_connect_and_dml_scope() -> None:
    source = (Path(__file__).resolve().parents[1] / "services/migration/directus_role.py").read_text()

    assert "REVOKE CONNECT ON DATABASE {} FROM PUBLIC" in source
    assert "GRANT CONNECT ON DATABASE {} TO {}" in source
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}" in source
    assert "REVOKE CREATE ON SCHEMA {} FROM PUBLIC" in source
    assert "_verify_role_attributes(cur, directus_user)" in source
    assert 'connect_scope": [database]' in source
