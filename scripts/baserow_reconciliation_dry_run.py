#!/usr/bin/env python3
"""Offline, redacted preflight for the owner-provided Baserow snapshot.

This tool validates snapshot/manifest integrity, exact source-field coverage,
field-disposition census, and source link integrity. It does not connect to a
database, construct canonical records, import data, or emit source row values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


DATABASE_ID = "115056"
DISPOSITIONS = {
    "CANDIDATE",
    "CONDITIONAL",
    "EXCLUDE_DERIVED",
    "EXCLUDE_SENSITIVE",
    "HOLD_FIELD",
    "HOLD_RELATIONSHIP",
    "MANUAL_CURATION",
    "PROVENANCE_ONLY",
    "RELATIONSHIP",
}
VALUE_EXCLUSIONS = {"EXCLUDE_DERIVED", "EXCLUDE_SENSITIVE", "MANUAL_CURATION"}
BLOCKING_DISPOSITIONS = {"CONDITIONAL", "HOLD_FIELD", "HOLD_RELATIONSHIP"}
TABLE_HEADER = re.compile(r"^### .*\(table ID `([^`]+)`; (\d+) fields\)$")
FIELD_ID = re.compile(r"^`([^`]+)`\s+\(`([^`]+)`\)$")
SCHEMA_DIGEST = re.compile(r"_([0-9a-f]{64})\.json$")


class DryRunError(ValueError):
    """Raised when the snapshot, manifest, or crosswalk is structurally unsafe."""


def _is_populated(value: Any) -> bool:
    """Return presence without serializing or displaying the value."""
    return value is not None and value != "" and value != [] and value != {}


def _parse_crosswalk(text: str) -> tuple[dict[str, dict[str, dict[str, str]]], dict[str, int]]:
    tables: dict[str, dict[str, dict[str, str]]] = {}
    declared_counts: dict[str, int] = {}
    current_table_id: str | None = None

    for line in text.splitlines():
        if line.startswith("### "):
            match = TABLE_HEADER.match(line)
            if match:
                current_table_id = match.group(1)
                if current_table_id in tables:
                    raise DryRunError(f"duplicate crosswalk table ID {current_table_id}")
                tables[current_table_id] = {}
                declared_counts[current_table_id] = int(match.group(2))
            else:
                current_table_id = None
            continue

        if current_table_id is None or not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) < 5:
            continue
        source_match = FIELD_ID.match(cells[0])
        if not source_match:
            continue
        field_name, field_id = source_match.groups()
        source_type_match = re.search(r"`([^`]+)`", cells[1])
        disposition = cells[3].strip().strip("`")
        if not source_type_match:
            raise DryRunError(f"crosswalk field {current_table_id}.{field_id} has no source type")
        if disposition not in DISPOSITIONS:
            raise DryRunError(f"crosswalk field {current_table_id}.{field_id} has invalid disposition")
        if field_id in tables[current_table_id]:
            raise DryRunError(f"duplicate crosswalk field {current_table_id}.{field_id}")
        tables[current_table_id][field_id] = {
            "name": field_name,
            "source_type": source_type_match.group(1),
            "target": cells[2],
            "disposition": disposition,
        }

    for table_id, fields in tables.items():
        if len(fields) != declared_counts[table_id]:
            raise DryRunError(f"crosswalk field coverage count differs for table {table_id}")
    return tables, declared_counts


def _manifest_database_item(manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        items = manifest["applications"]["database"]["items"]
    except (KeyError, TypeError) as exc:
        raise DryRunError("manifest lacks database item metadata") from exc
    matches = [item for item in items if str(item.get("id")) == DATABASE_ID]
    if len(matches) != 1:
        raise DryRunError(f"manifest must identify database {DATABASE_ID} exactly once")
    return matches[0]


def _link_ids(value: Any) -> tuple[list[str], int]:
    if not _is_populated(value):
        return [], 0
    entries = value if isinstance(value, list) else [value]
    ids: list[str] = []
    malformed = 0
    for entry in entries:
        if isinstance(entry, dict):
            entry = entry.get("id", entry.get("row_id"))
        if isinstance(entry, bool) or not isinstance(entry, (int, str)) or not str(entry).isdigit():
            malformed += 1
            continue
        ids.append(str(entry))
    return ids, malformed


def _validate_inventory(
    export: dict[str, Any], crosswalk: dict[str, dict[str, dict[str, str]]]
) -> tuple[dict[str, dict[str, dict[str, str]]], dict[str, set[str]]]:
    source_tables = export.get("tables")
    if not isinstance(source_tables, list):
        raise DryRunError("source export has no tables array")
    table_by_id: dict[str, dict[str, Any]] = {}
    row_ids_by_table: dict[str, set[str]] = {}
    source_keys: set[tuple[str, str]] = set()

    for table in source_tables:
        table_id = str(table.get("id"))
        if table_id in table_by_id:
            raise DryRunError(f"source export has duplicate table ID {table_id}")
        table_by_id[table_id] = table
        fields = table.get("fields")
        rows = table.get("rows")
        if not isinstance(fields, list) or not isinstance(rows, list):
            raise DryRunError(f"source table {table_id} lacks a fields or rows array")
        seen_field_ids: set[str] = set()
        for field in fields:
            field_id = str(field.get("id"))
            if field_id in seen_field_ids:
                raise DryRunError(f"source table {table_id} has duplicate field ID {field_id}")
            seen_field_ids.add(field_id)
            source_keys.add((table_id, field_id))
        row_ids: set[str] = set()
        for row in rows:
            if row.get("id") is not None:
                row_ids.add(str(row["id"]))
        row_ids_by_table[table_id] = row_ids

    crosswalk_keys = {
        (table_id, field_id)
        for table_id, fields in crosswalk.items()
        for field_id in fields
    }
    if source_keys != crosswalk_keys:
        missing = len(source_keys - crosswalk_keys)
        extra = len(crosswalk_keys - source_keys)
        raise DryRunError(
            f"crosswalk field coverage mismatch: {missing} source fields missing, {extra} extra crosswalk fields"
        )
    if set(table_by_id) != set(crosswalk):
        raise DryRunError("crosswalk table coverage mismatch")
    for table_id, table in table_by_id.items():
        for field in table["fields"]:
            field_id = str(field["id"])
            mapping = crosswalk[table_id][field_id]
            if mapping["name"] != str(field.get("name")) or mapping["source_type"] != str(field.get("type")):
                raise DryRunError(f"crosswalk field metadata mismatch for {table_id}.{field_id}")
    return table_by_id, row_ids_by_table


def _build_report(
    export: dict[str, Any],
    crosswalk: dict[str, dict[str, dict[str, str]]],
    table_by_id: dict[str, dict[str, Any]],
    row_ids_by_table: dict[str, set[str]],
    *,
    snapshot_sha256: str,
    manifest_sha256: str,
    crosswalk_sha256: str,
) -> dict[str, Any]:
    total_rows = 0
    total_fields = 0
    duplicate_row_ids = 0
    link_fields = 0
    link_references = 0
    dangling_links = 0
    malformed_links = 0
    candidate_cells = 0
    conditional_cells = 0
    held_cells = 0
    relationship_cells = 0
    provenance_cells = 0
    blocking_fields_with_data: list[dict[str, Any]] = []
    table_reports: list[dict[str, Any]] = []
    structural_issues: list[dict[str, Any]] = []

    for table_id, table in table_by_id.items():
        rows = table["rows"]
        fields = table["fields"]
        total_rows += len(rows)
        total_fields += len(fields)
        field_dispositions: Counter[str] = Counter()
        nonempty_cells: Counter[str] = Counter()
        table_link_fields = 0
        table_link_references = 0
        table_dangling_links = 0
        seen_row_ids: set[str] = set()
        duplicate_count = 0
        for row in rows:
            row_id = row.get("id")
            if row_id is None:
                structural_issues.append({"code": "MISSING_ROW_ID", "table_id": table_id, "count": 1})
                continue
            row_key = str(row_id)
            if row_key in seen_row_ids:
                duplicate_count += 1
            seen_row_ids.add(row_key)
        if duplicate_count:
            duplicate_row_ids += duplicate_count
            structural_issues.append({"code": "DUPLICATE_ROW_ID", "table_id": table_id, "count": duplicate_count})

        for field in fields:
            field_id = str(field["id"])
            mapping = crosswalk[table_id][field_id]
            disposition = mapping["disposition"]
            field_dispositions[disposition] += 1
            field_key = f"field_{field_id}"

            if disposition not in VALUE_EXCLUSIONS:
                populated_count = sum(1 for row in rows if _is_populated(row.get(field_key)))
                nonempty_cells[disposition] += populated_count
                if disposition in BLOCKING_DISPOSITIONS and populated_count:
                    blocking_fields_with_data.append(
                        {"table_id": table_id, "field_id": field_id, "disposition": disposition, "populated_cells": populated_count}
                    )
                if disposition == "CANDIDATE":
                    candidate_cells += populated_count
                elif disposition == "CONDITIONAL":
                    conditional_cells += populated_count
                elif disposition in {"HOLD_FIELD", "HOLD_RELATIONSHIP"}:
                    held_cells += populated_count
                elif disposition == "RELATIONSHIP":
                    relationship_cells += populated_count
                elif disposition == "PROVENANCE_ONLY":
                    provenance_cells += populated_count

            if field.get("type") != "link_row":
                continue
            link_fields += 1
            table_link_fields += 1
            target_table_id = field.get("link_row_table_id")
            target_table_key = str(target_table_id) if target_table_id is not None else None
            target_rows = row_ids_by_table.get(target_table_key, set()) if target_table_key is not None else set()
            field_refs = 0
            field_dangling = 0
            field_malformed = 0
            for row in rows:
                refs, malformed = _link_ids(row.get(field_key))
                field_malformed += malformed
                field_refs += len(refs)
                if target_table_key is None or target_table_key not in table_by_id:
                    field_dangling += len(refs)
                else:
                    field_dangling += sum(1 for ref in refs if ref not in target_rows)
            link_references += field_refs
            table_link_references += field_refs
            dangling_links += field_dangling
            table_dangling_links += field_dangling
            malformed_links += field_malformed
            if field_dangling:
                structural_issues.append(
                    {
                        "code": "DANGLING_LINK_REFERENCE",
                        "table_id": table_id,
                        "field_id": field_id,
                        "count": field_dangling,
                    }
                )
            if field_malformed:
                structural_issues.append(
                    {
                        "code": "MALFORMED_LINK_REFERENCE",
                        "table_id": table_id,
                        "field_id": field_id,
                        "count": field_malformed,
                    }
                )

        table_reports.append(
            {
                "table_id": table_id,
                "row_count": len(rows),
                "field_count": len(fields),
                "field_dispositions": dict(sorted(field_dispositions.items())),
                "nonempty_cells_by_disposition": dict(sorted(nonempty_cells.items())),
                "link_field_count": table_link_fields,
                "link_reference_count": table_link_references,
                "dangling_link_reference_count": table_dangling_links,
                "duplicate_row_id_count": duplicate_count,
            }
        )

    import_blocked = bool(structural_issues or blocking_fields_with_data or candidate_cells or conditional_cells)
    run_id_material = f"{snapshot_sha256}:{manifest_sha256}:{crosswalk_sha256}:baserow-preflight-v1"
    return {
        "report_version": 1,
        "run_id": hashlib.sha256(run_id_material.encode("ascii")).hexdigest(),
        "run_type": "offline_no_write_preflight",
        "source": {
            "database_id": str(export.get("id")),
            "snapshot_sha256": snapshot_sha256,
            "manifest_sha256": manifest_sha256,
            "crosswalk_sha256": crosswalk_sha256,
            "manifest_schema_hash_matched": True,
            "whole_export_parsed_in_memory": True,
        },
        "execution": {
            "database_connections": 0,
            "target_rows_written": 0,
            "staging_touched": False,
            "production_touched": False,
            "raw_row_values_emitted": False,
            "sensitive_field_values_included_in_projection": False,
        },
        "summary": {
            "status": "PREFLIGHT_REVIEW_REQUIRED" if structural_issues else "PREFLIGHT_COMPLETED_WITH_HOLDS",
            "ready_for_import": False,
            "source_tables": len(table_by_id),
            "source_rows": total_rows,
            "source_fields": total_fields,
            "crosswalk_fields": total_fields,
            "candidate_nonempty_cells": candidate_cells,
            "conditional_nonempty_cells": conditional_cells,
            "held_nonempty_cells": held_cells,
            "relationship_nonempty_cells": relationship_cells,
            "provenance_nonempty_cells": provenance_cells,
            "link_fields": link_fields,
            "link_references": link_references,
            "dangling_link_references": dangling_links,
            "malformed_link_references": malformed_links,
            "duplicate_source_row_ids": duplicate_row_ids,
            "blocking_fields_with_data": len(blocking_fields_with_data),
            "structural_issue_count": len(structural_issues),
            "import_blocked": import_blocked,
        },
        "tables": table_reports,
        "blocking_fields": blocking_fields_with_data,
        "structural_issues": structural_issues,
    }


def run_dry_run(export_path: Path, manifest_path: Path, crosswalk_path: Path) -> dict[str, Any]:
    """Verify and profile a snapshot without making a database connection."""
    export_path = Path(export_path)
    manifest_path = Path(manifest_path)
    crosswalk_path = Path(crosswalk_path)
    try:
        export_bytes = export_path.read_bytes()
        manifest_bytes = manifest_path.read_bytes()
        crosswalk_bytes = crosswalk_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        export = json.loads(export_bytes)
        crosswalk_text = crosswalk_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DryRunError("could not read or parse one of the preflight inputs") from exc

    item = _manifest_database_item(manifest)
    schema_reference = item.get("files", {}).get("schema")
    if not isinstance(schema_reference, str):
        raise DryRunError("manifest lacks the database schema export reference")
    digest_match = SCHEMA_DIGEST.search(schema_reference)
    if not digest_match:
        raise DryRunError("manifest schema filename lacks a SHA-256 digest")
    snapshot_sha256 = hashlib.sha256(export_bytes).hexdigest()
    if snapshot_sha256 != digest_match.group(1):
        raise DryRunError("source export SHA-256 does not match the manifest schema digest")
    if str(export.get("id")) != DATABASE_ID:
        raise DryRunError(f"source export database ID does not match {DATABASE_ID}")

    crosswalk, _ = _parse_crosswalk(crosswalk_text)
    table_by_id, row_ids_by_table = _validate_inventory(export, crosswalk)
    return _build_report(
        export,
        crosswalk,
        table_by_id,
        row_ids_by_table,
        snapshot_sha256=snapshot_sha256,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        crosswalk_sha256=hashlib.sha256(crosswalk_bytes).hexdigest(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an offline, redacted Baserow reconciliation preflight")
    parser.add_argument("--export", required=True, type=Path, help="Owner-provided Baserow JSON export")
    parser.add_argument("--manifest", required=True, type=Path, help="Export manifest JSON")
    parser.add_argument("--crosswalk", required=True, type=Path, help="Reviewed field crosswalk Markdown")
    parser.add_argument("--output", type=Path, help="Optional path for the redacted JSON report")
    args = parser.parse_args(argv)
    try:
        report = run_dry_run(args.export, args.manifest, args.crosswalk)
    except DryRunError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["summary"]["structural_issue_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
