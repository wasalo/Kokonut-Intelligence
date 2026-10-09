#!/usr/bin/env python3
"""
Export Service — CSV, JSON, Parquet

Exports collections from PostgreSQL (or ClickHouse) to files.
Logs every export to the export_log table.

Usage:
    python3 -m services.export.exporter --collection harvest_event --format csv --output exports/
    python3 -m services.export.exporter --collection expense_event --format json --filter '{"status":"verified"}'
"""

import argparse
import csv
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from ..common.database import get_db
from ..common.db import (
    CH_DB,
    CH_HOST,
    CH_PASSWORD,
    CH_PORT,
    CH_USER,
)
from ..common.utils import serialize_value

ALLOWED_COLLECTIONS = frozenset(
    {
        "harvest_event",
        "sales_event",
        "expense_event",
        "weather_observation",
        "remote_sensing_observation",
        "sensor_reading",
        "farm_activity",
        "soil_sample",
        "crop_cycle",
        "crop",
        "location",
        "farm",
        "plot",
        "partner",
        "staff",
        "infrastructure",
        "noi_snapshot",
        "forecast_output",
        "forecast_scenario",
        "attestation_record",
        "treasury_event",
        "sensor_alert",
        "agent_identity",
        "agent_task",
        "agent_action_log",
        "inventory_event",
        "maintenance_event",
        "revenue_event",
        "mrv_event",
        "attestation_request",
        "sensor_device",
        "loss_event",
        "field_note",
        "soil_carbon_measurement",
        "species_observation",
        "report_snapshot",
        "export_log",
    }
)

GOVERNED_COLLECTIONS = frozenset(
    {
        "harvest_event",
        "sales_event",
        "expense_event",
        "farm_activity",
        "loss_event",
        "field_note",
        "forecast_scenario",
        "report_snapshot",
        "attestation_record",
        "inventory_event",
        "maintenance_event",
        "revenue_event",
        "mrv_event",
        "attestation_request",
    }
)

VALID_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(name: str, label: str = "identifier") -> str:
    """Validate that a string is a safe SQL identifier (alphanumeric + underscore)."""
    if not VALID_IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid {label}: {name!r}")
    return name


def _validate_collection(collection: str) -> str:
    """Validate collection name against allowlist."""
    _validate_identifier(collection, "collection")
    if collection not in ALLOWED_COLLECTIONS:
        raise ValueError(f"Invalid collection: {collection!r}. Allowed: {', '.join(sorted(ALLOWED_COLLECTIONS))}")
    return collection


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for safe use in filenames."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


# ---------------------------------------------------------------------------
# Database connections
# ---------------------------------------------------------------------------


def get_pg():
    return get_db()


def get_ch():
    try:
        import clickhouse_connect

        return clickhouse_connect.get_client(
            host=CH_HOST, port=CH_PORT, username=CH_USER, password=CH_PASSWORD, database=CH_DB
        )
    except ImportError:
        print("WARNING: clickhouse_connect not installed. ClickHouse exports unavailable.")
        return None


# ---------------------------------------------------------------------------
# Export result
# ---------------------------------------------------------------------------


class ExportResult:
    def __init__(self, collection: str, fmt: str, file_path: str, row_count: int, file_size: int, duration_ms: int):
        self.collection = collection
        self.format = fmt
        self.file_path = file_path
        self.row_count = row_count
        self.file_size = file_size
        self.duration_ms = duration_ms

    def __repr__(self):
        return (
            f"ExportResult(collection={self.collection!r}, format={self.format!r}, "
            f"rows={self.row_count}, size={self.file_size}, path={self.file_path!r})"
        )


# ---------------------------------------------------------------------------
# Core exporter
# ---------------------------------------------------------------------------


class Exporter:
    BATCH_SIZE = 1000

    def __init__(self, source: str = "postgresql"):
        self.source = source

    def export(
        self,
        collection: str,
        fmt: str = "csv",
        output_dir: str = "exports/",
        filters: Optional[dict] = None,
        user_id: Optional[str] = None,
        include_drafts: bool = False,
    ) -> ExportResult:
        _validate_collection(collection)
        if fmt not in {"csv", "json", "parquet"}:
            raise ValueError(f"Unsupported format: {fmt}")
        os.makedirs(output_dir, exist_ok=True)

        start = time.time()

        # Generate filename (sanitized)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_name = _sanitize_filename(collection)
        filename = f"{safe_name}_{timestamp}.{fmt}"
        file_path = os.path.join(output_dir, filename)

        # Validate resolved path stays within output_dir
        resolved_output = os.path.realpath(output_dir)
        resolved_path = os.path.realpath(os.path.dirname(os.path.join(output_dir, filename)))
        if not resolved_path.startswith(resolved_output + os.sep) and resolved_path != resolved_output:
            raise ValueError(f"Path traversal detected in output path: {file_path}")

        rows = []
        try:
            if self.source == "clickhouse":
                row_iter, columns = self._iter_clickhouse(collection, filters)
            else:
                row_iter, columns = self._iter_postgres(collection, filters, include_drafts=include_drafts)

            # Parquet requires a materialized table; text formats stream batches.
            if fmt == "parquet":
                rows = list(row_iter)
            temp_fd, temp_path = tempfile.mkstemp(prefix=f".{safe_name}-", suffix=".tmp", dir=output_dir)
            os.close(temp_fd)
            if fmt == "csv":
                row_count = self._write_csv(row_iter, columns, temp_path)
            elif fmt == "json":
                row_count = self._write_json(row_iter, columns, temp_path)
            elif fmt == "parquet":
                row_count = self._write_parquet(rows, columns, temp_path)
            else:
                raise ValueError(f"Unsupported format: {fmt}")
            os.replace(temp_path, file_path)
            file_size = os.path.getsize(file_path)
            duration_ms = int((time.time() - start) * 1000)
            self._log_export(collection, fmt, filters, row_count, file_size, file_path, user_id, "completed")
            result = ExportResult(collection, fmt, file_path, row_count, file_size, duration_ms)
            print(f"Exported {row_count} rows to {file_path} ({duration_ms}ms)")
            return result
        except Exception as exc:
            self._log_export(collection, fmt, filters, len(rows), 0, file_path, user_id, "failed", str(exc))
            if "temp_path" in locals():
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass
            raise

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _query_postgres(self, collection: str, filters: Optional[dict], include_drafts: bool = False):
        row_iter, columns = self._iter_postgres(collection, filters, include_drafts)
        return list(row_iter), columns

    def _iter_postgres(self, collection: str, filters: Optional[dict], include_drafts: bool = False):
        _validate_identifier(collection, "table name")
        filters = self._apply_default_governance_filter(collection, filters, include_drafts)
        where_clause = ""
        params = []
        if filters:
            where_clause, params = self._build_where(filters)

        conn = get_pg()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        except Exception:
            conn.close()
            raise

        query = f"SELECT * FROM {collection} {where_clause} ORDER BY created_at DESC NULLS LAST, id DESC"
        try:
            cur.execute(query, params)
        except Exception:
            cur.close()
            conn.close()
            raise
        columns = [desc[0] for desc in cur.description] if cur.description else []

        def batches():
            try:
                while True:
                    batch = cur.fetchmany(self.BATCH_SIZE)
                    if not batch:
                        break
                    for row in batch:
                        yield self._clean_row(row)
            finally:
                cur.close()
                conn.close()

        return batches(), columns

    @staticmethod
    def _clean_row(row):
        return {
            k: serialize_value(v)
            for k, v in dict(row).items()
        }

    def _apply_default_governance_filter(
        self, collection: str, filters: Optional[dict], include_drafts: bool
    ) -> Optional[dict]:
        """Default governed exports to verified/published unless explicitly overridden."""
        if include_drafts or collection not in GOVERNED_COLLECTIONS:
            return filters

        merged = dict(filters or {})
        if "status" not in merged:
            merged["status"] = {"$in": ["verified", "published"]}
        return merged

    def _query_clickhouse(self, collection: str, filters: Optional[dict]):
        row_iter, columns = self._iter_clickhouse(collection, filters)
        return list(row_iter), columns

    def _iter_clickhouse(self, collection: str, filters: Optional[dict]):
        _validate_identifier(collection, "table name")
        client = get_ch()
        if client is None:
            raise RuntimeError("ClickHouse client unavailable")

        where_clause, params = self._build_clickhouse_where(filters)
        query = f"SELECT * FROM {collection} {where_clause} ORDER BY timestamp DESC, id DESC"
        try:
            result = client.query(query, parameters=params)
        except Exception:
            close = getattr(client, "close", None)
            if close:
                close()
            raise
        columns = result.column_names

        def rows():
            try:
                for row in result.result_rows:
                    yield dict(zip(columns, row))
            finally:
                close = getattr(client, "close", None)
                if close:
                    close()

        return rows(), columns

    def _build_clickhouse_where(self, filters):
        if not filters:
            return "", {}
        conditions = []
        params = {}
        for key, value in filters.items():
            _validate_identifier(key, "filter key")
            if isinstance(value, dict):
                for op, val in value.items():
                    if op not in {"$gte", "$lte", "$gt", "$lt", "$ne", "$in", "$like"}:
                        raise ValueError(f"Unsupported filter operator: {op}")
                    if op == "$in":
                        if not isinstance(val, (list, tuple)) or not val:
                            raise ValueError("$in requires a non-empty list")
                        names = []
                        for index, item in enumerate(val):
                            name = f"{key}_{index}"
                            names.append("{" + name + "}")
                            params[name] = item
                        conditions.append(f"{key} IN ({', '.join(names)})")
                    else:
                        name = f"{key}_{len(params)}"
                        operator = {"$gte": ">=", "$lte": "<=", "$gt": ">", "$lt": "<", "$ne": "!=", "$like": "LIKE"}[
                            op
                        ]
                        conditions.append(f"{key} {operator} {{{name}}}")
                        params[name] = val
            elif isinstance(value, (list, tuple)):
                if not value:
                    raise ValueError("list filter requires a non-empty list")
                names = []
                for index, item in enumerate(value):
                    name = f"{key}_{index}"
                    names.append("{" + name + "}")
                    params[name] = item
                conditions.append(f"{key} IN ({', '.join(names)})")
            else:
                name = f"{key}_{len(params)}"
                conditions.append(f"{key} = {{{name}}}")
                params[name] = value
        return "WHERE " + " AND ".join(conditions), params

    def _build_where(self, filters: dict):
        """Build a PostgreSQL WHERE clause from a filter dict."""
        conditions = []
        params = []
        for key, value in filters.items():
            _validate_identifier(key, "filter key")
            if isinstance(value, dict):
                for op, val in value.items():
                    if op == "$gte":
                        conditions.append(f"{key} >= %s")
                        params.append(val)
                    elif op == "$lte":
                        conditions.append(f"{key} <= %s")
                        params.append(val)
                    elif op == "$gt":
                        conditions.append(f"{key} > %s")
                        params.append(val)
                    elif op == "$lt":
                        conditions.append(f"{key} < %s")
                        params.append(val)
                    elif op == "$ne":
                        conditions.append(f"{key} != %s")
                        params.append(val)
                    elif op == "$in":
                        if not isinstance(val, (list, tuple)) or not val:
                            raise ValueError("$in requires a non-empty list")
                        placeholders = ", ".join(["%s"] * len(val))
                        conditions.append(f"{key} IN ({placeholders})")
                        params.extend(val)
                    elif op == "$like":
                        conditions.append(f"{key} LIKE %s")
                        params.append(val)
                    else:
                        raise ValueError(f"Unsupported filter operator: {op}")
            elif isinstance(value, list):
                if not value:
                    raise ValueError("list filter requires a non-empty list")
                placeholders = ", ".join(["%s"] * len(value))
                conditions.append(f"{key} IN ({placeholders})")
                params.extend(value)
            else:
                conditions.append(f"{key} = %s")
                params.append(value)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        return where, params

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------

    def _write_csv(self, rows, columns, file_path):
        count = 0
        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
                count += 1
        return count

    def _write_json(self, rows, columns, file_path):
        count = 0
        with open(file_path, "w") as f:
            f.write('{"collection": ' + json.dumps(columns[0] if columns else "") + ', "count": ')
            count_position = f.tell()
            f.write(" " * 20)
            f.write(', "data": [')
            for row in rows:
                if count:
                    f.write(",")
                json.dump(row, f, default=str)
                count += 1
            f.write("]}")
            f.seek(count_position)
            f.write(str(count).rjust(20))
        return count

    def _write_parquet(self, rows, columns, file_path):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            # Convert to arrow
            arrays = []
            for col in columns:
                values = [row.get(col) for row in rows]
                # Detect type
                sample = next((v for v in values if v is not None), None)
                if isinstance(sample, (int, float)):
                    arrays.append(pa.array(values, type=pa.float64()))
                elif isinstance(sample, bool):
                    arrays.append(pa.array(values, type=pa.bool_()))
                else:
                    arrays.append(pa.array([str(v) if v is not None else None for v in values], type=pa.string()))

            table = pa.table(arrays, names=columns)
            pq.write_table(table, file_path)
            return len(rows)
        except ImportError:
            raise RuntimeError("pyarrow is required for parquet exports")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_export(
        self, collection, fmt, filters, row_count, file_size, file_path, user_id, status="completed", error=None
    ):
        conn = None
        cur = None
        try:
            conn = get_pg()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO export_log (user_id, export_type, target_table, filters, row_count, file_size_bytes, file_url, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, fmt, collection, json.dumps(filters, default=str), row_count, file_size, file_path, status),
            )
            conn.commit()
        except Exception as e:
            print(f"WARNING: Failed to log export: {e}")
        finally:
            if cur is not None:
                cur.close()
            if conn is not None:
                conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Export Kokonut data to files")
    parser.add_argument("--collection", required=True, help="Collection/table to export")
    parser.add_argument("--format", choices=["csv", "json", "parquet"], default="csv", help="Output format")
    parser.add_argument("--output", default="exports/", help="Output directory")
    parser.add_argument("--filter", default=None, help="JSON filter expression")
    parser.add_argument("--source", choices=["postgresql", "clickhouse"], default="postgresql", help="Data source")
    parser.add_argument("--user-id", default=None, help="User ID for audit log")
    parser.add_argument(
        "--include-drafts",
        action="store_true",
        help="Include draft/submitted/rejected records for governed collections",
    )
    args = parser.parse_args()

    filters = json.loads(args.filter) if args.filter else None
    exporter = Exporter(source=args.source)
    result = exporter.export(
        collection=args.collection,
        fmt=args.format,
        output_dir=args.output,
        filters=filters,
        user_id=args.user_id,
        include_drafts=args.include_drafts,
    )
    print(result)


if __name__ == "__main__":
    main()
