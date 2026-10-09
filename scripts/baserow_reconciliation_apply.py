"""Fail-closed validation for Baserow insert-only apply plans."""

from __future__ import annotations

from typing import Any

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from scripts.baserow_reconciliation_projection import (
    JSONB_VALUE_TYPES,
    REQUIRED_TARGET_COLUMNS,
    TARGET_COLUMNS,
)


_EDGE_SOURCE_IDENTITY = (
    "source_system", "source_database_id", "source_table_id", "source_field_id",
    "source_row_id", "source_related_table_id", "source_related_row_id",
)
_ROW_SOURCE_IDENTITY = ("source_system", "source_database_id", "source_table_id", "source_row_id")

IDENTITY_KEYS: dict[str, tuple[tuple[str, ...], ...]] = {
    "location": (("id",), ("slug",), ("name", "region")),
    "farm": (("id",), ("slug",), ("name", "location_id")),
    "plot": (("id",), ("name", "farm_id")),
    "crop": (("id",), ("name",)),
    "farm_task": (("id",), ("source_system", "source_id")),
    "expense_event": (("id",), ("source_system", "source_id")),
    "farm_activity": (("id",), ("source_system", "source_id")),
    "farm_activity_output": (("id",), _ROW_SOURCE_IDENTITY),
    "farm_activity_reported_metric": (("id",), _ROW_SOURCE_IDENTITY),
    "farm_activity_plot": (("activity_id", "plot_id"), _EDGE_SOURCE_IDENTITY),
    "farm_activity_output_activity": (("output_id", "activity_id"), _EDGE_SOURCE_IDENTITY),
    "farm_activity_reported_metric_output": (("reported_metric_id", "output_id"), _EDGE_SOURCE_IDENTITY),
}

REQUIRED_IDENTITY_COLUMNS: dict[str, tuple[str, ...]] = {
    "location": ("id", "name", "slug"),
    "farm": ("id", "location_id", "name", "slug"),
    "plot": ("id", "farm_id", "name", "slug"),
    "crop": ("id", "name"),
    "farm_task": ("id", "source_system", "source_id"),
    "expense_event": ("id", "source_system", "source_id"),
    "farm_activity": ("id", "source_system", "source_id"),
    "farm_activity_output": ("id", *_ROW_SOURCE_IDENTITY),
    "farm_activity_reported_metric": ("id", *_ROW_SOURCE_IDENTITY),
    "farm_activity_plot": ("activity_id", "plot_id", *_EDGE_SOURCE_IDENTITY),
    "farm_activity_output_activity": ("output_id", "activity_id", *_EDGE_SOURCE_IDENTITY),
    "farm_activity_reported_metric_output": (
        "reported_metric_id", "output_id", *_EDGE_SOURCE_IDENTITY,
    ),
}

TARGET_DATABASE_NAME = "kokonut_intelligence"


class ApplyError(RuntimeError):
    """Raised when an apply plan is outside its approved scope."""


def validate_apply_target_config(
    *,
    target: str,
    commit: bool,
    confirm_target: str | None,
    runtime_environment: str,
    configured_host: str,
    expected_target_host: str | None,
    database_name: str,
) -> None:
    """Fail closed unless local settings explicitly identify Staging or scratch."""
    if (
        target not in {"staging", "scratch"}
        or commit is not True
        or confirm_target != target
        or str(runtime_environment).lower() != target
        or database_name != TARGET_DATABASE_NAME
        or not configured_host
        or not expected_target_host
        or configured_host != expected_target_host
    ):
        raise ApplyError("persistent apply target checks failed; no connection was opened")


def validate_staging_target_config(**kwargs: Any) -> None:
    """Backward-compatible Staging-only target check."""
    validate_apply_target_config(target="staging", **kwargs)


def validate_preflight_blockers(preflight: dict[str, Any], allowlist: dict[str, Any]) -> None:
    """Permit only the explicit exact-labor partial-category blocker during plan preparation."""
    summary = preflight.get("summary") if isinstance(preflight, dict) else None
    blockers = preflight.get("blocking_fields") if isinstance(preflight, dict) else None
    if not isinstance(summary, dict) or not isinstance(blockers, list):
        raise ApplyError("source preflight blocker report is invalid")
    structural_count = summary.get("structural_issue_count")
    blocker_count = summary.get("blocking_fields_with_data")
    if isinstance(structural_count, bool) or structural_count != 0:
        raise ApplyError("source preflight still has structural issues")
    if isinstance(blocker_count, bool) or not isinstance(blocker_count, int) or blocker_count != len(blockers):
        raise ApplyError("source preflight blocker count does not match its field details")

    target_specs = allowlist.get("target_tables") if isinstance(allowlist, dict) else None
    if not isinstance(target_specs, list):
        raise ApplyError("projection allow-list target section is invalid")
    approved_rule = None
    for spec in target_specs:
        if not isinstance(spec, dict):
            raise ApplyError("projection allow-list target entry is invalid")
        if str(spec.get("source_table_id")) == "317575" and spec.get("target_table") == "expense_event":
            approved_rule = spec.get("fields", {}).get("2330114")
            break
    category_option_map = approved_rule.get("option_map") if isinstance(approved_rule, dict) else None
    if not isinstance(approved_rule, dict) or (
        approved_rule.get("source_disposition") != "CONDITIONAL"
        or approved_rule.get("transform") != "single_select_partial_option_map"
        or not isinstance(category_option_map, dict)
        or not category_option_map
        or any(
            not isinstance(option_id, str)
            or not option_id.isdigit()
            or int(option_id) <= 0
            or target_value != "labor"
            for option_id, target_value in category_option_map.items()
        )
        or approved_rule.get("source_label") != "Labor"
        or approved_rule.get("owner_decision_ref") != "exact-Labor-to-labor-2026-10-08"
    ):
        if blockers:
            raise ApplyError("source preflight has unapproved populated-field blockers")
        return

    seen: set[tuple[str, str]] = set()
    for blocker in blockers:
        if not isinstance(blocker, dict):
            raise ApplyError("source preflight has unapproved populated-field blockers")
        key = (str(blocker.get("table_id")), str(blocker.get("field_id")))
        populated = blocker.get("populated_cells")
        if (
            key != ("317575", "2330114")
            or blocker.get("disposition") != "CONDITIONAL"
            or isinstance(populated, bool)
            or not isinstance(populated, int)
            or populated <= 0
            or key in seen
        ):
            raise ApplyError("source preflight has unapproved populated-field blockers")
        seen.add(key)


def validate_apply_plan(
    rows_by_target: dict[str, list[dict[str, Any]]], allowlist: dict[str, Any]
) -> tuple[str, ...]:
    """Require projection targets to match the explicit target allow-list."""
    if not isinstance(rows_by_target, dict) or not isinstance(allowlist, dict):
        raise ApplyError("apply plan or allow-list is invalid")
    if allowlist.get("schema_version") != 1:
        raise ApplyError("unsupported apply allow-list version")

    direct = allowlist.get("target_tables")
    relationships = allowlist.get("relationship_tables", [])
    if not isinstance(direct, list) or not isinstance(relationships, list):
        raise ApplyError("apply allow-list target sections are invalid")

    targets: list[str] = []
    for entry in [*direct, *relationships]:
        if not isinstance(entry, dict):
            raise ApplyError("apply allow-list target entry is invalid")
        target = entry.get("target_table")
        if not isinstance(target, str) or target not in TARGET_COLUMNS:
            raise ApplyError("apply allow-list contains an unapproved target")
        targets.append(target)
    if not targets or len(targets) != len(set(targets)):
        raise ApplyError("apply allow-list targets are empty or duplicated")
    if set(rows_by_target) != set(targets):
        raise ApplyError("projection target set does not exactly match the allow-list")

    for target in targets:
        records = rows_by_target[target]
        if not isinstance(records, list):
            raise ApplyError("projection rows must be lists")
        expected_columns = set(TARGET_COLUMNS[target])
        required_columns = set(REQUIRED_TARGET_COLUMNS.get(target, set())) | set(REQUIRED_IDENTITY_COLUMNS[target])
        seen_identities: set[tuple[tuple[str, ...], tuple[Any, ...]]] = set()
        for record in records:
            if not isinstance(record, dict) or set(record) != expected_columns:
                raise ApplyError("projection columns do not exactly match the approved target schema")
            if any(record.get(column) is None or record.get(column) == "" for column in required_columns):
                raise ApplyError("projection lacks required target or source identity data")
            for identity_key in IDENTITY_KEYS[target]:
                identity = (identity_key, tuple(record.get(column) for column in identity_key))
                if identity in seen_identities:
                    raise ApplyError("projection contains duplicate source identities")
                seen_identities.add(identity)

    return tuple(target for target in TARGET_COLUMNS if target in set(targets))


def _projection_digest(rows_by_target: dict[str, list[dict[str, Any]]]) -> str:
    canonical_rows = {
        target: [
            {
                column: (str(value) if isinstance(value, Decimal) else value)
                for column, value in row.items()
            }
            for row in rows
        ]
        for target, rows in sorted(rows_by_target.items())
    }
    try:
        serialized = json.dumps(
            canonical_rows,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ApplyError("projection could not be canonically verified") from None
    return hashlib.sha256(serialized).hexdigest()


def _canonical_allowlist_digest(allowlist: dict[str, Any]) -> str:
    try:
        serialized = json.dumps(
            allowlist,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ApplyError("apply allow-list could not be canonically verified") from None
    return hashlib.sha256(serialized).hexdigest()


def prepare_apply_projection(
    export_path: str | Path,
    manifest_path: str | Path,
    crosswalk_path: str | Path,
    allowlist_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Preflight source files, bind the reviewed allow-list, and build a safe projection."""
    from scripts.baserow_reconciliation_dry_run import DryRunError, run_dry_run
    from scripts.baserow_reconciliation_projection import (
        ProjectionError,
        build_projection,
        load_allowlist,
        validate_allowlist,
    )

    export_path = Path(export_path)
    manifest_path = Path(manifest_path)
    crosswalk_path = Path(crosswalk_path)
    allowlist_path = Path(allowlist_path)
    try:
        preflight = run_dry_run(export_path, manifest_path, crosswalk_path)
    except DryRunError:
        raise ApplyError("source manifest or snapshot verification failed") from None

    try:
        export_bytes = export_path.read_bytes()
        manifest_bytes = manifest_path.read_bytes()
        crosswalk_bytes = crosswalk_path.read_bytes()
        allowlist_bytes = allowlist_path.read_bytes()
        source_metadata = preflight.get("source", {})
        preflight_summary = preflight.get("summary", {})
        if (
            hashlib.sha256(export_bytes).hexdigest() != source_metadata.get("snapshot_sha256")
            or hashlib.sha256(manifest_bytes).hexdigest() != source_metadata.get("manifest_sha256")
            or hashlib.sha256(crosswalk_bytes).hexdigest() != source_metadata.get("crosswalk_sha256")
        ):
            raise ApplyError("source inputs changed after manifest preflight")
        if source_metadata.get("manifest_schema_hash_matched") is not True:
            raise ApplyError("source manifest did not verify the snapshot hash")
        if preflight_summary.get("structural_issue_count") != 0:
            raise ApplyError("source preflight still has structural issues")

        export = json.loads(export_bytes)
        crosswalk_text = crosswalk_bytes.decode("utf-8")
        allowlist = load_allowlist(allowlist_path)
        if allowlist_path.read_bytes() != allowlist_bytes:
            raise ApplyError("projection allow-list changed while it was being validated")
        validate_allowlist(export, allowlist, crosswalk_text)
        validate_preflight_blockers(preflight, allowlist)
        projected = build_projection(export, allowlist)
        rows_by_target = projected.get("rows_by_target")
        if not isinstance(rows_by_target, dict):
            raise ApplyError("source projection did not produce target rows")
        validate_apply_plan(rows_by_target, allowlist)

        bundle = {
            "rows_by_target": rows_by_target,
            "projection_sha256": projected.get("projection_sha256"),
            "report": projected.get("report"),
            "source": {
                "snapshot_sha256": source_metadata.get("snapshot_sha256"),
                "manifest_sha256": source_metadata.get("manifest_sha256"),
                "crosswalk_sha256": source_metadata.get("crosswalk_sha256"),
                "allowlist_sha256": _canonical_allowlist_digest(allowlist),
                "manifest_schema_hash_matched": True,
            },
        }
        validate_projection_bundle(bundle, allowlist)
        return bundle, allowlist
    except ApplyError:
        raise
    except (ProjectionError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ApplyError("source, crosswalk, or allow-list projection validation failed") from None


def validate_projection_bundle(
    bundle: dict[str, Any], allowlist: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """Verify projector output, source preflight identity, and allow-list binding."""
    if not isinstance(bundle, dict):
        raise ApplyError("validated projection bundle is missing")
    rows_by_target = bundle.get("rows_by_target")
    report = bundle.get("report")
    source = bundle.get("source")
    if not isinstance(rows_by_target, dict) or not isinstance(report, dict) or not isinstance(source, dict):
        raise ApplyError("validated projection bundle is incomplete")
    if report.get("run_type") != "allowlisted_scratch_projection" or report.get("import_authorized") is not False:
        raise ApplyError("projection report is not an approved scratch projection artifact")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ApplyError("projection summary is invalid")
    expected_digest = _projection_digest(rows_by_target)
    if bundle.get("projection_sha256") != expected_digest or summary.get("projection_sha256") != expected_digest:
        raise ApplyError("projection rows changed after the source projection was built")
    if source.get("allowlist_sha256") != _canonical_allowlist_digest(allowlist):
        raise ApplyError("projection bundle does not match the supplied allow-list")
    if source.get("manifest_schema_hash_matched") is not True:
        raise ApplyError("source snapshot was not verified against its manifest")
    for key in ("snapshot_sha256", "manifest_sha256", "crosswalk_sha256", "allowlist_sha256"):
        if not isinstance(source.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", source[key]):
            raise ApplyError("projection bundle source identity is invalid")
    validate_apply_plan(rows_by_target, allowlist)
    return rows_by_target


def _comparison_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return ("uuid", str(value))
    if isinstance(value, datetime):
        return ("datetime", value.isoformat())
    if isinstance(value, date):
        return ("date", value.isoformat())
    if isinstance(value, Decimal):
        return ("decimal", value.normalize())
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, str):
        try:
            return ("uuid", str(UUID(value)))
        except ValueError:
            pass
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            try:
                return ("date", date.fromisoformat(value).isoformat())
            except ValueError:
                pass
        try:
            parsed_datetime = datetime.fromisoformat(value)
            if "T" in value or " " in value:
                return ("datetime", parsed_datetime.isoformat())
        except ValueError:
            pass
        return ("str", value)
    if isinstance(value, list):
        return ("list", tuple(_comparison_value(item) for item in value))
    if isinstance(value, dict):
        return (
            "dict",
            tuple(sorted((key, _comparison_value(item)) for key, item in value.items())),
        )
    if value is None:
        return ("null",)
    return (type(value).__name__, value)


def _same_projected_row(existing: dict[str, Any], expected: dict[str, Any], target: str) -> bool:
    columns = TARGET_COLUMNS[target]
    return set(existing) == set(columns) and all(
        _comparison_value(existing.get(column)) == _comparison_value(expected[column])
        for column in columns
    )


def apply_projection(
    store: Any,
    rows_by_target: dict[str, list[dict[str, Any]]],
    *,
    allowlist: dict[str, Any],
) -> dict[str, Any]:
    """Insert missing rows; accept only exact existing matches and readbacks.

    The caller owns the database transaction. Any exception must escape the
    caller's transaction context so it rolls back the whole batch.
    """
    targets = validate_apply_plan(rows_by_target, allowlist)
    counts = {target: {"inserted": 0, "unchanged": 0} for target in targets}
    try:
        store.begin()
        for target in targets:
            identity_keys = IDENTITY_KEYS[target]
            for record in rows_by_target[target]:
                matches = store.find_matches(target, record, identity_keys)
                if len(matches) > 1:
                    raise ApplyError("multiple target rows match a projected identity")
                if matches:
                    if not _same_projected_row(matches[0], record, target):
                        raise ApplyError("pre-existing target identity conflicts with projected data")
                    counts[target]["unchanged"] += 1
                    continue

                store.insert(target, record)
                readback = store.find_matches(target, record, identity_keys)
                if len(readback) != 1 or not _same_projected_row(readback[0], record, target):
                    raise ApplyError("insert readback did not exactly match the projection")
                counts[target]["inserted"] += 1
    except ApplyError:
        raise
    except Exception:
        raise ApplyError("apply transaction failed; the caller must roll back") from None

    inserted = sum(table_counts["inserted"] for table_counts in counts.values())
    unchanged = sum(table_counts["unchanged"] for table_counts in counts.values())
    return {
        "summary": {
            "projected_rows": inserted + unchanged,
            "inserted_rows": inserted,
            "unchanged_rows": unchanged,
            "updated_rows": 0,
            "deleted_rows": 0,
            "truncated_tables": 0,
        },
        "tables": counts,
    }


class PostgresApplyStore:
    """Parameterized INSERT-only adapter for the approved PostgreSQL targets."""

    def __init__(self, connection: Any):
        self.connection = connection

    def begin(self) -> None:
        self.connection.execute("SET CONSTRAINTS ALL DEFERRED")

    @staticmethod
    def _validate_record(target: str, record: dict[str, Any]) -> tuple[str, ...]:
        columns = TARGET_COLUMNS.get(target)
        if columns is None or not isinstance(record, dict) or set(record) != set(columns):
            raise ApplyError("PostgreSQL operation is outside the approved target schema")
        return columns

    def find_matches(
        self,
        target: str,
        record: dict[str, Any],
        identity_keys: tuple[tuple[str, ...], ...],
    ) -> list[dict[str, Any]]:
        columns = self._validate_record(target, record)
        if identity_keys != IDENTITY_KEYS.get(target):
            raise ApplyError("PostgreSQL identity query is outside the approved scope")

        clauses = []
        params: dict[str, Any] = {}
        for key_index, identity_key in enumerate(identity_keys):
            if any(
                column not in columns or record.get(column) is None or record.get(column) == ""
                for column in identity_key
            ):
                continue
            comparisons = []
            for column_index, column in enumerate(identity_key):
                parameter = f"identity_{key_index}_{column_index}"
                comparisons.append(f'"{column}" IS NOT DISTINCT FROM :{parameter}')
                params[parameter] = record[column]
            clauses.append("(" + " AND ".join(comparisons) + ")")
        if not clauses:
            raise ApplyError("PostgreSQL identity query is missing a required key")

        selected = ", ".join(f'"{column}"' for column in columns)
        sql = (
            f'SELECT {selected} FROM public."{target}" WHERE '
            + " OR ".join(clauses)
            + " LIMIT 2"
        )
        return self.connection.execute(sql, params).all()

    def insert(self, target: str, record: dict[str, Any]) -> None:
        columns = self._validate_record(target, record)
        params: dict[str, Any] = {}
        placeholders = []
        for index, column in enumerate(columns):
            parameter = f"value_{index}"
            value = record[column]
            jsonb_type = JSONB_VALUE_TYPES.get((target, column))
            if value is not None and jsonb_type is not None:
                if not isinstance(value, jsonb_type):
                    raise ApplyError("PostgreSQL JSONB value has an invalid projected type")
                try:
                    serialized = json.dumps(
                        value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                    )
                except (TypeError, ValueError):
                    raise ApplyError("PostgreSQL JSONB value is not serializable") from None
                if "\x00" in serialized or _json_contains_nul(value):
                    raise ApplyError("PostgreSQL JSONB value contains unsupported text")
                try:
                    from psycopg2.extras import Json
                except ImportError:
                    raise ApplyError("PostgreSQL driver is unavailable for JSONB insertion") from None
                params[parameter] = Json(
                    value,
                    dumps=lambda item: json.dumps(
                        item, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                    ),
                )
            else:
                params[parameter] = value
            placeholders.append(f":{parameter}")

        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        sql = (
            f'INSERT INTO public."{target}" ({quoted_columns}) '
            f'VALUES ({", ".join(placeholders)})'
        )
        result = self.connection.execute(sql, params)
        if result.rowcount != 1:
            raise ApplyError("PostgreSQL insert did not affect exactly one row")


def _json_contains_nul(value: Any) -> bool:
    if isinstance(value, str):
        return "\x00" in value
    if isinstance(value, dict):
        return any(_json_contains_nul(key) or _json_contains_nul(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_json_contains_nul(item) for item in value)
    return False


def _connection_dsn_parameters(connection: Any) -> dict[str, Any]:
    getter = getattr(connection, "get_dsn_parameters", None)
    if not callable(getter):
        raw_connection = getattr(connection, "_connection", None)
        getter = getattr(raw_connection, "get_dsn_parameters", None)
    if not callable(getter):
        raise ApplyError("database connection does not expose verifiable target identity")
    parameters = getter()
    if not isinstance(parameters, dict):
        raise ApplyError("database connection target identity is invalid")
    return parameters


def run_staging_apply(
    projection_bundle: dict[str, Any],
    allowlist: dict[str, Any],
    *,
    target: str,
    commit: bool,
    confirm_target: str | None,
    runtime_environment: str,
    configured_host: str,
    expected_target_host: str | None,
    database_name: str,
    connection_factory: Any,
    store_factory: Any = None,
) -> dict[str, Any]:
    """Return an offline plan unless an explicit verified target is selected."""
    rows_by_target = validate_projection_bundle(projection_bundle, allowlist)
    targets = tuple(target for target in TARGET_COLUMNS if target in rows_by_target)
    if not commit:
        planned = {name: len(rows_by_target[name]) for name in targets}
        return {
            "run_type": "insert_only_baserow_plan",
            "transaction_result": "not_started",
            "summary": {"planned_rows": sum(planned.values()), "database_connections": 0},
            "tables": planned,
        }

    validate_apply_target_config(
        target=target,
        commit=commit,
        confirm_target=confirm_target,
        runtime_environment=runtime_environment,
        configured_host=configured_host,
        expected_target_host=expected_target_host,
        database_name=database_name,
    )
    if store_factory is None:
        store_factory = PostgresApplyStore

    try:
        with connection_factory() as connection:
            dsn = _connection_dsn_parameters(connection)
            if dsn.get("host") != expected_target_host or dsn.get("dbname") != TARGET_DATABASE_NAME:
                raise ApplyError("connected database does not match the explicitly selected target")
            target_row = connection.execute("SELECT current_database() AS database_name").first()
            if not isinstance(target_row, dict) or target_row.get("database_name") != TARGET_DATABASE_NAME:
                raise ApplyError("connected database does not match the explicitly selected target")
            report = apply_projection(
                store_factory(connection), rows_by_target, allowlist=allowlist
            )
    except ApplyError:
        raise
    except Exception:
        raise ApplyError("target apply failed; the transaction was rolled back") from None

    report["run_type"] = "insert_only_baserow_apply"
    report["transaction_result"] = "committed"
    report["target"] = target
    report["summary"]["database_connections"] = 1
    return report
