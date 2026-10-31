"""Directus role bootstrap input and privilege-contract checks."""

from __future__ import annotations

import re
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


def test_role_provisioner_reapplies_ordered_migration_relation_denials() -> None:
    source = (Path(__file__).resolve().parents[1] / "services/migration/directus_role.py").read_text()

    broad_grant = source.index("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA")
    policy_reapplication = source.index(
        "_apply_migration_declared_relation_policies(\n                cur, directus_ident"
    )
    role_validation = source.index("_verify_role_attributes(cur, directus_user)")
    assert broad_grant < policy_reapplication < role_validation
    assert "kokonut_security.directus_relation_privilege_policy" in source
    assert 'frozenset({"read_only", "no_access"})' in source
    assert "REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER" in source
    assert "has_any_column_privilege" in source
    assert "REVOKE ALL PRIVILEGES ON SEQUENCE {} FROM {}" in source
    provision_start = source.index("def provision_directus_role(")
    prerequisite = source.index(
        "ordered migrations must create the Directus relation privilege policy",
        provision_start,
    )
    role_creation = source.index("_ensure_login_role(", provision_start)
    assert prerequisite < role_creation < broad_grant


def test_directus_policy_migration_reconciles_prior_denials_and_preserves_catalog_exceptions() -> None:
    root = Path(__file__).resolve().parents[1]
    migration_path = root / "schemas/postgres/705_directus_relation_privilege_policy.sql"
    migration = migration_path.read_text()
    rows = re.findall(
        r"\('public', '([a-z_][a-z0-9_]*)', '(read_only|no_access)', '([0-9]{3}_[a-z0-9_]+\.sql)'\)",
        migration,
    )
    policies = {(relation, mode) for relation, mode, _source in rows}

    assert len(rows) >= 100
    assert len({relation for relation, _mode, _source in rows}) == len(rows)
    assert all((root / "schemas/postgres" / source).is_file() for _relation, _mode, source in rows)
    schema_sql = "\n".join(
        path.read_text(errors="replace")
        for path in sorted((root / "schemas/postgres").glob("*.sql"))
        if path != migration_path
    )
    for relation, _mode, _source in rows:
        assert re.search(
            rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|MATERIALIZED\s+VIEW|FOREIGN\s+TABLE)\s+"
            rf"(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?{re.escape(relation)}\b",
            schema_sql,
            re.IGNORECASE,
        ), f"Directus policy relation public.{relation} has no ordered schema definition"
    explicit_denials: set[str] = set()
    for path in sorted((root / "schemas/postgres").glob("*.sql")):
        if path == migration_path:
            continue
        for statement in re.findall(r"\bREVOKE\b[\s\S]*?;", path.read_text(), re.IGNORECASE):
            if "kokonut_directus_runtime" not in statement.lower():
                continue
            target_clause = re.search(
                r"\bON\s+TABLE\s+([\s\S]*?)\s+FROM\b",
                statement,
                re.IGNORECASE,
            )
            if target_clause:
                explicit_denials.update(
                    re.findall(
                        r"\bpublic\.([a-z_][a-z0-9_]*)\b",
                        target_clause.group(1),
                        re.IGNORECASE,
                    )
                )
    assert explicit_denials <= {relation for relation, _mode in policies}
    assert ("hive_record", "read_only") in policies
    assert ("pollinator_hive_inspection", "read_only") in policies
    assert ("pollinator_observation", "read_only") in policies
    assert ("pollinator_habitat", "read_only") in policies
    assert ("pesticide_impact_log", "read_only") in policies
    assert ("farm_activity_operator_event", "no_access") in policies
    assert ("governance_tactical_action_event", "no_access") in policies

    # Runtime-only reference migrations must not be widened into Directus ACL
    # denials; their deliberate compatibility behavior remains unchanged.
    for relation in (
        "capital_source",
        "consent_data_type",
        "process_benchmark",
        "living_wage_benchmark",
    ):
        assert not any(name == relation for name, _mode in policies)
    assert "695/696/697/704 intentionally do not" in migration
