#!/usr/bin/env python3
"""
Landscape Conservation & Connectivity

Tracks habitat zones, wildlife corridors, hedgerows, buffer zone
compliance, and landscape-level biodiversity assessment.

Usage:
    python -m services.analytics.landscape_conservation create-habitat --location-id UUID --name "Riparian Buffer" --type riparian --area 0.5 --biodiversity high
    python -m services.analytics.landscape_conservation create-corridor --location-id UUID --name "Stream Link" --source UUID --target UUID --width 15 --length 200
    python -m services.analytics.landscape_conservation record-hedgerow --location-id UUID --name "North Windbreak" --species '["calliandra","leucaena"]' --length 180 --purpose '["windbreak","biodiversity"]'
    python -m services.analytics.landscape_conservation record-buffer-check --location-id UUID --habitat-zone UUID --buffer-width 12 --minimum-required 10 --vegetation-pct 85
    python -m services.analytics.landscape_conservation record-biodiversity --location-id UUID --richness 34 --shannon 2.45 --habitat-diversity 1.8 --connectivity 6.5 --overall 7.2
    python -m services.analytics.landscape_conservation habitat-summary --location-id UUID
    python -m services.analytics.landscape_conservation corridor-status --location-id UUID
    python -m services.analytics.landscape_conservation buffer-compliance --location-id UUID
    python -m services.analytics.landscape_conservation biodiversity-trends --location-id UUID
    python -m services.analytics.landscape_conservation dashboard --location-id UUID
"""

import argparse
import json
import uuid
from datetime import date, timezone
from typing import Optional

from ..common.logging import get_logger

logger = get_logger("analytics.landscape_conservation")


# ============================================================
# Habitat Zone Creation
# ============================================================

def create_habitat_zone(
    conn,
    location_id: str,
    zone_name: str,
    habitat_type: str,
    area_ha: float,
    biodiversity_value: str = "medium",
    perimeter_m: float = None,
    description: str = None,
    gps_boundary: str = None,
    metadata: dict = None,
) -> dict:
    """Create a habitat zone record."""
    cur = conn.cursor()
    zone_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO habitat_zone
            (id, location_id, zone_name, habitat_type, area_ha,
             perimeter_m, description, biodiversity_value, gps_boundary,
             metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, 'active')
        RETURNING id
        """,
        (
            zone_id, location_id, zone_name, habitat_type, area_ha,
            perimeter_m, description, biodiversity_value,
            gps_boundary,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Created habitat zone %s at %s", zone_id[:8], location_id[:8])

    return {
        "zone_id": zone_id,
        "location_id": location_id,
        "zone_name": zone_name,
        "habitat_type": habitat_type,
        "area_ha": area_ha,
        "biodiversity_value": biodiversity_value,
    }


# ============================================================
# Wildlife Corridor Creation
# ============================================================

def create_corridor(
    conn,
    location_id: str,
    corridor_name: str,
    source_habitat_id: str = None,
    target_habitat_id: str = None,
    width_m: float = None,
    length_m: float = None,
    vegetation_type: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Create a wildlife corridor record."""
    cur = conn.cursor()
    corridor_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO wildlife_corridor
            (id, location_id, corridor_name, source_habitat_id,
             target_habitat_id, width_m, length_m, vegetation_type,
             notes, metadata, condition, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'fair', 'active')
        RETURNING id
        """,
        (
            corridor_id, location_id, corridor_name,
            source_habitat_id, target_habitat_id,
            width_m, length_m, vegetation_type,
            notes,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Created corridor %s at %s", corridor_id[:8], location_id[:8])

    return {
        "corridor_id": corridor_id,
        "location_id": location_id,
        "corridor_name": corridor_name,
        "source_habitat_id": source_habitat_id,
        "target_habitat_id": target_habitat_id,
        "width_m": width_m,
        "length_m": length_m,
    }


# ============================================================
# Hedgerow Recording
# ============================================================

def record_hedgerow(
    conn,
    location_id: str,
    hedgerow_name: str = None,
    species_mix: list = None,
    length_m: float = None,
    height_m: float = None,
    age_years: int = None,
    planting_date: date = None,
    purpose: list = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a hedgerow or windbreak."""
    cur = conn.cursor()
    hedgerow_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO hedgerow_record
            (id, location_id, hedgerow_name, species_mix, length_m,
             height_m, age_years, planting_date, purpose,
             notes, metadata, condition, status)
        VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, 'fair', 'active')
        RETURNING id
        """,
        (
            hedgerow_id, location_id, hedgerow_name,
            json.dumps(species_mix or []),
            length_m, height_m, age_years, planting_date,
            json.dumps(purpose or []),
            notes,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Recorded hedgerow %s at %s", hedgerow_id[:8], location_id[:8])

    return {
        "hedgerow_id": hedgerow_id,
        "location_id": location_id,
        "hedgerow_name": hedgerow_name,
        "species_mix": species_mix or [],
        "length_m": length_m,
        "purpose": purpose or [],
    }


# ============================================================
# Buffer Zone Compliance Check
# ============================================================

def record_buffer_check(
    conn,
    location_id: str,
    habitat_zone_id: str = None,
    buffer_width_m: float = None,
    minimum_required_m: float = None,
    vegetation_coverage_pct: float = None,
    erosion_observed: bool = False,
    notes: str = None,
    check_date: date = None,
    metadata: dict = None,
) -> dict:
    """Record a buffer zone compliance check."""
    cur = conn.cursor()
    check_id = str(uuid.uuid4())

    check_date = check_date or date.today()
    compliant = None
    if buffer_width_m is not None and minimum_required_m is not None:
        compliant = buffer_width_m >= minimum_required_m

    cur.execute(
        """
        INSERT INTO buffer_zone_monitoring
            (id, location_id, habitat_zone_id, check_date,
             buffer_width_m, minimum_required_m, compliant,
             vegetation_coverage_pct, erosion_observed,
             notes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'recorded')
        RETURNING id
        """,
        (
            check_id, location_id, habitat_zone_id, check_date,
            buffer_width_m, minimum_required_m, compliant,
            vegetation_coverage_pct, erosion_observed,
            notes,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Recorded buffer check %s at %s", check_id[:8], location_id[:8])

    return {
        "check_id": check_id,
        "location_id": location_id,
        "habitat_zone_id": habitat_zone_id,
        "check_date": check_date.isoformat(),
        "buffer_width_m": buffer_width_m,
        "minimum_required_m": minimum_required_m,
        "compliant": compliant,
        "vegetation_coverage_pct": vegetation_coverage_pct,
        "erosion_observed": erosion_observed,
    }


# ============================================================
# Biodiversity Score Recording
# ============================================================

def record_biodiversity_score(
    conn,
    location_id: str,
    species_richness: int = None,
    shannon_index: float = None,
    habitat_diversity_index: float = None,
    connectivity_score: float = None,
    overall_score: float = None,
    assessor: str = None,
    notes: str = None,
    assessment_date: date = None,
    metadata: dict = None,
) -> dict:
    """Record a landscape biodiversity assessment."""
    cur = conn.cursor()
    score_id = str(uuid.uuid4())

    assessment_date = assessment_date or date.today()

    cur.execute(
        """
        INSERT INTO landscape_biodiversity_score
            (id, location_id, assessment_date, species_richness,
             shannon_index, habitat_diversity_index, connectivity_score,
             overall_score, assessor, notes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'recorded')
        RETURNING id
        """,
        (
            score_id, location_id, assessment_date,
            species_richness, shannon_index,
            habitat_diversity_index, connectivity_score,
            overall_score, assessor, notes,
            json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Recorded biodiversity score %s at %s", score_id[:8], location_id[:8])

    return {
        "score_id": score_id,
        "location_id": location_id,
        "assessment_date": assessment_date.isoformat(),
        "species_richness": species_richness,
        "shannon_index": shannon_index,
        "habitat_diversity_index": habitat_diversity_index,
        "connectivity_score": connectivity_score,
        "overall_score": overall_score,
    }


# ============================================================
# Habitat Summary
# ============================================================

def get_habitat_summary(conn, location_id: str) -> dict:
    """Get habitat zones with area and biodiversity value."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT habitat_id, zone_name, habitat_type, area_ha,
               perimeter_m, biodiversity_value, status,
               corridor_count, compliant_buffer_checks, total_buffer_checks
        FROM v_habitat_summary
        WHERE location_id = %s
        ORDER BY area_ha DESC NULLS LAST
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    zones = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT COUNT(*) AS total_zones,
               SUM(area_ha) AS total_area_ha,
               COUNT(*) FILTER (WHERE biodiversity_value = 'critical') AS critical_habitats,
               COUNT(*) FILTER (WHERE biodiversity_value = 'high') AS high_value_habitats
        FROM habitat_zone
        WHERE location_id = %s AND status = 'active'
        """,
        (location_id,),
    )
    agg_row = cur.fetchone()
    cur.close()

    return {
        "location_id": location_id,
        "total_zones": int(agg_row[0]) if agg_row[0] else 0,
        "total_area_ha": round(float(agg_row[1]), 2) if agg_row[1] else 0,
        "critical_habitats": int(agg_row[2]) if agg_row[2] else 0,
        "high_value_habitats": int(agg_row[3]) if agg_row[3] else 0,
        "zones": zones,
    }


# ============================================================
# Corridor Status
# ============================================================

def get_corridor_status(conn, location_id: str) -> dict:
    """Get corridors with condition and connectivity status."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT corridor_id, corridor_name, source_habitat, target_habitat,
               width_m, length_m, vegetation_type, condition,
               last_survey_date, connectivity_status, status
        FROM v_corridor_status
        WHERE location_id = %s
        ORDER BY length_m DESC NULLS LAST
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    corridors = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT COUNT(*) AS total_corridors,
               COUNT(*) FILTER (WHERE condition IN ('excellent', 'good')) AS healthy_corridors,
               SUM(length_m) AS total_length_m,
               AVG(width_m) AS avg_width_m
        FROM wildlife_corridor
        WHERE location_id = %s AND status = 'active'
        """,
        (location_id,),
    )
    agg_row = cur.fetchone()
    cur.close()

    return {
        "location_id": location_id,
        "total_corridors": int(agg_row[0]) if agg_row[0] else 0,
        "healthy_corridors": int(agg_row[1]) if agg_row[1] else 0,
        "total_length_m": round(float(agg_row[2]), 2) if agg_row[2] else 0,
        "avg_width_m": round(float(agg_row[3]), 2) if agg_row[3] else 0,
        "corridors": corridors,
    }


# ============================================================
# Buffer Compliance
# ============================================================

def get_buffer_compliance(conn, location_id: str) -> dict:
    """Get buffer zone compliance rates."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT habitat_zone_id, habitat_zone_name, total_checks,
               compliant_checks, compliance_rate_pct,
               avg_buffer_width_m, avg_minimum_required_m,
               avg_vegetation_coverage_pct, erosion_incidents, last_check_date
        FROM v_buffer_compliance
        WHERE location_id = %s
        ORDER BY compliance_rate_pct ASC NULLS LAST
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    compliance = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT COUNT(*) AS total_checks,
               COUNT(*) FILTER (WHERE compliant = TRUE) AS compliant_checks,
               ROUND(
                   COUNT(*) FILTER (WHERE compliant = TRUE)::NUMERIC /
                   NULLIF(COUNT(*), 0) * 100, 1
               ) AS overall_compliance_pct,
               COUNT(*) FILTER (WHERE erosion_observed = TRUE) AS erosion_incidents
        FROM buffer_zone_monitoring
        WHERE location_id = %s
        """,
        (location_id,),
    )
    agg_row = cur.fetchone()
    cur.close()

    return {
        "location_id": location_id,
        "total_checks": int(agg_row[0]) if agg_row[0] else 0,
        "compliant_checks": int(agg_row[1]) if agg_row[1] else 0,
        "overall_compliance_pct": round(float(agg_row[2]), 1) if agg_row[2] else 0,
        "total_erosion_incidents": int(agg_row[3]) if agg_row[3] else 0,
        "by_habitat": compliance,
    }


# ============================================================
# Biodiversity Trends
# ============================================================

def get_biodiversity_trends(conn, location_id: str) -> dict:
    """Get biodiversity scores over time."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT assessment_date, species_richness, shannon_index,
               habitat_diversity_index, connectivity_score, overall_score,
               prev_overall_score, score_change,
               prev_species_richness, prev_connectivity_score,
               assessor, status
        FROM v_landscape_biodiversity_trends
        WHERE location_id = %s
        ORDER BY assessment_date DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    assessments = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT COUNT(*) AS assessments,
               AVG(overall_score) AS avg_score,
               AVG(shannon_index) AS avg_shannon,
               AVG(species_richness) AS avg_richness,
               MIN(assessment_date) AS first_assessment,
               MAX(assessment_date) AS last_assessment
        FROM landscape_biodiversity_score
        WHERE location_id = %s AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    agg_row = cur.fetchone()
    cur.close()

    return {
        "location_id": location_id,
        "total_assessments": int(agg_row[0]) if agg_row[0] else 0,
        "avg_overall_score": round(float(agg_row[1]), 2) if agg_row[1] else None,
        "avg_shannon_index": round(float(agg_row[2]), 3) if agg_row[2] else None,
        "avg_species_richness": round(float(agg_row[3]), 1) if agg_row[3] else None,
        "first_assessment": agg_row[4].isoformat() if agg_row[4] else None,
        "last_assessment": agg_row[5].isoformat() if agg_row[5] else None,
        "assessments": assessments,
    }


# ============================================================
# Landscape Dashboard
# ============================================================

def get_landscape_dashboard(conn, location_id: str) -> dict:
    """Comprehensive dashboard with habitats, corridors, compliance, biodiversity."""
    habitats = get_habitat_summary(conn, location_id)
    corridors = get_corridor_status(conn, location_id)
    compliance = get_buffer_compliance(conn, location_id)
    biodiversity = get_biodiversity_trends(conn, location_id)

    connectivity_ratio = 0.0
    if habitats["total_zones"] > 0:
        connectivity_ratio = round(
            corridors["healthy_corridors"] / max(habitats["total_zones"], 1) * 100, 1
        )

    return {
        "location_id": location_id,
        "habitats": habitats,
        "corridors": corridors,
        "buffer_compliance": compliance,
        "biodiversity": biodiversity,
        "connectivity_ratio_pct": connectivity_ratio,
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Landscape conservation & connectivity")
    sub = parser.add_subparsers(dest="command")

    # create-habitat
    ch = sub.add_parser("create-habitat", help="Create habitat zone")
    ch.add_argument("--location-id", required=True)
    ch.add_argument("--name", required=True)
    ch.add_argument("--type", required=True, choices=[
        "wetland", "riparian", "forest_patch", "grassland",
        "hedgerow", "orchard", "agroforestry", "other",
    ])
    ch.add_argument("--area", type=float, required=True, help="Area in hectares")
    ch.add_argument("--biodiversity", default="medium", choices=["low", "medium", "high", "critical"])
    ch.add_argument("--perimeter", type=float, help="Perimeter in metres")
    ch.add_argument("--description")
    ch.add_argument("--json", action="store_true")

    # create-corridor
    cc = sub.add_parser("create-corridor", help="Create wildlife corridor")
    cc.add_argument("--location-id", required=True)
    cc.add_argument("--name", required=True)
    cc.add_argument("--source", help="Source habitat zone ID")
    cc.add_argument("--target", help="Target habitat zone ID")
    cc.add_argument("--width", type=float, help="Width in metres")
    cc.add_argument("--length", type=float, help="Length in metres")
    cc.add_argument("--vegetation", help="Vegetation type")
    cc.add_argument("--json", action="store_true")

    # record-hedgerow
    rh = sub.add_parser("record-hedgerow", help="Record hedgerow")
    rh.add_argument("--location-id", required=True)
    rh.add_argument("--name")
    rh.add_argument("--species", help="JSON array of species")
    rh.add_argument("--length", type=float, help="Length in metres")
    rh.add_argument("--height", type=float, help="Height in metres")
    rh.add_argument("--age", type=int, help="Age in years")
    rh.add_argument("--planting-date", help="Planting date YYYY-MM-DD")
    rh.add_argument("--purpose", help="JSON array of purposes")
    rh.add_argument("--json", action="store_true")

    # record-buffer-check
    rb = sub.add_parser("record-buffer-check", help="Record buffer zone check")
    rb.add_argument("--location-id", required=True)
    rb.add_argument("--habitat-zone", help="Habitat zone ID")
    rb.add_argument("--buffer-width", type=float, help="Buffer width in metres")
    rb.add_argument("--minimum-required", type=float, help="Minimum required width")
    rb.add_argument("--vegetation-pct", type=float, help="Vegetation coverage %")
    rb.add_argument("--erosion", action="store_true", help="Erosion observed")
    rb.add_argument("--check-date", help="Check date YYYY-MM-DD")
    rb.add_argument("--json", action="store_true")

    # record-biodiversity
    rbd = sub.add_parser("record-biodiversity", help="Record biodiversity assessment")
    rbd.add_argument("--location-id", required=True)
    rbd.add_argument("--richness", type=int, help="Species richness")
    rbd.add_argument("--shannon", type=float, help="Shannon index")
    rbd.add_argument("--habitat-diversity", type=float, help="Habitat diversity index")
    rbd.add_argument("--connectivity", type=float, help="Connectivity score")
    rbd.add_argument("--overall", type=float, help="Overall score")
    rbd.add_argument("--assessor")
    rbd.add_argument("--date", help="Assessment date YYYY-MM-DD")
    rbd.add_argument("--json", action="store_true")

    # habitat-summary
    hs = sub.add_parser("habitat-summary", help="Habitat zone summary")
    hs.add_argument("--location-id", required=True)
    hs.add_argument("--json", action="store_true")

    # corridor-status
    cs = sub.add_parser("corridor-status", help="Corridor status")
    cs.add_argument("--location-id", required=True)
    cs.add_argument("--json", action="store_true")

    # buffer-compliance
    bc = sub.add_parser("buffer-compliance", help="Buffer zone compliance")
    bc.add_argument("--location-id", required=True)
    bc.add_argument("--json", action="store_true")

    # biodiversity-trends
    bt = sub.add_parser("biodiversity-trends", help="Biodiversity trends")
    bt.add_argument("--location-id", required=True)
    bt.add_argument("--json", action="store_true")

    # dashboard
    db_cmd = sub.add_parser("dashboard", help="Landscape dashboard")
    db_cmd.add_argument("--location-id", required=True)
    db_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from services.common.database import get_db

    if args.command not in (
        "create-habitat", "create-corridor", "record-hedgerow",
        "record-buffer-check", "record-biodiversity",
        "habitat-summary", "corridor-status", "buffer-compliance",
        "biodiversity-trends", "dashboard",
    ):
        parser.print_help()
        return

    db = get_db()

    try:
        if args.command == "create-habitat":
            result = create_habitat_zone(
                db, args.location_id, args.name, args.type, args.area,
                biodiversity_value=args.biodiversity,
                perimeter_m=args.perimeter, description=args.description,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_habitat(result)
            print(output)

        elif args.command == "create-corridor":
            result = create_corridor(
                db, args.location_id, args.name,
                source_habitat_id=args.source,
                target_habitat_id=args.target,
                width_m=args.width, length_m=args.length,
                vegetation_type=args.vegetation,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_corridor(result)
            print(output)

        elif args.command == "record-hedgerow":
            species = json.loads(args.species) if args.species else []
            purpose = json.loads(args.purpose) if args.purpose else []
            pd = date.fromisoformat(args.planting_date) if args.planting_date else None
            result = record_hedgerow(
                db, args.location_id, hedgerow_name=args.name,
                species_mix=species, length_m=args.length,
                height_m=args.height, age_years=args.age,
                planting_date=pd, purpose=purpose,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_hedgerow(result)
            print(output)

        elif args.command == "record-buffer-check":
            cd = date.fromisoformat(args.check_date) if args.check_date else None
            result = record_buffer_check(
                db, args.location_id,
                habitat_zone_id=args.habitat_zone,
                buffer_width_m=args.buffer_width,
                minimum_required_m=args.minimum_required,
                vegetation_coverage_pct=args.vegetation_pct,
                erosion_observed=args.erosion,
                check_date=cd,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_buffer(result)
            print(output)

        elif args.command == "record-biodiversity":
            ad = date.fromisoformat(args.date) if args.date else None
            result = record_biodiversity_score(
                db, args.location_id,
                species_richness=args.richness,
                shannon_index=args.shannon,
                habitat_diversity_index=args.habitat_diversity,
                connectivity_score=args.connectivity,
                overall_score=args.overall,
                assessor=args.assessor,
                assessment_date=ad,
            )
            output = json.dumps(result, indent=2, default=str) if args.json else _format_biodiversity(result)
            print(output)

        elif args.command == "habitat-summary":
            result = get_habitat_summary(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_habitat_summary(result)
            print(output)

        elif args.command == "corridor-status":
            result = get_corridor_status(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_corridor_status(result)
            print(output)

        elif args.command == "buffer-compliance":
            result = get_buffer_compliance(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_buffer_compliance(result)
            print(output)

        elif args.command == "biodiversity-trends":
            result = get_biodiversity_trends(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_biodiversity_trends(result)
            print(output)

        elif args.command == "dashboard":
            result = get_landscape_dashboard(db, args.location_id)
            output = json.dumps(result, indent=2, default=str) if args.json else _format_dashboard(result)
            print(output)

    finally:
        db.close()


def _format_habitat(r: dict) -> str:
    return f"Habitat: {r['zone_name']} ({r['habitat_type']}) — {r['area_ha']} ha, biodiversity={r['biodiversity_value']}"


def _format_corridor(r: dict) -> str:
    src = r['source_habitat_id'][:8] + '...' if r['source_habitat_id'] else 'none'
    tgt = r['target_habitat_id'][:8] + '...' if r['target_habitat_id'] else 'none'
    return f"Corridor: {r['corridor_name']} — {src} → {tgt}, {r['width_m']}m × {r['length_m']}m"


def _format_hedgerow(r: dict) -> str:
    sp = ', '.join(r['species_mix'][:3]) if r['species_mix'] else 'none'
    return f"Hedgerow: {r['hedgerow_name']} — {r['length_m']}m, species=[{sp}]"


def _format_buffer(r: dict) -> str:
    status = "COMPLIANT" if r['compliant'] else ("NON-COMPLIANT" if r['compliant'] is not None else "unknown")
    return (
        f"Buffer Check: {status} — width={r['buffer_width_m']}m (min={r['minimum_required_m']}m), "
        f"vegetation={r['vegetation_coverage_pct']}%, erosion={r['erosion_observed']}"
    )


def _format_biodiversity(r: dict) -> str:
    return (
        f"Biodiversity: overall={r['overall_score']}, richness={r['species_richness']}, "
        f"shannon={r['shannon_index']}, connectivity={r['connectivity_score']}"
    )


def _format_habitat_summary(r: dict) -> str:
    lines = [
        f"Habitat Summary — {r['location_id'][:8]}... ({r['total_zones']} zones, {r['total_area_ha']} ha)",
        f"  Critical: {r['critical_habitats']}  High-value: {r['high_value_habitats']}",
    ]
    for z in r["zones"]:
        lines.append(
            f"  {z['zone_name']:30s} {z['habitat_type']:15s} {z['area_ha']:.2f} ha  "
            f"bio={z['biodiversity_value']}  corridors={z['corridor_count']}"
        )
    return "\n".join(lines) if len(lines) > 2 else "No habitat data."


def _format_corridor_status(r: dict) -> str:
    lines = [
        f"Corridor Status — {r['location_id'][:8]}... ({r['total_corridors']} corridors, {r['total_length_m']:.0f}m total)",
        f"  Healthy: {r['healthy_corridors']}  Avg width: {r['avg_width_m']:.1f}m",
    ]
    for c in r["corridors"]:
        lines.append(
            f"  {c['corridor_name']:30s} {c['condition']:10s} {c['connectivity_status']:20s} "
            f"{c['length_m']:.0f}m × {c['width_m']:.0f}m"
        )
    return "\n".join(lines) if len(lines) > 2 else "No corridor data."


def _format_buffer_compliance(r: dict) -> str:
    lines = [
        f"Buffer Compliance — {r['location_id'][:8]}... ({r['total_checks']} checks, {r['overall_compliance_pct']}% compliant)",
        f"  Erosion incidents: {r['total_erosion_incidents']}",
    ]
    for c in r["by_habitat"]:
        lines.append(
            f"  {(c['habitat_zone_name'] or 'unassigned'):30s} "
            f"{c['compliance_rate_pct']}%  ({c['compliant_checks']}/{c['total_checks']})"
        )
    return "\n".join(lines) if len(lines) > 2 else "No buffer data."


def _format_biodiversity_trends(r: dict) -> str:
    lines = [
        f"Biodiversity Trends — {r['location_id'][:8]}... ({r['total_assessments']} assessments)",
        f"  Avg score: {r['avg_overall_score']}  Avg Shannon: {r['avg_shannon_index']}  Avg richness: {r['avg_species_richness']}",
    ]
    for a in r["assessments"]:
        change = ""
        if a["score_change"] is not None:
            delta = float(a["score_change"])
            change = f" (Δ{delta:+.2f})"
        lines.append(
            f"  {a['assessment_date']}  overall={a['overall_score']}{change}  "
            f"richness={a['species_richness']}  shannon={a['shannon_index']}"
        )
    return "\n".join(lines) if len(lines) > 2 else "No biodiversity data."


def _format_dashboard(r: dict) -> str:
    lines = [
        f"Landscape Dashboard — {r['location_id'][:8]}...",
        f"  Habitats: {r['habitats']['total_zones']} zones, {r['habitats']['total_area_ha']} ha",
        f"  Corridors: {r['corridors']['total_corridors']} ({r['corridors']['healthy_corridors']} healthy, {r['corridors']['total_length_m']:.0f}m)",
        f"  Buffer compliance: {r['buffer_compliance']['overall_compliance_pct']}%",
        f"  Connectivity ratio: {r['connectivity_ratio_pct']}%",
    ]
    if r["biodiversity"]["avg_overall_score"]:
        lines.append(f"  Biodiversity score: {r['biodiversity']['avg_overall_score']}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
