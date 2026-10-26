"""The isolated restore bootstrap must cover every migration-owned role."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREQUISITES = ROOT / "scripts" / "kernel-restore-role-prerequisites.sql"
MIGRATION_ROLE = re.compile(r"\b(?:TO|OWNER\s+TO)\s+(kokonut_[a-z0-9_]+)\b", re.IGNORECASE)
PREREQUISITE_ROLE = re.compile(r"'((?:kokonut_[a-z0-9_]+))'", re.IGNORECASE)


def test_restore_bootstrap_covers_all_roles_in_migration_policies_and_owners():
    source_roles = set()
    for migration in (ROOT / "schemas" / "postgres").glob("*.sql"):
        source_roles.update(MIGRATION_ROLE.findall(migration.read_text(encoding="utf-8")))

    configured_roles = set(PREREQUISITE_ROLE.findall(PREREQUISITES.read_text(encoding="utf-8")))

    assert source_roles <= configured_roles


def test_restore_bootstrap_only_creates_disabled_roles_and_rejects_unsafe_existing_roles():
    source = " ".join(PREREQUISITES.read_text(encoding="utf-8").split())

    assert "CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB" in source
    assert "NOCREATEROLE NOREPLICATION NOBYPASSRLS" in source
    assert "AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole" in source
    assert "OR rolreplication OR rolbypassrls OR rolinherit" in source
