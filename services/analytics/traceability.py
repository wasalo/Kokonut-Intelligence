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

import json
import uuid
from datetime import date

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
        batch_number = f"PB-{batch_id}"
        hd = harvest_date or date.today().isoformat()

        cur.execute(
            """
            INSERT INTO produce_batch
                (id, location_id, batch_number, crop_name, variety, quantity_kg,
                 quantity_unit, harvest_date, organic, origin_plot_id, notes, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'active')
            RETURNING id
            """,
            (
                batch_id, location_id, batch_number, crop_name, variety, quantity, unit,
                hd, organic, field_id, notes, json.dumps(metadata or {}),
            ),
        )

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor_name, location_name, description, data)
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
    except Exception:
        conn.rollback()
        raise
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
            SELECT quantity_kg, quantity_unit FROM produce_batch WHERE id = %s
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

        cur.execute("SELECT COALESCE(MAX(sequence_num), 0) + 1 FROM chain_of_custody WHERE batch_id = %s", (batch_id,))
        sequence_num = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO chain_of_custody
                (id, batch_id, sequence_num, from_actor_name, from_actor_type,
                 to_actor_name, to_actor_type, quantity_kg, quantity_unit,
                 transfer_method, notes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                transfer_id, batch_id, sequence_num, from_actor, "sender",
                to_actor, "recipient", quantity, batch_unit, transfer_type,
                notes, json.dumps({**(metadata or {}), "location": location}),
            ),
        )

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor_name, location_name, description, data)
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
    except Exception:
        conn.rollback()
        raise
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
                (id, batch_id, inspection_point, overall_grade, inspector_name,
                 passed, notes, metadata)
            VALUES (%s, %s, 'harvest', %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                inspection_id, batch_id, grade, inspector, result.lower() in ("pass", "passed"),
                notes, json.dumps({**(metadata or {}), "inspection_type": inspection_type, "result": result}),
            ),
        )

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor_name, description, data)
            VALUES (%s, %s, 'quality_inspection', %s, %s, %s::jsonb)
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
    except Exception:
        conn.rollback()
        raise
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

        cur.execute("SELECT location_id FROM produce_batch WHERE id = %s", (batch_id,))
        batch = cur.fetchone()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        cur.execute("SELECT id FROM certification_type WHERE name = %s OR category = %s ORDER BY name LIMIT 1", (cert_type, cert_type))
        cert_type_row = cur.fetchone()
        if not cert_type_row:
            raise ValueError(f"Certification type {cert_type} not found")

        cur.execute(
            """
            INSERT INTO certification_verify
                (id, location_id, certification_type_id, batch_id, certificate_number,
                 issuing_body, issued_date, expiry_date, verified, verified_at,
                 status, notes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s THEN NOW() ELSE NULL END, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                cert_id, batch[0], cert_type_row[0], batch_id, cert_number, issuer,
                date.today().isoformat(), expiry_date, verified, verified,
                "verified" if verified else "pending", notes, json.dumps(metadata or {}),
            ),
        )

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor_name, description, data)
            VALUES (%s, %s, 'certification_verified', %s, %s, %s::jsonb)
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
    except Exception:
        conn.rollback()
        raise
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
                (id, batch_id, event_type, actor_name, location_name,
                 description, evidence_urls, data)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            RETURNING id
            """,
            (
                event_id, batch_id, event_type, actor, location,
                description, json.dumps([evidence_url] if evidence_url else []), json.dumps(metadata or {}),
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
    except Exception:
        conn.rollback()
        raise
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
            SELECT id, batch_id, event_type, actor_name AS actor,
                   location_name AS location, description,
                   evidence_urls, data AS metadata, event_time AS created_at
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
            SELECT id, crop_name, variety, quantity_kg AS quantity,
                   quantity_unit AS unit,
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
            SELECT id, location_id, crop_name, variety, quantity_kg AS quantity,
                   quantity_unit AS unit,
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
            SELECT to_actor_name, transfer_method, quantity_kg, metadata, transfer_date
            FROM chain_of_custody
            WHERE batch_id = %s
            ORDER BY sequence_num DESC
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
            SELECT id, location_id, crop_name, variety, quantity_kg AS quantity,
                   quantity_unit AS unit,
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
            INSERT INTO food_safety_record
                (id, batch_id, record_type, recorded_by, temperature_c,
                 passed, notes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                check_id, batch_id,
                "temperature_log" if check_type in ("temperature", "cold_chain") else check_type,
                inspector, temperature, result.lower() in ("pass", "passed"),
                notes, json.dumps({**(metadata or {}), "result": result}),
            ),
        )

        cur.execute(
            """
            INSERT INTO provenance_event
                (id, batch_id, event_type, actor_name, description, data)
            VALUES (%s, %s, 'food_safety_check', %s, %s, %s::jsonb)
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
    except Exception:
        conn.rollback()
        raise
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
            SELECT cv.id, cv.batch_id, ct.name AS cert_type,
                   cv.certificate_number AS cert_number,
                   cv.issuing_body AS issuer, cv.expiry_date, cv.verified,
                   pb.crop_name, pb.quantity_kg AS quantity,
                   pb.quantity_unit AS unit
            FROM certification_verify cv
            JOIN certification_type ct ON ct.id = cv.certification_type_id
            LEFT JOIN produce_batch pb ON pb.id = cv.batch_id
            WHERE cv.location_id = %s AND cv.verified = TRUE
            ORDER BY cv.expiry_date DESC
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
            SELECT id, crop_name, quantity_kg, quantity_unit, status
            FROM produce_batch WHERE id = %s
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"error": f"Batch {batch_id} not found"}

        cur.execute(
            """
            SELECT to_actor_name AS to_actor, transfer_method AS transfer_type,
                   quantity_kg AS quantity, metadata AS location,
                   transfer_date AS created_at, notes
            FROM chain_of_custody
            WHERE batch_id = %s
            ORDER BY sequence_num ASC
            """,
            (batch_id,),
        )
        cols = [d[0] for d in cur.description]
        transfers = [dict(zip(cols, row)) for row in cur.fetchall()]

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
            SELECT id, location_id, crop_name, quantity_kg AS quantity,
                   quantity_unit AS unit,
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
            SELECT from_actor_name AS from_actor, transfer_method AS transfer_type,
                   quantity_kg AS quantity, metadata AS location,
                   transfer_date AS created_at, notes
            FROM chain_of_custody
            WHERE batch_id = %s
            ORDER BY sequence_num ASC
            """,
            (batch_id,),
        )
        tcols = [d[0] for d in cur.description]
        transfers = [dict(zip(tcols, trow)) for trow in cur.fetchall()]

        cur.execute(
            """
            SELECT event_type, actor_name AS actor, location_name AS location,
                   description, evidence_urls, event_time AS created_at
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
            SELECT id, record_type AS check_type,
                   CASE WHEN passed THEN 'pass' ELSE 'fail' END AS result,
                   temperature_c AS temperature, recorded_by AS inspector,
                   notes, metadata, record_time AS created_at
            FROM food_safety_record
            WHERE batch_id = %s AND record_type = 'temperature_log'
            ORDER BY record_time ASC
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
