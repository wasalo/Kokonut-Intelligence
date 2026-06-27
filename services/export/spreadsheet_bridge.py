"""CSV spreadsheet bridge for low-barrier farm activity exchange."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

import psycopg2.extras

from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER

FARM_ACTIVITY_FIELDS = [
    "location_id",
    "plot_id",
    "crop_cycle_id",
    "activity_type",
    "activity_date",
    "description",
    "labor_hours",
    "labor_cost",
    "materials_used",
    "notes",
    "source_system",
    "source_id",
]
REQUIRED_FARM_ACTIVITY_FIELDS = {"location_id", "activity_type", "activity_date", "description"}

EBF_SCORECARD_FIELDS = [
    "location_id",
    "farm_id",
    "period_start",
    "period_end",
    "rubric_version",
    "calibration_method",
    "calibration_report_url",
]
REQUIRED_EBF_SCORECARD_FIELDS = {"location_id", "period_start", "period_end", "rubric_version"}

EBF_EVIDENCE_FIELDS = [
    "scorecard_id",
    "pillar_key",
    "evidence_type",
    "evidence_id",
    "evidence_maturity_level",
    "evidence_summary",
]
REQUIRED_EBF_EVIDENCE_FIELDS = {"scorecard_id", "pillar_key", "evidence_type", "evidence_id"}
EBF_EVIDENCE_TYPES = {
    "metric_value", "soil_sample", "species_observation", "water_analysis", "remote_sensing_observation",
    "stakeholder_feedback", "stakeholder_outcome", "impact_claim", "attestation_record", "report_snapshot", "file_upload",
}


def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def template_rows() -> list[dict[str, str]]:
    """Return one example row suitable for CSV template generation."""
    return [{field: "" for field in FARM_ACTIVITY_FIELDS}]


def ebf_scorecard_template_rows() -> list[dict[str, str]]:
    """Return one example EBF scorecard row for CSV template generation."""
    return [{field: "" for field in EBF_SCORECARD_FIELDS}]


def ebf_evidence_template_rows() -> list[dict[str, str]]:
    """Return one example EBF evidence-link row for CSV template generation."""
    return [{field: "" for field in EBF_EVIDENCE_FIELDS}]


def validate_farm_activity_row(row: dict[str, Any], row_number: int) -> list[str]:
    """Validate one farm activity import row."""
    errors: list[str] = []
    for field in REQUIRED_FARM_ACTIVITY_FIELDS:
        if not str(row.get(field) or "").strip():
            errors.append(f"row {row_number}: missing required field {field}")
    if row.get("labor_hours") not in (None, ""):
        try:
            if float(row["labor_hours"]) < 0:
                errors.append(f"row {row_number}: labor_hours must be non-negative")
        except ValueError:
            errors.append(f"row {row_number}: labor_hours must be numeric")
    if row.get("labor_cost") not in (None, ""):
        try:
            if float(row["labor_cost"]) < 0:
                errors.append(f"row {row_number}: labor_cost must be non-negative")
        except ValueError:
            errors.append(f"row {row_number}: labor_cost must be numeric")
    return errors


def validate_ebf_scorecard_row(row: dict[str, Any], row_number: int) -> list[str]:
    """Validate one EBF scorecard import row."""
    errors: list[str] = []
    for field in REQUIRED_EBF_SCORECARD_FIELDS:
        if not str(row.get(field) or "").strip():
            errors.append(f"row {row_number}: missing required field {field}")
    if row.get("calibration_method") not in (None, "", "third_party", "team_with_report", "mixed_panel"):
        errors.append(f"row {row_number}: calibration_method must be third_party, team_with_report, or mixed_panel")
    return errors


def validate_ebf_evidence_row(row: dict[str, Any], row_number: int) -> list[str]:
    """Validate one EBF evidence-link import row."""
    errors: list[str] = []
    for field in REQUIRED_EBF_EVIDENCE_FIELDS:
        if not str(row.get(field) or "").strip():
            errors.append(f"row {row_number}: missing required field {field}")
    if row.get("evidence_type") and row["evidence_type"] not in EBF_EVIDENCE_TYPES:
        errors.append(f"row {row_number}: evidence_type is not supported")
    if row.get("evidence_maturity_level") not in (None, ""):
        try:
            level = int(row["evidence_maturity_level"])
            if level < 0 or level > 6:
                errors.append(f"row {row_number}: evidence_maturity_level must be between 0 and 6")
        except ValueError:
            errors.append(f"row {row_number}: evidence_maturity_level must be an integer")
    return errors


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def write_csv(path: str, rows: Iterable[dict[str, Any]], fields: list[str] = FARM_ACTIVITY_FIELDS) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def import_farm_activity_csv(conn, path: str, dry_run: bool = False) -> dict[str, Any]:
    rows = read_csv(path)
    errors: list[str] = []
    for index, row in enumerate(rows, start=2):
        errors.extend(validate_farm_activity_row(row, index))
    if errors:
        return {"inserted": 0, "errors": errors, "dry_run": dry_run}
    if dry_run:
        return {"inserted": 0, "validated": len(rows), "errors": [], "dry_run": True}

    cur = conn.cursor()
    inserted = 0
    for row in rows:
        cur.execute(
            """
            INSERT INTO farm_activity
                (location_id, plot_id, crop_cycle_id, activity_type, activity_date,
                 description, labor_hours, labor_cost, materials_used, notes,
                 status, source_system, source_id, source_raw)
            VALUES (%s, NULLIF(%s, '')::uuid, NULLIF(%s, '')::uuid, %s, %s::date,
                    %s, NULLIF(%s, '')::numeric, NULLIF(%s, '')::numeric,
                    NULLIF(%s, ''), NULLIF(%s, ''), 'draft', %s, %s, %s::jsonb)
            """,
            (
                row["location_id"], row.get("plot_id", ""), row.get("crop_cycle_id", ""),
                row["activity_type"], row["activity_date"], row["description"],
                row.get("labor_hours", ""), row.get("labor_cost", ""),
                row.get("materials_used", ""), row.get("notes", ""),
                row.get("source_system") or "spreadsheet_bridge",
                row.get("source_id") or None,
                json.dumps({"source": "spreadsheet_bridge", "row": row}),
            ),
        )
        inserted += 1
    conn.commit()
    cur.close()
    return {"inserted": inserted, "errors": [], "dry_run": False}


def validate_ebf_csv(path: str, template_type: str) -> dict[str, Any]:
    """Validate EBF CSV files without writing canonical records."""
    rows = read_csv(path)
    validator = validate_ebf_scorecard_row if template_type == "ebf_scorecard" else validate_ebf_evidence_row
    errors: list[str] = []
    for index, row in enumerate(rows, start=2):
        errors.extend(validator(row, index))
    return {"validated": 0 if errors else len(rows), "errors": errors, "template_type": template_type}


def export_farm_activity_csv(conn, path: str, location_id: str) -> dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT location_id, plot_id, crop_cycle_id, activity_type, activity_date,
               description, labor_hours, labor_cost, materials_used, notes,
               source_system, source_id
        FROM farm_activity
        WHERE location_id = %s AND status IN ('verified', 'published')
        ORDER BY activity_date DESC, created_at DESC
        """,
        (location_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    write_csv(path, rows)
    return {"exported": len(rows), "path": path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokonut CSV spreadsheet bridge")
    parser.add_argument("--template", help="Write farm_activity CSV template")
    parser.add_argument("--template-type", choices=["farm_activity", "ebf_scorecard", "ebf_evidence"], default="farm_activity", help="Template kind")
    parser.add_argument("--import-file", help="Import farm_activity CSV")
    parser.add_argument("--export-file", help="Export farm_activity CSV")
    parser.add_argument("--location-id", help="Location UUID for export")
    parser.add_argument("--dry-run", action="store_true", help="Validate import without writing")
    args = parser.parse_args()

    if args.template:
        if args.template_type == "ebf_scorecard":
            write_csv(args.template, ebf_scorecard_template_rows(), EBF_SCORECARD_FIELDS)
        elif args.template_type == "ebf_evidence":
            write_csv(args.template, ebf_evidence_template_rows(), EBF_EVIDENCE_FIELDS)
        else:
            write_csv(args.template, template_rows())
        print(json.dumps({"template": args.template}, indent=2))
        return

    if args.import_file:
        if args.template_type in {"ebf_scorecard", "ebf_evidence"}:
            print(json.dumps(validate_ebf_csv(args.import_file, args.template_type), indent=2))
            return
        conn = get_connection()
        try:
            print(json.dumps(import_farm_activity_csv(conn, args.import_file, dry_run=args.dry_run), indent=2))
        finally:
            conn.close()
        return

    if args.export_file:
        if not args.location_id:
            parser.error("--export-file requires --location-id")
        conn = get_connection()
        try:
            print(json.dumps(export_farm_activity_csv(conn, args.export_file, args.location_id), indent=2))
        finally:
            conn.close()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
