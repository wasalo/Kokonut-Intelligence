"""Regression checks for the offline SDK/PostgreSQL schema guard."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_sdk_schema_parity", ROOT / "scripts" / "check-sdk-schema-parity.py"
)
assert SPEC is not None and SPEC.loader is not None
SCHEMA_GUARD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SCHEMA_GUARD
SPEC.loader.exec_module(SCHEMA_GUARD)


def test_column_type_inventory_reads_base_sql_declarations(tmp_path):
    schema = tmp_path / "fixture.sql"
    schema.write_text(
        """CREATE TABLE IF NOT EXISTS sdk_guard_fixture (
    id UUID PRIMARY KEY,
    count INTEGER NOT NULL,
    ratio NUMERIC(12, 4),
    tags TEXT[],
    location GEOMETRY(Point, 4326)
);
""",
        encoding="utf-8",
    )

    assert SCHEMA_GUARD.table_column_types(schema, "sdk_guard_fixture") == {
        "id": "UUID",
        "count": "INTEGER",
        "ratio": "NUMERIC(12, 4)",
        "tags": "TEXT[]",
        "location": "GEOMETRY(POINT, 4326)",
    }


def test_column_type_inventory_applies_additions_and_type_migrations(tmp_path, monkeypatch):
    schema = tmp_path / "base.sql"
    schema.write_text(
        """CREATE TABLE IF NOT EXISTS sdk_guard_fixture (
    id UUID PRIMARY KEY,
    label TEXT
);
""",
        encoding="utf-8",
    )
    migrations = tmp_path / "schemas" / "postgres"
    migrations.mkdir(parents=True)
    (migrations / "001_fixture.sql").write_text(
        """ALTER TABLE sdk_guard_fixture ADD COLUMN score NUMERIC(12, 4);
ALTER TABLE sdk_guard_fixture ALTER COLUMN score TYPE NUMERIC(14, 4);
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(SCHEMA_GUARD, "ROOT", tmp_path)

    assert SCHEMA_GUARD.table_column_types(schema, "sdk_guard_fixture") == {
        "id": "UUID",
        "label": "TEXT",
        "score": "NUMERIC(14, 4)",
    }


def test_sql_type_families_cover_scalar_and_leave_domain_types_explicit():
    assert SCHEMA_GUARD.sql_type_family("UUID") == "string"
    assert SCHEMA_GUARD.sql_type_family("NUMERIC(12, 4)") == "number"
    assert SCHEMA_GUARD.sql_type_family("INTEGER") == "integer"
    assert SCHEMA_GUARD.sql_type_family("TEXT[]") == "string_array"
    assert SCHEMA_GUARD.sql_type_family("JSONB") is None
    assert SCHEMA_GUARD.sql_type_family("GEOMETRY(POINT, 4326)") is None


def test_sdk_scalar_types_match_sql_families_and_nullable_unions():
    assert SCHEMA_GUARD.python_type_matches_family("Optional[float]", "number")
    assert SCHEMA_GUARD.python_type_matches_family("Optional[List[str]]", "string_array")
    assert not SCHEMA_GUARD.python_type_matches_family("Optional[str]", "number")

    assert SCHEMA_GUARD.typescript_type_matches_family("number | null", "integer")
    assert SCHEMA_GUARD.typescript_type_matches_family("'draft' | 'published' | null", "string")
    assert SCHEMA_GUARD.typescript_type_matches_family("string[]", "string_array")
    assert not SCHEMA_GUARD.typescript_type_matches_family("string", "number")
