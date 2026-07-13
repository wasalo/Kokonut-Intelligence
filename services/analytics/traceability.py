#!/usr/bin/env python3
"""
Supply Chain Traceability

Farm-to-fork tracking: produce batches, custody transfers, quality
inspections, certifications, provenance events, food safety checks,
and cold chain monitoring.

Usage:
    python -m services.analytics.traceability create-batch --location-id UUID --crop maize --quantity 500 --harvest-date 2026-07-10
    python -m services.analytics.traceability custody --batch-id UUID --from "Farm A" --to "Cooperative B" --type harvest_collection
    python -m services.analytics.traceability quality --batch-id UUID --type visual --result pass --grade A
    python -m services.analytics.traceability certification --batch-id UUID --type organic --cert-number ORG-001 --issuer KCB --expiry 2027-01-01
    python -m services.analytics.traceability provenance --batch-id UUID --event harvest --actor "Farmer John" --location "Adelphi"
    python -m services.analytics.traceability provenance-log --batch-id UUID
    python -m services.analytics.traceability status --batch-id UUID
    python -m services.analytics.traceability list --location-id UUID --status active
    python -m services.analytics.traceability food-safety --batch-id UUID --type temperature --result pass --temperature 4.2
    python -m services.analytics.traceability certs --location-id UUID
    python -m services.analytics.traceability trace-forward --batch-id UUID
    python -m services.analytics.traceability trace-backward --batch-id UUID
    python -m services.analytics.traceability cold-chain --batch-id UUID
"""

import argparse
import json
import uuid
from datetime import datetime, date, timezone
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.traceability")


# ============================================================
# Batch Creation
# ============================================================

def create_produce_batch(
    conn,
    location_id: str,
    crop_name: str,
    quantity: float,
    harvest_date: str = None,
    variety: str = None,
    organic: bool = False,
    unit: str = "kg",
    field_id: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Create a produce batch at harvest."""
    cur = conn.cursor()
    try:
        batch_id = str(uuid.uuid4())
        hd = harvest_date or date.today().isoformat()

        cur.execute(
            """
            INSERT INTO produce_batch
                (id, location_id, crop_name, variety, quantity, unit,
                 harvest_date, organic, field_id, notes, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'active')
            RETURNING id
            """,
            (
                batch_id, location_id, crop_name, variety, quantity, unit,
                hd, organic, field_id, notes, json.dumps(metadata or {}),
            ),
        )

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor, location, description, metadata)
            VALUES (%s, %s, 'batch_created', %s, %s, %s, %s::jsonb)
            """,
            (
                str(uuid.uuid4()), batch_id, f"system:{location_id[:8]}",
                location_id,
                f"Created produce batch: {quantity} {unit} of {crop_name}",
                json.dumps({"variety": variety, "organic": organic}),
            ),
        )

        conn.commit()
        logger.info("Created produce batch %s for %s", batch_id[:8], crop_name)
        return {
            "batch_id": batch_id,
            "location_id": location_id,
            "crop_name": crop_name,
            "variety": variety,
            "quantity": quantity,
            "unit": unit,
            "harvest_date": hd,
            "organic": organic,
            "status": "active",
        }
    finally:
        cur.close()


# ============================================================
# Custody Transfer
# ============================================================

def record_custody_transfer(
    conn,
    batch_id: str,
    from_actor: str,
    to_actor: str,
    transfer_type: str = "sale",
    location: str = None,
    quantity: float = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a custody transfer event."""
    cur = conn.cursor()
    try:
        transfer_id = str(uuid.uuid4())

        cur.execute(
            """
            SELECT quantity, unit FROM produce_batch WHERE id = %s
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Batch {batch_id} not found")
        batch_qty = float(row[0])
        batch_unit = row[1] or "kg"

        if quantity is None:
            quantity = batch_qty

        cur.execute(
            """
            INSERT INTO custody_transfer
                (id, batch_id, from_actor, to_actor, transfer_type,
                 location, quantity, unit, notes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                transfer_id, batch_id, from_actor, to_actor, transfer_type,
                location, quantity, batch_unit, notes, json.dumps(metadata or {}),
            ),
        )

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor, location, description, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                str(uuid.uuid4()), batch_id, f"custody_{transfer_type}",
                from_actor, location or to_actor,
                f"Transfer from {from_actor} to {to_actor} ({transfer_type})",
                json.dumps({"transfer_id": transfer_id, "quantity": quantity, "unit": batch_unit}),
            ),
        )

        conn.commit()
        logger.info("Recorded custody transfer %s for batch %s", transfer_id[:8], batch_id[:8])
        return {
            "transfer_id": transfer_id,
            "batch_id": batch_id,
            "from_actor": from_actor,
            "to_actor": to_actor,
            "transfer_type": transfer_type,
            "quantity": quantity,
            "unit": batch_unit,
            "location": location,
        }
    finally:
        cur.close()


# ============================================================
# Quality Inspection
# ============================================================

def record_quality_inspection(
    conn,
    batch_id: str,
    inspection_type: str,
    result: str,
    grade: str = None,
    inspector: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a quality inspection event."""
    cur = conn.cursor()
    try:
        inspection_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO quality_inspection
                (id, batch_id, inspection_type, result, grade,
                 inspector, notes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                inspection_id, batch_id, inspection_type, result, grade,
                inspector, notes, json.dumps(metadata or {}),
            ),
        )

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor, location, description, metadata)
            VALUES (%s, %s, 'quality_inspection', %s, NULL, %s, %s::jsonb)
            """,
            (
                str(uuid.uuid4()), batch_id, inspector or "system",
                f"Quality inspection ({inspection_type}): {result} grade={grade or 'N/A'}",
                json.dumps({"inspection_id": inspection_id}),
            ),
        )

        conn.commit()
        logger.info("Recorded quality inspection %s for batch %s", inspection_id[:8], batch_id[:8])
        return {
            "inspection_id": inspection_id,
            "batch_id": batch_id,
            "inspection_type": inspection_type,
            "result": result,
            "grade": grade,
            "inspector": inspector,
        }
    finally:
        cur.close()


# ============================================================
# Certification Verification
# ============================================================

def verify_certification(
    conn,
    batch_id: str,
    cert_type: str,
    cert_number: str,
    issuer: str,
    expiry_date: str = None,
    verified: bool = True,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Verify a certification for a produce batch."""
    cur = conn.cursor()
    try:
        cert_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO certification_record
                (id, batch_id, cert_type, cert_number, issuer,
                 expiry_date, verified, notes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                cert_id, batch_id, cert_type, cert_number, issuer,
                expiry_date, verified, notes, json.dumps(metadata or {}),
            ),
        )

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor, location, description, metadata)
            VALUES (%s, %s, 'certification_verified', %s, NULL, %s, %s::jsonb)
            """,
            (
                str(uuid.uuid4()), batch_id, issuer,
                f"Certification verified: {cert_type} #{cert_number}",
                json.dumps({"cert_id": cert_id, "expiry": expiry_date}),
            ),
        )

        conn.commit()
        logger.info("Verified certification %s for batch %s", cert_id[:8], batch_id[:8])
        return {
            "cert_id": cert_id,
            "batch_id": batch_id,
            "cert_type": cert_type,
            "cert_number": cert_number,
            "issuer": issuer,
            "expiry_date": expiry_date,
            "verified": verified,
        }
    finally:
        cur.close()


# ============================================================
# Provenance Event
# ============================================================

def log_provenance_event(
    conn,
    batch_id: str,
    event_type: str,
    actor: str,
    location: str = None,
    description: str = None,
    evidence_url: str = None,
    metadata: dict = None,
) -> dict:
    """Log an immutable provenance event for a batch."""
    cur = conn.cursor()
    try:
        event_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor, location,
                 description, evidence_url, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                event_id, batch_id, event_type, actor, location,
                description, evidence_url, json.dumps(metadata or {}),
            ),
        )

        conn.commit()
        logger.info("Logged provenance event %s for batch %s", event_id[:8], batch_id[:8])
        return {
            "event_id": event_id,
            "batch_id": batch_id,
            "event_type": event_type,
            "actor": actor,
            "location": location,
            "description": description,
            "evidence_url": evidence_url,
        }
    finally:
        cur.close()


# ============================================================
# Provenance Chain
# ============================================================

def get_batch_provenance(conn, batch_id: str) -> dict:
    """Get the full provenance chain for a batch."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, batch_id, event_type, actor, location,
                   description, evidence_url, metadata, created_at
            FROM provenance_event
            WHERE batch_id = %s
            ORDER BY created_at ASC
            """,
            (batch_id,),
        )
        cols = [d[0] for d in cur.description]
        events = [dict(zip(cols, row)) for row in cur.fetchall()]

        cur.execute(
            """
            SELECT id, crop_name, variety, quantity, unit,
                   harvest_date, organic, status
            FROM produce_batch WHERE id = %s
            """,
            (batch_id,),
        )
        batch_row = cur.fetchone()
        batch_info = None
        if batch_row:
            bcols = [d[0] for d in cur.description]
            batch_info = dict(zip(bcols, batch_row))

        return {
            "batch_id": batch_id,
            "batch": batch_info,
            "event_count": len(events),
            "events": events,
        }
    finally:
        cur.close()


# ============================================================
# Batch Status
# ============================================================

def get_batch_status(conn, batch_id: str) -> dict:
    """Get current batch status, location, and custody chain."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, location_id, crop_name, variety, quantity, unit,
                   harvest_date, organic, status, created_at
            FROM produce_batch WHERE id = %s
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"error": f"Batch {batch_id} not found"}

        cols = [d[0] for d in cur.description]
        batch = dict(zip(cols, row))

        cur.execute(
            """
            SELECT to_actor, transfer_type, quantity, location, created_at
            FROM custody_transfer
            WHERE batch_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (batch_id,),
        )
        ct_row = cur.fetchone()
        current_holder = None
        if ct_row:
            current_holder = ct_row[0]

        cur.execute(
            """
            SELECT COUNT(*) FROM provenance_event WHERE batch_id = %s
            """,
            (batch_id,),
        )
        event_count = cur.fetchone()[0]

        return {
            "batch_id": batch_id,
            "crop_name": batch["crop_name"],
            "variety": batch["variety"],
            "quantity": batch["quantity"],
            "unit": batch["unit"],
            "harvest_date": batch["harvest_date"].isoformat() if batch["harvest_date"] else None,
            "organic": batch["organic"],
            "status": batch["status"],
            "current_holder": current_holder,
            "event_count": event_count,
            "created_at": batch["created_at"].isoformat() if batch["created_at"] else None,
        }
    finally:
        cur.close()


# ============================================================
# List Batches
# ============================================================

def list_batches(
    conn,
    location_id: str = None,
    status: str = None,
    limit: int = 50,
) -> list:
    """List batches, optionally filtered by location and status."""
    cur = conn.cursor()
    try:
        where = "1=1"
        params = []
        if location_id:
            where += " AND location_id = %s"
            params.append(location_id)
        if status:
            where += " AND status = %s"
            params.append(status)

        cur.execute(
            f"""
            SELECT id, location_id, crop_name, variety, quantity, unit,
                   harvest_date, organic, status, created_at
            FROM produce_batch
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (*params, limit),
        )
        cols = [d[0] for d in cur.description]
        batches = [dict(zip(cols, row)) for row in cur.fetchall()]

        return {
            "count": len(batches),
            "batches": batches,
        }
    finally:
        cur.close()


# ============================================================
# Food Safety
# ============================================================

def record_food_safety(
    conn,
    batch_id: str,
    check_type: str,
    result: str,
    temperature: float = None,
    inspector: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a food safety check event."""
    cur = conn.cursor()
    try:
        check_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO food_safety_check
                (id, batch_id, check_type, result, temperature,
                 inspector, notes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                check_id, batch_id, check_type, result, temperature,
                inspector, notes, json.dumps(metadata or {}),
            ),
        )

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor, location, description, metadata)
            VALUES (%s, %s, 'food_safety_check', %s, NULL, %s, %s::jsonb)
            """,
            (
                str(uuid.uuid4()), batch_id, inspector or "system",
                f"Food safety check ({check_type}): {result}",
                json.dumps({"check_id": check_id, "temperature": temperature}),
            ),
        )

        conn.commit()
        logger.info("Recorded food safety check %s for batch %s", check_id[:8], batch_id[:8])
        return {
            "check_id": check_id,
            "batch_id": batch_id,
            "check_type": check_type,
            "result": result,
            "temperature": temperature,
            "inspector": inspector,
        }
    finally:
        cur.close()


# ============================================================
# Certification Status
# ============================================================

def get_certification_status(conn, location_id: str) -> dict:
    """Get active certifications for a location."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT cr.id, cr.batch_id, cr.cert_type, cr.cert_number,
                   cr.issuer, cr.expiry_date, cr.verified,
                   pb.crop_name, pb.quantity, pb.unit
            FROM certification_record cr
            JOIN produce_batch pb ON pb.id = cr.batch_id
            WHERE pb.location_id = %s AND cr.verified = TRUE
            ORDER BY cr.expiry_date DESC
            """,
            (location_id,),
        )
        cols = [d[0] for d in cur.description]
        certs = [dict(zip(cols, row)) for row in cur.fetchall()]

        today = date.today()
        active = []
        expiring_soon = []
        expired = []
        for c in certs:
            entry = dict(c)
            if entry.get("expiry_date"):
                entry["expiry_date"] = entry["expiry_date"].isoformat() if hasattr(entry["expiry_date"], "isoformat") else str(entry["expiry_date"])
            if entry.get("verified") is not None:
                entry["verified"] = bool(entry["verified"])
            if c.get("expiry_date") and c["expiry_date"] < today:
                expired.append(entry)
            elif c.get("expiry_date") and (c["expiry_date"] - today).days < 90:
                expiring_soon.append(entry)
            else:
                active.append(entry)

        return {
            "location_id": location_id,
            "total": len(certs),
            "active": active,
            "expiring_soon": expiring_soon,
            "expired": expired,
        }
    finally:
        cur.close()


# ============================================================
# Trace Forward
# ============================================================

def trace_forward(conn, batch_id: str) -> dict:
    """Trace from a batch to all downstream recipients."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, crop_name, quantity, unit, status
            FROM produce_batch WHERE id = %s
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"error": f"Batch {batch_id} not found"}

        cur.execute(
            """
            SELECT to_actor, transfer_type, quantity, location,
                   created_at, notes
            FROM custody_transfer
            WHERE batch_id = %s
            ORDER BY created_at ASC
            """,
            (batch_id,),
        )
        cols = [d[0] for d in cur.description]
        transfers = [dict(zip(cols, row)) for row in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT batch_id FROM custody_transfer
            WHERE batch_id IN (
                SELECT DISTINCT batch_id FROM custody_transfer
                WHERE batch_id = %s
            )
            """,
            (batch_id,),
        )

        return {
            "batch_id": batch_id,
            "crop_name": row[1],
            "original_quantity": row[2],
            "unit": row[3],
            "transfer_count": len(transfers),
            "downstream_chain": transfers,
        }
    finally:
        cur.close()


# ============================================================
# Trace Backward
# ============================================================

def trace_backward(conn, batch_id: str) -> dict:
    """Trace from a batch back to the origin farm."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, location_id, crop_name, quantity, unit,
                   harvest_date, organic, status
            FROM produce_batch WHERE id = %s
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"error": f"Batch {batch_id} not found"}

        cols = [d[0] for d in cur.description]
        batch = dict(zip(cols, row))

        cur.execute(
            """
            SELECT from_actor, transfer_type, quantity, location,
                   created_at, notes
            FROM custody_transfer
            WHERE batch_id = %s
            ORDER BY created_at ASC
            """,
            (batch_id,),
        )
        tcols = [d[0] for d in cur.description]
        transfers = [dict(zip(tcols, trow)) for trow in cur.fetchall()]

        cur.execute(
            """
            SELECT event_type, actor, location, description,
                   evidence_url, created_at
            FROM provenance_event
            WHERE batch_id = %s
            ORDER BY created_at ASC
            """,
            (batch_id,),
        )
        pcols = [d[0] for d in cur.description]
        provenance = [dict(zip(pcols, prow)) for prow in cur.fetchall()]

        origin_farm = batch.get("location_id")
        first_handler = transfers[0]["from_actor"] if transfers else None

        return {
            "batch_id": batch_id,
            "crop_name": batch["crop_name"],
            "quantity": batch["quantity"],
            "unit": batch["unit"],
            "harvest_date": batch["harvest_date"].isoformat() if batch["harvest_date"] else None,
            "organic": batch["organic"],
            "origin_location_id": origin_farm,
            "first_handler": first_handler,
            "upstream_chain": transfers,
            "provenance_events": provenance,
        }
    finally:
        cur.close()


# ============================================================
# Cold Chain Log
# ============================================================

def get_cold_chain_log(conn, batch_id: str) -> dict:
    """Get temperature monitoring log for a batch."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, check_type, result, temperature,
                   inspector, notes, metadata, created_at
            FROM food_safety_check
            WHERE batch_id = %s AND check_type IN ('temperature', 'cold_chain')
            ORDER BY created_at ASC
            """,
            (batch_id,),
        )
        cols = [d[0] for d in cur.description]
        logs = [dict(zip(cols, row)) for row in cur.fetchall()]

        temps = [float(l["temperature"]) for l in logs if l.get("temperature") is not None]

        stats = {}
        if temps:
            stats = {
                "min_temp": round(min(temps), 2),
                "max_temp": round(max(temps), 2),
                "avg_temp": round(sum(temps) / len(temps), 2),
                "readings": len(temps),
            }

        return {
            "batch_id": batch_id,
            "total_checks": len(logs),
            "temperature_stats": stats,
            "logs": logs,
        }
    finally:
        cur.close()


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Supply chain traceability")
    sub = parser.add_subparsers(dest="command")

    # create-batch
    cb = sub.add_parser("create-batch", help="Create produce batch")
    cb.add_argument("--location-id", required=True)
    cb.add_argument("--crop", required=True, help="Crop name")
    cb.add_argument("--quantity", type=float, required=True)
    cb.add_argument("--harvest-date", help="Harvest date YYYY-MM-DD")
    cb.add_argument("--variety")
    cb.add_argument("--organic", action="store_true")
    cb.add_argument("--unit", default="kg")
    cb.add_argument("--field-id")
    cb.add_argument("--notes")
    cb.add_argument("--json", action="store_true")

    # custody
    ct = sub.add_parser("custody", help="Record custody transfer")
    ct.add_argument("--batch-id", required=True)
    ct.add_argument("--from", dest="from_actor", required=True)
    ct.add_argument("--to", dest="to_actor", required=True)
    ct.add_argument("--type", dest="transfer_type", default="sale")
    ct.add_argument("--location")
    ct.add_argument("--quantity", type=float)
    ct.add_argument("--notes")
    ct.add_argument("--json", action="store_true")

    # quality
    qi = sub.add_parser("quality", help="Record quality inspection")
    qi.add_argument("--batch-id", required=True)
    qi.add_argument("--type", dest="inspection_type", required=True)
    qi.add_argument("--result", required=True)
    qi.add_argument("--grade")
    qi.add_argument("--inspector")
    qi.add_argument("--notes")
    qi.add_argument("--json", action="store_true")

    # certification
    cf = sub.add_parser("certification", help="Verify certification")
    cf.add_argument("--batch-id", required=True)
    cf.add_argument("--type", dest="cert_type", required=True)
    cf.add_argument("--cert-number", required=True)
    cf.add_argument("--issuer", required=True)
    cf.add_argument("--expiry", help="Expiry date YYYY-MM-DD")
    cf.add_argument("--notes")
    cf.add_argument("--json", action="store_true")

    # provenance
    pv = sub.add_parser("provenance", help="Log provenance event")
    pv.add_argument("--batch-id", required=True)
    pv.add_argument("--event", dest="event_type", required=True)
    pv.add_argument("--actor", required=True)
    pv.add_argument("--location")
    pv.add_argument("--description")
    pv.add_argument("--evidence-url")
    pv.add_argument("--json", action="store_true")

    # provenance-log
    pl = sub.add_parser("provenance-log", help="Get provenance chain")
    pl.add_argument("--batch-id", required=True)
    pl.add_argument("--json", action="store_true")

    # status
    st = sub.add_parser("status", help="Get batch status")
    st.add_argument("--batch-id", required=True)
    st.add_argument("--json", action="store_true")

    # list
    ls = sub.add_parser("list", help="List batches")
    ls.add_argument("--location-id")
    ls.add_argument("--status")
    ls.add_argument("--limit", type=int, default=50)
    ls.add_argument("--json", action="store_true")

    # food-safety
    fs = sub.add_parser("food-safety", help="Record food safety check")
    fs.add_argument("--batch-id", required=True)
    fs.add_argument("--type", dest="check_type", required=True)
    fs.add_argument("--result", required=True)
    fs.add_argument("--temperature", type=float)
    fs.add_argument("--inspector")
    fs.add_argument("--notes")
    fs.add_argument("--json", action="store_true")

    # certs
    cs = sub.add_parser("certs", help="Get certification status")
    cs.add_argument("--location-id", required=True)
    cs.add_argument("--json", action="store_true")

    # trace-forward
    tf = sub.add_parser("trace-forward", help="Trace downstream")
    tf.add_argument("--batch-id", required=True)
    tf.add_argument("--json", action="store_true")

    # trace-backward
    tb = sub.add_parser("trace-backward", help="Trace to origin")
    tb.add_argument("--batch-id", required=True)
    tb.add_argument("--json", action="store_true")

    # cold-chain
    cc = sub.add_parser("cold-chain", help="Get cold chain log")
    cc.add_argument("--batch-id", required=True)
    cc.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from .base import get_db

    if args.command in (
        "create-batch", "custody", "quality", "certification",
        "provenance", "provenance-log", "status", "list",
        "food-safety", "certs", "trace-forward", "trace-backward",
        "cold-chain",
    ):
        db = get_db()
    else:
        parser.print_help()
        return

    try:
        if args.command == "create-batch":
            result = create_produce_batch(
                db, args.location_id, args.crop, args.quantity,
                harvest_date=args.harvest_date, variety=args.variety,
                organic=args.organic, unit=args.unit,
                field_id=args.field_id, notes=args.notes,
            )
        elif args.command == "custody":
            result = record_custody_transfer(
                db, args.batch_id, args.from_actor, args.to_actor,
                transfer_type=args.transfer_type, location=args.location,
                quantity=args.quantity, notes=args.notes,
            )
        elif args.command == "quality":
            result = record_quality_inspection(
                db, args.batch_id, args.inspection_type, args.result,
                grade=args.grade, inspector=args.inspector, notes=args.notes,
            )
        elif args.command == "certification":
            result = verify_certification(
                db, args.batch_id, args.cert_type, args.cert_number,
                args.issuer, expiry_date=args.expiry, notes=args.notes,
            )
        elif args.command == "provenance":
            result = log_provenance_event(
                db, args.batch_id, args.event_type, args.actor,
                location=args.location, description=args.description,
                evidence_url=args.evidence_url,
            )
        elif args.command == "provenance-log":
            result = get_batch_provenance(db, args.batch_id)
        elif args.command == "status":
            result = get_batch_status(db, args.batch_id)
        elif args.command == "list":
            result = list_batches(
                db, location_id=args.location_id,
                status=args.status, limit=args.limit,
            )
        elif args.command == "food-safety":
            result = record_food_safety(
                db, args.batch_id, args.check_type, args.result,
                temperature=args.temperature, inspector=args.inspector,
                notes=args.notes,
            )
        elif args.command == "certs":
            result = get_certification_status(db, args.location_id)
        elif args.command == "trace-forward":
            result = trace_forward(db, args.batch_id)
        elif args.command == "trace-backward":
            result = trace_backward(db, args.batch_id)
        elif args.command == "cold-chain":
            result = get_cold_chain_log(db, args.batch_id)

        print(json.dumps(result, indent=2, default=str))

    finally:
        db.close()


if __name__ == "__main__":
    main()
