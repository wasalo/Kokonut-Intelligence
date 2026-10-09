#!/usr/bin/env python3
"""
Crop Rotation Planning

Manages multi-season rotation plans, tracks rotation impacts on soil health
and pest pressure, validates plans against best practices, and recommends
rotations based on crop family diversity.

Usage:
    python -m services.analytics.crop_rotation create-plan --location-id UUID --name "3-Year Plan"
    python -m services.analytics.crop_rotation add-slot --plan-id UUID --season 1 --crop maize --purpose cash_crop
    python -m services.analytics.crop_rotation get-plan --plan-id UUID
    python -m services.analytics.crop_rotation list-plans --location-id UUID
    python -m services.analytics.crop_rotation record-impact --plan-id UUID --slot-id UUID --type soil_health --direction positive --severity 15
    python -m services.analytics.crop_rotation impact-summary --plan-id UUID
    python -m services.analytics.crop_rotation family-usage --location-id UUID
    python -m services.analytics.crop_rotation recommend --location-id UUID --plot-id UUID
    python -m services.analytics.crop_rotation validate --plan-id UUID
    python -m services.analytics.crop_rotation dashboard --location-id UUID
"""

import json
import uuid
from datetime import date
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.crop_rotation")


# ============================================================
# Crop Family Lookup
# ============================================================

def _resolve_crop_family(cur, crop_name: str) -> Optional[str]:
    """Resolve a crop name to its crop_family UUID."""
    cur.execute(
        """
        SELECT id FROM crop_family
        WHERE example_crops::text ILIKE %s
           OR family_name ILIKE %s
        LIMIT 1
        """,
        (f"%{crop_name}%", crop_name),
    )
    row = cur.fetchone()
    return str(row[0]) if row else None


# ============================================================
# Create Rotation Plan
# ============================================================

def create_plan(
    conn,
    location_id: str,
    plan_name: str,
    plot_id: str = None,
    zone_id: str = None,
    duration_seasons: int = 4,
    start_season: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Create a new rotation plan."""
    cur = conn.cursor()
    plan_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO rotation_plan
            (id, location_id, plan_name, plot_id, zone_id,
             duration_seasons, start_season, status, notes, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft', %s, %s::jsonb)
        RETURNING id
        """,
        (
            plan_id, location_id, plan_name, plot_id, zone_id,
            duration_seasons, start_season, notes,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Created rotation plan %s for location %s", plan_id, location_id)

    return {
        "plan_id": plan_id,
        "location_id": location_id,
        "plan_name": plan_name,
        "plot_id": plot_id,
        "zone_id": zone_id,
        "duration_seasons": duration_seasons,
        "start_season": start_season,
        "status": "draft",
    }


# ============================================================
# Add Slot to Plan
# ============================================================

def add_slot(
    conn,
    plan_id: str,
    season_number: int,
    crop_name: str,
    purpose: str = None,
    expected_area_ha: float = None,
    season_name: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Add a season slot to a rotation plan."""
    cur = conn.cursor()
    slot_id = str(uuid.uuid4())

    family_id = _resolve_crop_family(cur, crop_name)

    cur.execute(
        """
        INSERT INTO rotation_slot
            (id, plan_id, season_number, season_name, crop_name,
             crop_family_id, purpose, expected_area_ha, notes, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (
            slot_id, plan_id, season_number, season_name, crop_name,
            family_id, purpose, expected_area_ha, notes,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Added slot season %d (%s) to plan %s", season_number, crop_name, plan_id)

    return {
        "slot_id": slot_id,
        "plan_id": plan_id,
        "season_number": season_number,
        "crop_name": crop_name,
        "crop_family_id": family_id,
        "purpose": purpose,
        "expected_area_ha": expected_area_ha,
    }


# ============================================================
# Get Plan with Full Crop Sequence
# ============================================================

def get_plan(conn, plan_id: str) -> dict:
    """Get rotation plan with its full crop sequence."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, location_id, plan_name, plot_id, zone_id,
               duration_seasons, start_season, status, notes,
               metadata, created_at, updated_at
        FROM rotation_plan
        WHERE id = %s
        """,
        (plan_id,),
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    if not row:
        cur.close()
        return {"error": "plan_not_found"}

    plan = dict(zip(cols, row))

    cur.execute(
        """
        SELECT rs.id, rs.season_number, rs.season_name, rs.crop_name,
               cf.family_name, rs.purpose, rs.expected_area_ha,
               rs.notes, rs.metadata
        FROM rotation_slot rs
        LEFT JOIN crop_family cf ON cf.id = rs.crop_family_id
        WHERE rs.plan_id = %s
        ORDER BY rs.season_number
        """,
        (plan_id,),
    )
    slot_cols = [d[0] for d in cur.description]
    slots = [dict(zip(slot_cols, r)) for r in cur.fetchall()]

    cur.close()

    plan["slots"] = slots
    plan["crop_sequence"] = [s["crop_name"] for s in slots]
    plan["family_sequence"] = [s["family_name"] for s in slots]
    plan["filled_slots"] = len(slots)
    plan["metadata"] = str(plan.get("metadata", "{}"))
    plan["created_at"] = plan["created_at"].isoformat() if plan["created_at"] else None
    plan["updated_at"] = plan["updated_at"].isoformat() if plan["updated_at"] else None

    return plan


# ============================================================
# List Plans
# ============================================================

def list_plans(conn, location_id: str) -> dict:
    """List all rotation plans for a location."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT rp.id, rp.plan_name, rp.plot_id, rp.zone_id,
               rp.duration_seasons, rp.status, rp.start_season,
               (SELECT COUNT(*) FROM rotation_slot rs WHERE rs.plan_id = rp.id) AS slot_count,
               rp.created_at
        FROM rotation_plan rp
        WHERE rp.location_id = %s
        ORDER BY rp.created_at DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    plans = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()

    for p in plans:
        p["id"] = str(p["id"])
        p["created_at"] = p["created_at"].isoformat() if p["created_at"] else None

    return {
        "location_id": location_id,
        "plans": plans,
        "total": len(plans),
    }


# ============================================================
# Record Impact
# ============================================================

def record_impact(
    conn,
    plan_id: str = None,
    slot_id: str = None,
    location_id: str = None,
    impact_type: str = "soil_health",
    impact_direction: str = "positive",
    severity_pct: float = None,
    measurement_value: float = None,
    measurement_unit: str = None,
    record_date: date = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a rotation impact observation."""
    cur = conn.cursor()
    impact_id = str(uuid.uuid4())

    if not location_id and plan_id:
        cur.execute(
            "SELECT location_id FROM rotation_plan WHERE id = %s",
            (plan_id,),
        )
        r = cur.fetchone()
        location_id = str(r[0]) if r else None

    record_date = record_date or date.today()

    cur.execute(
        """
        INSERT INTO rotation_impact_record
            (id, plan_id, slot_id, location_id, record_date,
             impact_type, impact_direction, severity_pct,
             measurement_value, measurement_unit, notes, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'recorded', %s::jsonb)
        RETURNING id
        """,
        (
            impact_id, plan_id, slot_id, location_id, record_date,
            impact_type, impact_direction, severity_pct,
            measurement_value, measurement_unit, notes,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Recorded impact %s: %s/%s on plan %s",
                impact_id, impact_type, impact_direction, plan_id)

    return {
        "impact_id": impact_id,
        "plan_id": plan_id,
        "slot_id": slot_id,
        "location_id": location_id,
        "impact_type": impact_type,
        "impact_direction": impact_direction,
        "severity_pct": severity_pct,
        "record_date": record_date.isoformat(),
    }


# ============================================================
# Impact Summary
# ============================================================

def get_impact_summary(conn, plan_id: str) -> dict:
    """Get impact records aggregated by type and direction."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT impact_type, impact_direction,
               COUNT(*) AS record_count,
               AVG(severity_pct) AS avg_severity,
               MAX(severity_pct) AS max_severity,
               MIN(record_date) AS first_recorded,
               MAX(record_date) AS last_recorded,
               measurement_unit
        FROM rotation_impact_record
        WHERE plan_id = %s AND status != 'dismissed'
        GROUP BY impact_type, impact_direction, measurement_unit
        ORDER BY impact_type, impact_direction
        """,
        (plan_id,),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE impact_direction = 'positive'),
               COUNT(*) FILTER (WHERE impact_direction = 'negative')
        FROM rotation_impact_record
        WHERE plan_id = %s AND status != 'dismissed'
        """,
        (plan_id,),
    )
    totals = cur.fetchone()
    cur.close()

    for row in rows:
        row["record_count"] = int(row["record_count"])
        row["avg_severity"] = round(float(row["avg_severity"]), 2) if row["avg_severity"] else None
        row["max_severity"] = round(float(row["max_severity"]), 2) if row["max_severity"] else None
        row["first_recorded"] = row["first_recorded"].isoformat() if row["first_recorded"] else None
        row["last_recorded"] = row["last_recorded"].isoformat() if row["last_recorded"] else None

    return {
        "plan_id": plan_id,
        "total_records": int(totals[0]) if totals[0] else 0,
        "positive_count": int(totals[1]) if totals[1] else 0,
        "negative_count": int(totals[2]) if totals[2] else 0,
        "impacts_by_type": rows,
    }


# ============================================================
# Crop Family Usage
# ============================================================

def get_crop_family_usage(conn, location_id: str) -> dict:
    """Check crop family repetition across plots and plans."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT cf.id AS family_id, cf.family_name, cf.example_crops,
               rp.plan_name, rp.id AS plan_id,
               COUNT(rs.id) AS slot_count,
               ARRAY_AGG(rs.crop_name ORDER BY rs.season_number) AS crops_used,
               ARRAY_AGG(rs.season_number ORDER BY rs.season_number) AS seasons_used
        FROM crop_family cf
        LEFT JOIN rotation_slot rs ON rs.crop_family_id = cf.id
        LEFT JOIN rotation_plan rp ON rp.id = rs.plan_id AND rp.location_id = %s
        WHERE rp.location_id = %s OR rp.location_id IS NULL
        GROUP BY cf.id, cf.family_name, cf.example_crops, rp.plan_name, rp.id
        HAVING rp.location_id = %s
        ORDER BY cf.family_name
        """,
        (location_id, location_id, location_id),
    )
    cols = [d[0] for d in cur.description]
    usage = [dict(zip(cols, r)) for r in cur.fetchall()]

    # Overall family distribution across all plans
    cur.execute(
        """
        SELECT cf.family_name, COUNT(rs.id) AS total_slots,
               COUNT(DISTINCT rp.id) AS plan_count
        FROM rotation_slot rs
        JOIN rotation_plan rp ON rp.id = rs.plan_id
        JOIN crop_family cf ON cf.id = rs.crop_family_id
        WHERE rp.location_id = %s
        GROUP BY cf.family_name
        ORDER BY total_slots DESC
        """,
        (location_id,),
    )
    dist_cols = [d[0] for d in cur.description]
    distribution = [dict(zip(dist_cols, r)) for r in cur.fetchall()]
    cur.close()

    for u in usage:
        u["family_id"] = str(u["family_id"])
        u["slot_count"] = int(u["slot_count"])

    for d in distribution:
        d["total_slots"] = int(d["total_slots"])
        d["plan_count"] = int(d["plan_count"])

    return {
        "location_id": location_id,
        "family_usage": usage,
        "family_distribution": distribution,
        "families_used": len(distribution),
    }


# ============================================================
# Recommend Rotation
# ============================================================

def recommend_rotation(conn, location_id: str, plot_id: str = None) -> dict:
    """Recommend rotation based on soil data and family diversity."""
    cur = conn.cursor()

    # Gather recent crop history for this location
    cur.execute(
        """
        SELECT rs.crop_name, cf.family_name, rp.plot_id,
               COUNT(*) AS times_used
        FROM rotation_slot rs
        JOIN rotation_plan rp ON rp.id = rs.plan_id
        LEFT JOIN crop_family cf ON cf.id = rs.crop_family_id
        WHERE rp.location_id = %s
        GROUP BY rs.crop_name, cf.family_name, rp.plot_id
        ORDER BY times_used DESC
        """,
        (location_id,),
    )
    hist_cols = [d[0] for d in cur.description]
    history = [dict(zip(hist_cols, r)) for r in cur.fetchall()]

    # All crop families
    cur.execute(
        """
        SELECT id, family_name, example_crops, notes
        FROM crop_family
        ORDER BY family_name
        """,
    )
    fam_cols = [d[0] for d in cur.description]
    families = [dict(zip(fam_cols, r)) for r in cur.fetchall()]

    # Soil health trends
    cur.execute(
        """
        SELECT AVG(severity_pct) AS avg_soil_severity
        FROM rotation_impact_record rip
        JOIN rotation_plan rp ON rp.id = rip.plan_id
        WHERE rp.location_id = %s
          AND rip.impact_type = 'soil_health'
          AND rip.impact_direction = 'negative'
          AND rip.status != 'dismissed'
        """,
        (location_id,),
    )
    soil_row = cur.fetchone()
    avg_soil_severity = float(soil_row[0]) if soil_row and soil_row[0] else None

    # Impact history
    cur.execute(
        """
        SELECT impact_type, impact_direction, COUNT(*) AS cnt
        FROM rotation_impact_record rip
        JOIN rotation_plan rp ON rp.id = rip.plan_id
        WHERE rp.location_id = %s AND rip.status != 'dismissed'
        GROUP BY impact_type, impact_direction
        """,
        (location_id,),
    )
    imp_cols = [d[0] for d in cur.description]
    impacts = [dict(zip(imp_cols, r)) for r in cur.fetchall()]
    cur.close()

    # Determine overused families
    used_families = set(h["family_name"] for h in history if h["family_name"])
    overused = set()
    for h in history:
        if h["times_used"] and int(h["times_used"]) >= 2:
            overused.add(h["family_name"])

    # Build recommendations from families not overused
    recommendations = []
    for fam in families:
        fname = fam["family_name"]
        fid = str(fam["id"])
        crops = json.loads(fam["example_crops"]) if isinstance(fam["example_crops"], str) else (fam["example_crops"] or [])

        if fname in overused:
            confidence = 0.3
            reason = f"{fname} is overused in recent rotations"
        elif fname not in used_families:
            confidence = 0.9
            reason = f"{fname} has not been used — good for diversity"
        else:
            confidence = 0.6
            reason = f"{fname} is moderately used"

        if crops:
            recommended_crop = crops[0]
        else:
            recommended_crop = fname.lower().replace("aceae", "")

        recommendations.append({
            "family_name": fname,
            "family_id": fid,
            "recommended_crop": recommended_crop,
            "confidence_score": confidence,
            "reason": reason,
            "soil_benefit": fam.get("notes", ""),
            "is_overused": fname in overused,
        })

    recommendations.sort(key=lambda x: x["confidence_score"], reverse=True)

    return {
        "location_id": location_id,
        "plot_id": plot_id,
        "history_crops": len(history),
        "overused_families": sorted(overused),
        "unused_families": sorted(used_families and set(d["family_name"] for d in families) - used_families),
        "avg_soil_severity": avg_soil_severity,
        "recommendations": recommendations,
    }


# ============================================================
# Validate Plan
# ============================================================

def validate_plan(conn, plan_id: str) -> dict:
    """Validate rotation plan against best practices."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT rs.season_number, rs.crop_name, cf.family_name, rs.purpose
        FROM rotation_slot rs
        LEFT JOIN crop_family cf ON cf.id = rs.crop_family_id
        WHERE rs.plan_id = %s
        ORDER BY rs.season_number
        """,
        (plan_id,),
    )
    cols = [d[0] for d in cur.description]
    slots = [dict(zip(cols, r)) for r in cur.fetchall()]

    cur.execute(
        "SELECT duration_seasons FROM rotation_plan WHERE id = %s",
        (plan_id,),
    )
    plan_row = cur.fetchone()
    cur.close()

    if not plan_row:
        return {"error": "plan_not_found"}

    duration = int(plan_row[0]) if plan_row[0] else 4

    issues = []
    warnings = []
    checks_passed = 0
    total_checks = 0

    # Check 1: Same family consecutive
    total_checks += 1
    consecutive_families = []
    for i in range(1, len(slots)):
        prev_fam = slots[i - 1]["family_name"]
        curr_fam = slots[i]["family_name"]
        if prev_fam and curr_fam and prev_fam == curr_fam:
            consecutive_families.append({
                "season_1": slots[i - 1]["season_number"],
                "season_2": slots[i]["season_number"],
                "family": prev_fam,
            })
    if consecutive_families:
        issues.append({
            "check": "no_same_family_consecutive",
            "passed": False,
            "details": consecutive_families,
        })
    else:
        checks_passed += 1

    # Check 2: Cover crop inclusion
    total_checks += 1
    purposes = [s["purpose"] for s in slots]
    has_cover = any(p in ("cover_crop", "green_manure", "nitrogen_fixer") for p in purposes)
    if not has_cover:
        warnings.append({
            "check": "cover_crop_inclusion",
            "passed": False,
            "message": "No cover crop, green manure, or nitrogen fixer in rotation",
        })
    else:
        checks_passed += 1

    # Check 3: Solanaceae break (min 3-season gap)
    total_checks += 1
    solanaceae_seasons = [
        s["season_number"] for s in slots
        if s["family_name"] == "Solanaceae"
    ]
    solanaceae_gaps = []
    for i in range(1, len(solanaceae_seasons)):
        gap = solanaceae_seasons[i] - solanaceae_seasons[i - 1]
        solanaceae_gaps.append(gap)
        if gap < 3:
            issues.append({
                "check": "solanaceae_break",
                "passed": False,
                "details": {
                    "seasons": [solanaceae_seasons[i - 1], solanaceae_seasons[i]],
                    "gap": gap,
                    "minimum_required": 3,
                },
            })
    if not solanaceae_gaps or all(g >= 3 for g in solanaceae_gaps):
        checks_passed += 1

    # Check 4: Plan fills expected duration
    total_checks += 1
    if len(slots) < duration:
        warnings.append({
            "check": "plan_fills_duration",
            "passed": False,
            "message": f"Plan has {len(slots)} of {duration} expected seasons filled",
        })
    else:
        checks_passed += 1

    # Check 5: No same crop repeated
    total_checks += 1
    crop_names = [s["crop_name"] for s in slots]
    seen = set()
    duplicates = []
    for c in crop_names:
        if c in seen:
            duplicates.append(c)
        seen.add(c)
    if duplicates:
        warnings.append({
            "check": "no_duplicate_crops",
            "passed": False,
            "message": f"Crops repeated: {', '.join(duplicates)}",
        })
    else:
        checks_passed += 1

    score = round(checks_passed / total_checks * 100, 1) if total_checks > 0 else 0

    return {
        "plan_id": plan_id,
        "duration_seasons": duration,
        "slots_validated": len(slots),
        "total_checks": total_checks,
        "checks_passed": checks_passed,
        "score_pct": score,
        "issues": issues,
        "warnings": warnings,
        "valid": len(issues) == 0,
    }


# ============================================================
# Rotation Dashboard
# ============================================================

def get_rotation_dashboard(conn, location_id: str) -> dict:
    """Get rotation dashboard with plans, impacts, and family diversity."""
    cur = conn.cursor()

    # Plans
    cur.execute(
        """
        SELECT rp.id, rp.plan_name, rp.status, rp.duration_seasons,
               (SELECT COUNT(*) FROM rotation_slot rs WHERE rs.plan_id = rp.id) AS slot_count,
               rp.created_at
        FROM rotation_plan rp
        WHERE rp.location_id = %s
        ORDER BY rp.created_at DESC
        """,
        (location_id,),
    )
    plan_cols = [d[0] for d in cur.description]
    plans = [dict(zip(plan_cols, r)) for r in cur.fetchall()]

    # Impact summary
    cur.execute(
        """
        SELECT rip.impact_type, rip.impact_direction,
               COUNT(*) AS cnt,
               AVG(rip.severity_pct) AS avg_severity
        FROM rotation_impact_record rip
        JOIN rotation_plan rp ON rp.id = rip.plan_id
        WHERE rp.location_id = %s AND rip.status != 'dismissed'
        GROUP BY rip.impact_type, rip.impact_direction
        """,
        (location_id,),
    )
    imp_cols = [d[0] for d in cur.description]
    impacts = [dict(zip(imp_cols, r)) for r in cur.fetchall()]

    # Family diversity
    cur.execute(
        """
        SELECT cf.family_name, COUNT(rs.id) AS slot_count
        FROM rotation_slot rs
        JOIN rotation_plan rp ON rp.id = rs.plan_id
        JOIN crop_family cf ON cf.id = rs.crop_family_id
        WHERE rp.location_id = %s
        GROUP BY cf.family_name
        ORDER BY slot_count DESC
        """,
        (location_id,),
    )
    fam_cols = [d[0] for d in cur.description]
    families = [dict(zip(fam_cols, r)) for r in cur.fetchall()]

    # Recent impact records
    cur.execute(
        """
        SELECT rip.impact_type, rip.impact_direction, rip.severity_pct,
               rip.record_date, rs.crop_name
        FROM rotation_impact_record rip
        JOIN rotation_plan rp ON rp.id = rip.plan_id
        LEFT JOIN rotation_slot rs ON rs.id = rip.slot_id
        WHERE rp.location_id = %s AND rip.status != 'dismissed'
        ORDER BY rip.record_date DESC
        LIMIT 10
        """,
        (location_id,),
    )
    recent_cols = [d[0] for d in cur.description]
    recent = [dict(zip(recent_cols, r)) for r in cur.fetchall()]

    cur.close()

    for p in plans:
        p["id"] = str(p["id"])
        p["slot_count"] = int(p["slot_count"])
        p["created_at"] = p["created_at"].isoformat() if p["created_at"] else None

    for imp in impacts:
        imp["cnt"] = int(imp["cnt"])
        imp["avg_severity"] = round(float(imp["avg_severity"]), 2) if imp["avg_severity"] else None

    for f in families:
        f["slot_count"] = int(f["slot_count"])

    for r in recent:
        r["record_date"] = r["record_date"].isoformat() if r["record_date"] else None
        r["severity_pct"] = round(float(r["severity_pct"]), 2) if r["severity_pct"] else None

    active = sum(1 for p in plans if p["status"] == "active")
    draft = sum(1 for p in plans if p["status"] == "draft")
    completed = sum(1 for p in plans if p["status"] == "completed")

    return {
        "location_id": location_id,
        "summary": {
            "total_plans": len(plans),
            "active_plans": active,
            "draft_plans": draft,
            "completed_plans": completed,
            "unique_families": len(families),
        },
        "plans": plans,
        "impacts_by_type": impacts,
        "family_diversity": families,
        "recent_impacts": recent,
    }
