"""Pin / dependency graph — the chess "pin" tactic for governed state.

A *pin* in chess inhibits a piece from moving because doing so would expose a
more valuable piece behind it. On the platform, a governed record is "pinned"
when it cannot advance to a published/verified state because an upstream record
it depends on is not yet verified. Publishing the upstream while the downstream
is exposed would be unsafe or invalid.

This module maps those publish-blocks as pins: each entry names the pinned
(downstream) record, the pinning (upstream) record, and the gate that holds it.
It is READ-ONLY by default; ``propose_pin_blocks`` writes DRAFT rows to
``tactical_opportunity`` (status forced to 'draft'; human review required).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _jsonb(obj: Any) -> Any:
    import json as _json

    return _json.dumps(obj)


def detect_pin_blocks(conn, location_id: Optional[str] = None) -> Dict[str, Any]:
    """Find governed records pinned by an unverified upstream (read-only).

    Covers the canonical publish gates documented in AGENTS.md / safety.py:
      * metric_value not verified  -> blocks public metric views
      * farm_registry_record not verified/published -> blocks public data_stream
      * climate_impact_summary not verified/published -> blocks credit issuance
      * credit_retirement not verified -> blocks retirement_certificate issuance
    """
    pins: List[Dict[str, Any]] = []
    params: List[Any] = []
    loc_filter = ""
    if location_id:
        loc_filter = " AND location_id = %s"
        params.append(location_id)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # metric_value pinned (not verified) -> blocks public view
        cur.execute(
            f"""
            SELECT id, location_id, metric_id, computed_at
            FROM metric_value
            WHERE verified = FALSE {loc_filter}
            LIMIT 500
            """,
            list(params),
        )
        for row in cur.fetchall():
            pins.append(_pin(
                downstream="metric_value", downstream_id=str(row["id"]),
                upstream="metric_value.verified", gate="public_metric_view",
                location_id=str(row["location_id"]),
                summary="Unverified metric_value pins the public metric summary view.",
            ))

        # farm_registry_record not verified/published -> blocks public data_stream
        if not location_id:
            params2: List[Any] = []
            loc2 = ""
        else:
            params2 = [location_id]
            loc2 = " AND location_id = %s"
        cur.execute(
            f"""
            SELECT id, location_id, status
            FROM farm_registry_record
            WHERE status NOT IN ('verified', 'published') {loc2}
            LIMIT 500
            """,
            params2,
        )
        for row in cur.fetchall():
            pins.append(_pin(
                downstream="farm_registry_record", downstream_id=str(row["id"]),
                upstream="farm_registry_record.status", gate="public_data_stream",
                location_id=str(row["location_id"]),
                summary=f"farm_registry_record in '{row['status']}' pins public data_stream visibility.",
            ))

        # climate_impact_summary not verified/published -> blocks credit issuance
        cur.execute(
            f"""
            SELECT id, location_id, status
            FROM climate_impact_summary
            WHERE status NOT IN ('verified', 'published') {loc_filter}
            LIMIT 500
            """,
            list(params),
        )
        for row in cur.fetchall():
            pins.append(_pin(
                downstream="climate_impact_summary", downstream_id=str(row["id"]),
                upstream="climate_impact_summary.status", gate="credit_issuance",
                location_id=str(row["location_id"]),
                summary=f"climate_impact_summary in '{row['status']}' pins carbon credit issuance.",
            ))

        # credit_retirement not verified -> blocks certificate issuance
        cur.execute(
            f"""
            SELECT id, location_id, status
            FROM credit_retirement
            WHERE status NOT IN ('verified', 'published') {loc_filter}
            LIMIT 500
            """,
            list(params),
        )
        for row in cur.fetchall():
            pins.append(_pin(
                downstream="credit_retirement", downstream_id=str(row["id"]),
                upstream="credit_retirement.status", gate="certificate_issuance",
                location_id=str(row["location_id"]),
                summary=f"credit_retirement in '{row['status']}' pins retirement_certificate issuance.",
            ))

    severity = "high" if len(pins) > 20 else ("medium" if len(pins) > 5 else "low")
    return {
        "location_id": location_id,
        "pin_count": len(pins),
        "pins": pins,
        "severity": severity,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Pins are read-only detections of publish-blocked governed records. "
            "Use propose_pin_blocks to surface DRAFT tactical items for review."
        ),
    }


def _pin(
    downstream: str, downstream_id: str, upstream: str, gate: str,
    location_id: Optional[str], summary: str,
) -> Dict[str, Any]:
    return {
        "status": "draft",
        "downstream": downstream,
        "downstream_id": downstream_id,
        "pinning_upstream": upstream,
        "gate": gate,
        "location_id": location_id,
        "summary": summary,
        "requires_human_approval": True,
    }


def propose_pin_blocks(
    conn, location_id: Optional[str] = None, actor: Optional[str] = None
) -> Dict[str, Any]:
    """Write DRAFT tactical_opportunity rows for detected pin blocks.

    Status forced to 'draft' in code; no autonomous publish or state change.
    """
    detection = detect_pin_blocks(conn, location_id=location_id)
    created = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for pin in detection["pins"]:
            opp_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO tactical_opportunity
                    (id, opportunity_type, location_id, severity,
                     opportunity_summary, source_refs, status, proposed_by)
                VALUES (%s, 'pin', %s, %s, %s, %s, 'draft', %s)
                RETURNING *
                """,
                (
                    opp_id,
                    pin.get("location_id"),
                    detection["severity"],
                    pin["summary"],
                    _jsonb({
                        "downstream": pin["downstream"],
                        "downstream_id": pin["downstream_id"],
                        "gate": pin["gate"],
                    }),
                    actor,
                ),
            )
            created.append(dict(cur.fetchone()))
    conn.commit()
    return {
        "location_id": location_id,
        "proposed_count": len(created),
        "opportunities": created,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "DRAFT opportunities created; human review required to act.",
    }
