"""Snapshot storage, hashing, verification, and empty-check components."""

import hashlib
import json
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from .common import (
    _looks_like_uuid,
    attach_public_interest_context,
    build_negative_findings,
)


def compute_hash(data: dict) -> str:
    """Compute SHA-256 hash of report data for reproducibility."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def store_snapshot(
    conn, report_data: dict, location_id: str = None, period_start: str = None, period_end: str = None
) -> str:
    """Store an unfrozen draft report for independent review."""
    # The report_snapshot.location_id column is a UUID; network-level scopes
    # (e.g. "all" or a comma-joined multi-select) are stored as NULL.
    storage_location_id = location_id if _looks_like_uuid(location_id) else None
    report_data = attach_public_interest_context(conn, report_data, storage_location_id)
    snapshot_hash = compute_hash(report_data)
    report_type = report_data.get("report_type", "unknown")
    public_interest = report_data.get("public_interest", {})
    public_summary = "; ".join(public_interest.get("limitations", [])) if public_interest else None
    negative_findings = build_negative_findings(public_interest) if public_interest else []
    uncertainty_notes = (
        "Checks use available governed records and public-safe views; missing records do not prove absence. "
        + public_interest.get("signed_error_convention", "")
        if public_interest
        else None
    )
    affected_voice = json.dumps(public_interest.get("public_feedback", []), default=str) if public_interest else None

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO report_snapshot (
            report_name, report_type, location_id, period_start, period_end,
            report_data, snapshot_hash, status, frozen, frozen_at,
            public_interest_summary, uncertainty_notes, negative_findings, affected_community_voice
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft', FALSE, NULL, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            f"{report_type}_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            report_type,
            storage_location_id,
            period_start,
            period_end,
            json.dumps(report_data, default=str),
            snapshot_hash,
            public_summary,
            uncertainty_notes,
            json.dumps(negative_findings, default=str),
            affected_voice,
        ),
    )
    snapshot_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return snapshot_id


def list_snapshots(conn, location_id: str = None):
    """List existing report snapshots."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if location_id:
            cur.execute(
                "SELECT id, report_name, report_type, snapshot_hash, status, created_at FROM report_snapshot WHERE location_id = %s ORDER BY created_at DESC, id DESC LIMIT 20",
                (location_id,),
            )
        else:
            cur.execute(
                "SELECT id, report_name, report_type, snapshot_hash, status, created_at FROM report_snapshot ORDER BY created_at DESC, id DESC LIMIT 20"
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()


def _verify_snapshot(conn, snapshot_id_or_hash: str) -> None:
    """Verify a snapshot's hash integrity."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        "SELECT id, report_name, report_type, report_data, snapshot_hash, status FROM report_snapshot WHERE id = %s OR snapshot_hash = %s",
        (snapshot_id_or_hash, snapshot_id_or_hash),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        print(f"Snapshot not found: {snapshot_id_or_hash}")
        return

    stored_hash = row["snapshot_hash"]
    report_data = row["report_data"]

    recomputed = compute_hash(report_data)

    print(f"Snapshot:   {row['id']}")
    print(f"Report:     {row['report_name']} ({row['report_type']})")
    print(f"Status:     {row['status']}")
    print(f"Stored:     {stored_hash}")
    print(f"Recomputed: {recomputed}")

    if stored_hash == recomputed:
        print("Result:     PASS -- hash matches, report is intact")
    else:
        print("Result:     FAIL -- hash mismatch, report may have been tampered with")


def _check_report_empty(report_data: dict, report_type: str) -> None:
    """Warn if a report has no primary content rows."""
    content_keys = [
        k
        for k in report_data
        if k
        in {
            "plans",
            "risks",
            "milestones",
            "scenarios",
            "observations",
            "reviews",
            "policies",
            "protocols",
            "mechanisms",
            "experiments",
            "barriers",
            "stress_tests",
            "artifacts",
            "economics",
            "targets",
            "assessments",
            "outcomes",
            "mechanisms",
            "rows",
            "items",
            "farms",
            "crops",
            "pillars",
            "scores",
            "evidence_gaps",
            "recommendations",
            "cultural_context",
            "wellbeing_metrics",
            "participatory_actions",
            "financial_sustainability",
            "risk_mitigation",
        }
    ]
    for key in content_keys:
        value = report_data.get(key)
        if isinstance(value, list) and len(value) == 0:
            print(f"  ⚠ {report_type}: no rows in '{key}' — report may be empty")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
