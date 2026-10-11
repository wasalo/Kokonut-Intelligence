"""Read-only startup gate for explicitly selected Kernel deployments."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from services.common.database import get_db

# Application read contracts, deliberately limited to the migrated public slice.
PUBLIC_READ_RELATIONS = {
    "v_public_farm_summary": (frozenset({"v"}), frozenset({
        "location_id", "location_name", "country", "region", "status",
    })),
    "v_public_metric_summary": (frozenset({"v"}), frozenset({
        "location_id", "metric_key", "display_name", "unit", "latest_value", "computed_at",
    })),
    "v_public_attestation_summary": (frozenset({"v"}), frozenset({
        "location_id", "total_attestations", "published_count", "latest_attestation",
    })),
    "crisp_risk_assessment": (frozenset({"r", "p"}), frozenset({
        "id", "location_id", "period_start", "period_end", "methodology_version",
        "composite_score", "rating", "confidence_level", "evidence_maturity_level",
        "score_computed_at", "status",
    })),
}


class SchemaReadinessError(RuntimeError):
    """Safe operator diagnostic containing only local categories and counts."""

    def __init__(self, code: str, *, expected: int = 0, missing: int = 0,
                 not_applied: int = 0, checksum_drift: int = 0,
                 unknown_applied: int = 0, extensions_expected: int = 0,
                 extensions_missing: int = 0, relations_expected: int = 0,
                 relations_invalid: int = 0, columns_missing: int = 0):
        self.code = code
        self.counts = {
            "expected": expected, "missing": missing, "not_applied": not_applied,
            "checksum_drift": checksum_drift, "unknown_applied": unknown_applied,
            "extensions_expected": extensions_expected, "extensions_missing": extensions_missing,
            "relations_expected": relations_expected, "relations_invalid": relations_invalid,
            "columns_missing": columns_missing,
        }
        super().__init__(
            f"{code}: expected={expected}, missing={missing}, not_applied={not_applied}, "
            f"checksum_drift={checksum_drift}, unknown_applied={unknown_applied}, "
            f"extensions_expected={extensions_expected}, extensions_missing={extensions_missing}, "
            f"relations_expected={relations_expected}, relations_invalid={relations_invalid}, "
            f"columns_missing={columns_missing}"
        )


def required_extensions(directory: Path) -> frozenset[str]:
    """Read the canonical extension list, rejecting unsupported SQL forms."""
    path = directory / "000_extensions.sql"
    if not path.is_file():
        raise SchemaReadinessError("extension_inventory_unavailable")
    sql = "\n".join(line for line in path.read_text().splitlines()
                    if not line.lstrip().startswith("--"))
    pattern = re.compile(
        r'CREATE\s+EXTENSION\s+IF\s+NOT\s+EXISTS\s+(?:"([a-z0-9_-]+)"|([a-z0-9_]+))\s*;',
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(sql))
    if not matches or pattern.sub("", sql).strip():
        raise SchemaReadinessError("extension_inventory_unsupported")
    return frozenset(match.group(1) or match.group(2).lower() for match in matches)


def require_schema_ready() -> dict[str, int]:
    """Require the bundled schemas' applied checksums without running migrations."""
    directory = Path(__file__).resolve().parents[2] / "schemas" / "postgres"
    files = sorted(directory.glob("[0-9]*.sql"))
    if not files:
        raise SchemaReadinessError("inventory_unavailable")
    expected = {
        f"schema:{path.name}": hashlib.sha256(path.read_bytes()).hexdigest()
        for path in files
    }
    extensions = required_extensions(directory)
    connection = get_db(connect_timeout=3)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            cursor.execute("SELECT to_regclass('public.schema_migration')")
            if cursor.fetchone()[0] is None:
                raise SchemaReadinessError("tracking_unavailable", expected=len(expected),
                                           missing=len(expected), extensions_expected=len(extensions))
            cursor.execute(
                "SELECT migration_id, checksum, status FROM public.schema_migration "
                "WHERE migration_id LIKE 'schema:%'"
            )
            rows = cursor.fetchall()
            cursor.execute("SELECT extname FROM pg_catalog.pg_extension")
            installed_extensions = {row[0] for row in cursor.fetchall()}
            cursor.execute(
                """SELECT relation.relname, relation.relkind, attribute.attname
                   FROM pg_catalog.pg_class relation
                   JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
                   LEFT JOIN pg_catalog.pg_attribute attribute
                     ON attribute.attrelid = relation.oid
                    AND attribute.attnum > 0 AND NOT attribute.attisdropped
                   WHERE namespace.nspname = 'public' AND relation.relname = ANY(%s)""",
                (list(PUBLIC_READ_RELATIONS),),
            )
            relation_rows = cursor.fetchall()
        applied = {identifier: (checksum, status) for identifier, checksum, status in rows}
        missing = sum(identifier not in applied for identifier in expected)
        not_applied = sum(
            identifier in applied and applied[identifier][1] != "applied"
            for identifier in expected
        )
        checksum_drift = sum(
            identifier in applied and applied[identifier][0] != checksum
            for identifier, checksum in expected.items()
        )
        newer = sum(identifier not in expected and status == "applied"
                    for identifier, (_, status) in applied.items())
        extensions_missing = len(extensions - installed_extensions)
        if missing or not_applied or checksum_drift or newer:
            raise SchemaReadinessError(
                "schema_mismatch", expected=len(expected), missing=missing,
                not_applied=not_applied, checksum_drift=checksum_drift,
                unknown_applied=newer,
                extensions_expected=len(extensions), extensions_missing=extensions_missing,
            )
        if extensions_missing:
            raise SchemaReadinessError("extensions_missing", expected=len(expected),
                                       extensions_expected=len(extensions),
                                       extensions_missing=extensions_missing)
        observed = {}
        for name, kind, column in relation_rows:
            entry = observed.setdefault(name, {"kind": kind, "columns": set()})
            if column is not None:
                entry["columns"].add(column)
        relations_invalid = 0
        columns_missing = 0
        for name, (kinds, columns) in PUBLIC_READ_RELATIONS.items():
            entry = observed.get(name)
            relations_invalid += entry is None or entry["kind"] not in kinds
            columns_missing += len(columns - (entry["columns"] if entry else set()))
        if relations_invalid or columns_missing:
            raise SchemaReadinessError(
                "public_relations_mismatch", expected=len(expected),
                extensions_expected=len(extensions), relations_expected=len(PUBLIC_READ_RELATIONS),
                relations_invalid=relations_invalid, columns_missing=columns_missing,
            )
        return {
            "expected": len(expected), "missing": 0, "not_applied": 0,
            "checksum_drift": 0, "unknown_applied": 0,
            "extensions_expected": len(extensions), "extensions_missing": 0,
            "relations_expected": len(PUBLIC_READ_RELATIONS), "relations_invalid": 0,
            "columns_missing": 0,
        }
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
