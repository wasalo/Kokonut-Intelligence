"""Sampling protocol management for soil and other field sampling."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("analytics.sampling_protocol")


def create_sampling_protocol(
    conn,
    location_id: str,
    protocol_key: str,
    title: str,
    domain: str,
    version: str,
    sampling_design: str = None,
    sub_sample_count: int = 5,
    target_depth_cm: float = None,
    depth_layer: str = None,
    collection_method: str = None,
    equipment_specification: str = None,
    required_analyses: List[str] = None,
    analytical_method: str = None,
    lab_accreditation_required: str = None,
    monitoring_frequency: str = None,
    **kwargs,
) -> str:
    """Create a new sampling protocol."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sampling_protocol (
            location_id, protocol_key, title, domain, version,
            sampling_design, sub_sample_count, target_depth_cm, depth_layer,
            collection_method, equipment_specification,
            required_analyses, analytical_method, lab_accreditation_required,
            monitoring_frequency, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')
        ON CONFLICT (location_id, protocol_key) DO UPDATE SET
            title = EXCLUDED.title, domain = EXCLUDED.domain, version = EXCLUDED.version,
            updated_at = NOW()
        RETURNING id
    """, (
        location_id, protocol_key, title, domain, version,
        sampling_design, sub_sample_count, target_depth_cm, depth_layer,
        collection_method, equipment_specification,
        required_analyses or [], analytical_method, lab_accreditation_required,
        monitoring_frequency,
    ))
    protocol_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Created sampling protocol: %s (domain=%s, v%s)", protocol_key, domain, version)
    return protocol_id


def validate_sample_compliance(conn, sample_id: str) -> Dict[str, Any]:
    """Check a soil sample against its sampling protocol for compliance."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM soil_sample WHERE id = %s", (sample_id,))
    sample = cur.fetchone()
    if not sample:
        cur.close()
        return {"status": "error", "message": "Sample not found"}

    sample = dict(sample)
    protocol_id = sample.get("protocol_id")
    if not protocol_id:
        cur.close()
        return {"status": "no_protocol", "message": "No protocol linked to this sample"}

    cur.execute("SELECT * FROM sampling_protocol WHERE id = %s", (protocol_id,))
    protocol = cur.fetchone()
    if not protocol:
        cur.close()
        return {"status": "error", "message": "Protocol not found"}

    protocol = dict(protocol)
    issues = []

    # Check required analyses
    required = set(protocol.get("required_analyses", []) or [])
    provided = set()
    for field in ["ph", "organic_matter_pct", "nitrogen_ppm", "phosphorus_ppm", "potassium_ppm", "cec", "texture"]:
        if sample.get(field) is not None:
            provided.add(field)

    missing = required - provided
    if missing:
        issues.append(f"Missing analyses: {', '.join(missing)}")

    # Check GPS
    if protocol.get("collection_method") in ("stratified_random", "systematic_grid") and not sample.get("gps_latitude"):
        issues.append("GPS coordinates required for this sampling design")

    # Check chain of custody
    if protocol.get("chain_of_custody_required", True) and not sample.get("chain_of_custody"):
        issues.append("Chain of custody required but not provided")

    # Check lab accreditation
    if protocol.get("lab_accreditation_required") and not sample.get("lab_accredited"):
        issues.append(f"Lab accreditation required: {protocol['lab_accreditation_required']}")

    # Check sample mass
    if protocol.get("minimum_sample_mass_g") and sample.get("sample_mass_g"):
        if sample["sample_mass_g"] < protocol["minimum_sample_mass_g"]:
            issues.append(f"Sample mass {sample['sample_mass_g']}g below minimum {protocol['minimum_sample_mass_g']}g")

    cur.close()

    compliant = len(issues) == 0
    return {
        "sample_id": sample_id,
        "protocol_id": str(protocol_id),
        "compliant": compliant,
        "issues": issues,
        "issue_count": len(issues),
    }


def get_protocol_for_location(conn, location_id: str, domain: str) -> Optional[Dict[str, Any]]:
    """Get the active sampling protocol for a location and domain."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM sampling_protocol
        WHERE location_id = %s AND domain = %s AND status = 'active'
        ORDER BY version DESC LIMIT 1
    """, (location_id, domain))
    row = cur.fetchone()
    cur.close()
    return dict(row) if row else None
