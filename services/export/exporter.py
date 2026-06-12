#!/usr/bin/env python3
"""
Export Service — CSV, JSON, Parquet

Exports collections from PostgreSQL (or ClickHouse) to files.
Logs every export to the export_log table.

Usage:
    python3 -m services.export.exporter --collection harvest_event --format csv --output exports/
    python3 -m services.export.exporter --collection expense_event --format json --filter '{"status":"approved"}'
"""

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _load_env():
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


_load_env()

PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DB = os.environ.get("PG_DB", "kokonut_intelligence")
PG_USER = os.environ.get("PG_USER", "kokonut")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "dev-kokonut-postgres-2026")

CH_HOST = os.environ.get("CH_HOST", "localhost")
CH_PORT = int(os.environ.get("CH_PORT", "8123"))
CH_USER = os.environ.get("CH_USER", "kokonut")
CH_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "dev-clickhouse-kokonut-2026")
CH_DB = os.environ.get("CH_DB", "default")


# ---------------------------------------------------------------------------
# Database connections
# ---------------------------------------------------------------------------

def get_pg():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )


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
    def __init__(self, source: str = "postgresql"):
        self.source = source

    def export(
        self,
        collection: str,
        fmt: str = "csv",
        output_dir: str = "exports/",
        filters: Optional[dict] = None,
        user_id: Optional[str] = None,
    ) -> ExportResult:
        os.makedirs(output_dir, exist_ok=True)

        start = time.time()

        if self.source == "clickhouse":
            rows, columns = self._query_clickhouse(collection, filters)
        else:
            rows, columns = self._query_postgres(collection, filters)

        # Generate filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{collection}_{timestamp}.{fmt}"
        file_path = os.path.join(output_dir, filename)

        # Write file
        if fmt == "csv":
            self._write_csv(rows, columns, file_path)
        elif fmt == "json":
            self._write_json(rows, columns, file_path)
        elif fmt == "parquet":
            file_path = self._write_parquet(rows, columns, file_path)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        duration_ms = int((time.time() - start) * 1000)
        file_size = os.path.getsize(file_path)

        # Log export
        self._log_export(collection, fmt, filters, len(rows), file_size, file_path, user_id)

        result = ExportResult(collection, fmt, file_path, len(rows), file_size, duration_ms)
        print(f"Exported {len(rows)} rows to {file_path} ({duration_ms}ms)")
        return result

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _query_postgres(self, collection: str, filters: Optional[dict]):
        conn = get_pg()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        where_clause = ""
        params = []
        if filters:
            where_clause, params = self._build_where(filters)

        query = f"SELECT * FROM {collection} {where_clause} ORDER BY created_at DESC NULLS LAST"
        cur.execute(query, params)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description] if cur.description else []
        cur.close()
        conn.close()

        # Convert non-serializable types
        clean_rows = []
        for row in rows:
            clean = {}
            for k, v in dict(row).items():
                if hasattr(v, "isoformat"):
                    clean[k] = v.isoformat()
                elif isinstance(v, (bytes, memoryview)):
                    clean[k] = hashlib.sha256(bytes(v)).hexdigest()[:16]
                else:
                    clean[k] = v
            clean_rows.append(clean)

        return clean_rows, columns

    def _query_clickhouse(self, collection: str, filters: Optional[dict]):
        client = get_ch()
        if client is None:
            raise RuntimeError("ClickHouse client unavailable")

        where_clause = ""
        params = {}
        if filters:
            where_parts = []
            for k, v in filters.items():
                where_parts.append(f"{k} = {{{k}}}")
                params[k] = v
            where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        query = f"SELECT * FROM {collection} {where_clause} ORDER BY timestamp DESC LIMIT 100000"
        result = client.query(query, parameters=params)
        rows = [dict(zip(result.column_names, row)) for row in result.result_rows]
        columns = result.column_names
        return rows, columns

    def _build_where(self, filters: dict):
        """Build a PostgreSQL WHERE clause from a filter dict."""
        conditions = []
        params = []
        for key, value in filters.items():
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
                        placeholders = ", ".join(["%s"] * len(val))
                        conditions.append(f"{key} IN ({placeholders})")
                        params.extend(val)
                    elif op == "$like":
                        conditions.append(f"{key} LIKE %s")
                        params.append(val)
            elif isinstance(value, list):
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
        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def _write_json(self, rows, columns, file_path):
        with open(file_path, "w") as f:
            json.dump({"collection": columns[0] if columns else "", "count": len(rows), "data": rows}, f, indent=2, default=str)

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
            return file_path
        except ImportError:
            # Fallback: write as JSON with .json extension
            print("WARNING: pyarrow not installed. Falling back to JSON format.")
            json_path = file_path.replace(".parquet", ".json")
            self._write_json(rows, columns, json_path)
            return json_path

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_export(self, collection, fmt, filters, row_count, file_size, file_path, user_id):
        try:
            conn = get_pg()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO export_log (user_id, export_type, target_table, filters, row_count, file_size_bytes, file_url, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, fmt, collection, json.dumps(filters, default=str), row_count, file_size, file_path, "completed"),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"WARNING: Failed to log export: {e}")


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
    args = parser.parse_args()

    filters = json.loads(args.filter) if args.filter else None
    exporter = Exporter(source=args.source)
    result = exporter.export(
        collection=args.collection,
        fmt=args.format,
        output_dir=args.output,
        filters=filters,
        user_id=args.user_id,
    )
    print(result)


if __name__ == "__main__":
    main()
