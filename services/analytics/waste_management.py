#!/usr/bin/env python3
"""
Waste Management

Records waste streams, composting operations, recycling activities,
and pollution incidents. Provides summaries, efficiency metrics, and dashboards.

Usage:
    python -m services.analytics.waste_management record-waste --location-id UUID --waste-type organic --waste-name "Crop residues" --quantity 50.0 --disposal-method composting
    python -m services.analytics.waste_management record-composting --location-id UUID --feedstock "Banana stems" --feedstock-kg 100 --method vermicomposting
    python -m services.analytics.waste_management record-recycling --location-id UUID --material plastic --quantity 15.0 --destination "Recycling center" --revenue 5.00
    python -m services.analytics.waste_management report-incident --location-id UUID --incident-type chemical_spill --severity high --description "Pesticide container leak" --affected-area "Near stream"
    python -m services.analytics.waste_management resolve-incident --incident-id UUID --remedial-action "Cleaned and neutralized soil" --resolution-date 2026-07-10
    python -m services.analytics.waste_management waste-summary --location-id UUID
    python -m services.analytics.waste_management composting-efficiency --location-id UUID
    python -m services.analytics.waste_management open-incidents --location-id UUID
    python -m services.analytics.waste_management dashboard --location-id UUID
"""

import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from services.common.commands import CommandLine
from ..common.logging import get_logger

logger = get_logger("analytics.waste_management")


# ============================================================
# Waste Stream Recording
# ============================================================

def record_waste(
    conn,
    location_id: str,
    waste_type: str,
    waste_name: str,
    quantity_kg: float,
    disposal_method: str,
    source: str = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a waste stream entry."""
    cur = conn.cursor()
    waste_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO waste_stream_record
            (id, location_id, waste_type, waste_name, quantity_kg,
             disposal_method, source, notes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'draft')
        RETURNING id
        """,
        (
            waste_id, location_id, waste_type, waste_name, quantity_kg,
            disposal_method, source, notes, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Recorded waste stream %s: %s %s kg via %s", waste_id, waste_type, quantity_kg, disposal_method)

    return {
        "waste_id": waste_id,
        "location_id": location_id,
        "waste_type": waste_type,
        "waste_name": waste_name,
        "quantity_kg": quantity_kg,
        "disposal_method": disposal_method,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# Composting Recording
# ============================================================

def record_composting(
    conn,
    location_id: str,
    feedstock_type: str,
    feedstock_kg: float,
    compost_method: str,
    duration_days: int = None,
    output_kg: float = None,
    temperature_c: float = None,
    ph: float = None,
    moisture_pct: float = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a composting operation."""
    cur = conn.cursor()
    compost_id = str(uuid.uuid4())

    output_yield_pct = None
    if output_kg is not None and feedstock_kg > 0:
        output_yield_pct = round(output_kg / feedstock_kg * 100, 1)

    cur.execute(
        """
        INSERT INTO composting_record
            (id, location_id, feedstock_type, feedstock_kg, compost_method,
             duration_days, output_kg, output_yield_pct,
             temperature_c, ph, moisture_pct, notes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'draft')
        RETURNING id
        """,
        (
            compost_id, location_id, feedstock_type, feedstock_kg, compost_method,
            duration_days, output_kg, output_yield_pct,
            temperature_c, ph, moisture_pct, notes, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Recorded composting %s: %s %s kg via %s", compost_id, feedstock_type, feedstock_kg, compost_method)

    return {
        "compost_id": compost_id,
        "location_id": location_id,
        "feedstock_type": feedstock_type,
        "feedstock_kg": feedstock_kg,
        "compost_method": compost_method,
        "output_kg": output_kg,
        "output_yield_pct": output_yield_pct,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# Recycling Recording
# ============================================================

def record_recycling(
    conn,
    location_id: str,
    material_type: str,
    quantity_kg: float,
    destination: str,
    revenue: float = None,
    notes: str = None,
    metadata: dict = None,
) -> dict:
    """Record a recycling activity."""
    cur = conn.cursor()
    recycle_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO recycling_record
            (id, location_id, material_type, quantity_kg, destination,
             revenue, notes, metadata, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'draft')
        RETURNING id
        """,
        (
            recycle_id, location_id, material_type, quantity_kg, destination,
            revenue, notes, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.info("Recorded recycling %s: %s %s kg to %s", recycle_id, material_type, quantity_kg, destination)

    return {
        "recycle_id": recycle_id,
        "location_id": location_id,
        "material_type": material_type,
        "quantity_kg": quantity_kg,
        "destination": destination,
        "revenue": revenue,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# Pollution Incident Reporting
# ============================================================

def report_incident(
    conn,
    location_id: str,
    incident_type: str,
    severity: str,
    description: str,
    affected_area: str,
    reported_by: str = None,
    metadata: dict = None,
) -> dict:
    """Report a pollution incident."""
    cur = conn.cursor()
    incident_id = str(uuid.uuid4())

    cur.execute(
        """
        INSERT INTO pollution_incident
            (id, location_id, incident_type, severity, description,
             affected_area, reported_by, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'open', %s::jsonb)
        RETURNING id
        """,
        (
            incident_id, location_id, incident_type, severity, description,
            affected_area, reported_by, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    cur.close()

    logger.warning("Pollution incident reported %s: %s [%s]", incident_id, incident_type, severity)

    return {
        "incident_id": incident_id,
        "location_id": location_id,
        "incident_type": incident_type,
        "severity": severity,
        "description": description,
        "affected_area": affected_area,
        "status": "open",
        "reported_at": datetime.now(timezone.utc).isoformat(),
    }


def resolve_incident(
    conn,
    incident_id: str,
    remedial_action: str,
    resolution_date: str = None,
) -> dict:
    """Mark a pollution incident as resolved."""
    cur = conn.cursor()
    res_date = date.fromisoformat(resolution_date) if resolution_date else date.today()

    cur.execute(
        """
        UPDATE pollution_incident
        SET status = 'resolved',
            remedial_action = %s,
            resolution_date = %s,
            resolved_at = NOW()
        WHERE id = %s
        RETURNING id, incident_type, severity
        """,
        (remedial_action, res_date, incident_id),
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        raise ValueError(f"Incident {incident_id} not found")

    conn.commit()
    cur.close()

    logger.info("Incident %s resolved: %s", incident_id, remedial_action)

    return {
        "incident_id": row[0],
        "incident_type": row[1],
        "severity": row[2],
        "status": "resolved",
        "remedial_action": remedial_action,
        "resolution_date": res_date.isoformat(),
    }


# ============================================================
# Waste Summary
# ============================================================

def get_waste_summary(conn, location_id: str, days: int = 30) -> dict:
    """Get waste totals by type and disposal method."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT waste_type,
               SUM(quantity_kg) AS total_kg,
               COUNT(*) AS record_count
        FROM waste_stream_record
        WHERE location_id = %s
          AND recorded_at >= NOW() - INTERVAL '%s days'
          AND status IN ('verified', 'published')
        GROUP BY waste_type
        ORDER BY total_kg DESC
        """,
        (location_id, days),
    )
    cols = [d[0] for d in cur.description]
    by_type = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT disposal_method,
               SUM(quantity_kg) AS total_kg,
               COUNT(*) AS record_count
        FROM waste_stream_record
        WHERE location_id = %s
          AND recorded_at >= NOW() - INTERVAL '%s days'
          AND status IN ('verified', 'published')
        GROUP BY disposal_method
        ORDER BY total_kg DESC
        """,
        (location_id, days),
    )
    cols = [d[0] for d in cur.description]
    by_disposal = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT SUM(quantity_kg), COUNT(*)
        FROM waste_stream_record
        WHERE location_id = %s
          AND recorded_at >= NOW() - INTERVAL '%s days'
          AND status IN ('verified', 'published')
        """,
        (location_id, days),
    )
    total_row = cur.fetchone()
    cur.close()

    return {
        "location_id": location_id,
        "period_days": days,
        "total_waste_kg": float(total_row[0]) if total_row[0] else 0,
        "total_records": int(total_row[1]) if total_row[1] else 0,
        "by_type": by_type,
        "by_disposal_method": by_disposal,
    }


# ============================================================
# Composting Efficiency
# ============================================================

def get_composting_efficiency(conn, location_id: str) -> dict:
    """Get composting yield and quality trends."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT compost_method,
               COUNT(*) AS batches,
               AVG(output_yield_pct) AS avg_yield_pct,
               AVG(feedstock_kg) AS avg_feedstock_kg,
               AVG(output_kg) AS avg_output_kg,
               AVG(duration_days) AS avg_duration_days
        FROM composting_record
        WHERE location_id = %s
          AND status IN ('verified', 'published')
          AND output_kg IS NOT NULL
        GROUP BY compost_method
        ORDER BY batches DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    by_method = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT ph, moisture_pct, temperature_c, output_yield_pct,
               recorded_at
        FROM composting_record
        WHERE location_id = %s
          AND status IN ('verified', 'published')
        ORDER BY recorded_at DESC LIMIT 10
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    recent_quality = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT COUNT(*), SUM(feedstock_kg), SUM(output_kg)
        FROM composting_record
        WHERE location_id = %s
          AND status IN ('verified', 'published')
        """,
        (location_id,),
    )
    total_row = cur.fetchone()
    cur.close()

    overall_yield_pct = None
    if total_row[1] and total_row[2] and float(total_row[1]) > 0:
        overall_yield_pct = round(float(total_row[2]) / float(total_row[1]) * 100, 1)

    return {
        "location_id": location_id,
        "total_batches": int(total_row[0]) if total_row[0] else 0,
        "total_feedstock_kg": float(total_row[1]) if total_row[1] else 0,
        "total_output_kg": float(total_row[2]) if total_row[2] else 0,
        "overall_yield_pct": overall_yield_pct,
        "by_method": by_method,
        "recent_quality": recent_quality,
    }


# ============================================================
# Open Incidents
# ============================================================

def get_open_incidents(conn, location_id: str) -> dict:
    """Get unresolved pollution incidents."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, incident_type, severity, description, affected_area,
               reported_by, created_at
        FROM pollution_incident
        WHERE location_id = %s AND status = 'open'
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END,
            created_at DESC
        """,
        (location_id,),
    )
    cols = [d[0] for d in cur.description]
    open_incidents = [dict(zip(cols, row)) for row in cur.fetchall()]

    cur.execute(
        """
        SELECT severity, COUNT(*)
        FROM pollution_incident
        WHERE location_id = %s AND status = 'open'
        GROUP BY severity
        """,
        (location_id,),
    )
    severity_counts = {row[0]: int(row[1]) for row in cur.fetchall()}

    cur.execute(
        """
        SELECT COUNT(*)
        FROM pollution_incident
        WHERE location_id = %s AND status = 'resolved'
        """,
        (location_id,),
    )
    resolved_row = cur.fetchone()
    cur.close()

    return {
        "location_id": location_id,
        "open_count": len(open_incidents),
        "resolved_count": int(resolved_row[0]) if resolved_row[0] else 0,
        "severity_breakdown": severity_counts,
        "incidents": open_incidents,
    }


# ============================================================
# Dashboard
# ============================================================

def get_waste_dashboard(conn, location_id: str) -> dict:
    """Dashboard combining waste, composting, and incident data."""
    waste = get_waste_summary(conn, location_id, days=30)
    composting = get_composting_efficiency(conn, location_id)
    incidents = get_open_incidents(conn, location_id)

    total_waste = waste["total_waste_kg"]
    recycled_kg = sum(
        d["total_kg"] for d in waste["by_disposal_method"]
        if d.get("disposal_method") in ("recycling", "recycled")
    )
    composted_kg = sum(
        d["total_kg"] for d in waste["by_disposal_method"]
        if d.get("disposal_method") in ("composting", "composted")
    )
    landfill_kg = sum(
        d["total_kg"] for d in waste["by_disposal_method"]
        if d.get("disposal_method") in ("landfill", "dump")
    )

    diversion_rate = None
    if total_waste > 0:
        diverted = recycled_kg + composted_kg
        diversion_rate = round(diverted / total_waste * 100, 1)

    return {
        "location_id": location_id,
        "waste_summary": waste,
        "composting_efficiency": composting,
        "incidents": incidents,
        "key_metrics": {
            "total_waste_kg": total_waste,
            "recycled_kg": recycled_kg,
            "composted_kg": composted_kg,
            "landfill_kg": landfill_kg,
            "diversion_rate_pct": diversion_rate,
            "composting_batches": composting["total_batches"],
            "composting_yield_pct": composting["overall_yield_pct"],
            "open_incidents": incidents["open_count"],
            "critical_incidents": incidents["severity_breakdown"].get("critical", 0),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# CLI
# ============================================================

cli = CommandLine("waste_management", "Waste management")


def _render(result, args, human):
    print(json.dumps(result, indent=2, default=str) if args.json else human(result))


def _cmd_record_waste(db, a):
    return record_waste(
        db, a.location_id, a.waste_type, a.waste_name,
        a.quantity, a.disposal_method, source=a.source, notes=a.notes,
    )


def _cmd_record_composting(db, a):
    return record_composting(
        db, a.location_id, a.feedstock, a.feedstock_kg, a.method,
        duration_days=a.duration, output_kg=a.output_kg,
        temperature_c=a.temperature, ph=a.ph, moisture_pct=a.moisture,
        notes=a.notes,
    )


def _cmd_record_recycling(db, a):
    return record_recycling(
        db, a.location_id, a.material, a.quantity,
        a.destination, revenue=a.revenue, notes=a.notes,
    )


def _cmd_report_incident(db, a):
    return report_incident(
        db, a.location_id, a.incident_type, a.severity,
        a.description, a.affected_area, reported_by=a.reported_by,
    )


def _cmd_resolve_incident(db, a):
    return resolve_incident(
        db, a.incident_id, a.remedial_action,
        resolution_date=a.resolution_date,
    )


cli.subcommand("record-waste", "Record waste stream") \
    .add("--location-id", required=True) \
    .add("--waste-type", required=True, help="organic, plastic, metal, chemical, electronic, other") \
    .add("--waste-name", required=True) \
    .add("--quantity", type=float, required=True, help="Quantity in kg") \
    .add("--disposal-method", required=True, help="composting, recycling, landfill, incineration") \
    .add("--source") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_waste) \
    .render_with(lambda r, a: _render(r, a, _format_waste_record))

cli.subcommand("record-composting", "Record composting operation") \
    .add("--location-id", required=True) \
    .add("--feedstock", required=True, help="Feedstock type description") \
    .add("--feedstock-kg", type=float, required=True) \
    .add("--method", required=True, help="vermicomposting, aerobic, anaerobic, bokashi") \
    .add("--duration", type=int, help="Duration in days") \
    .add("--output-kg", type=float, help="Output in kg") \
    .add("--temperature", type=float, help="Temperature in C") \
    .add("--ph", type=float) \
    .add("--moisture", type=float, help="Moisture percentage") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_composting) \
    .render_with(lambda r, a: _render(r, a, _format_composting_record))

cli.subcommand("record-recycling", "Record recycling activity") \
    .add("--location-id", required=True) \
    .add("--material", required=True, help="plastic, glass, metal, paper, organic") \
    .add("--quantity", type=float, required=True, help="Quantity in kg") \
    .add("--destination", required=True) \
    .add("--revenue", type=float) \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_recycling) \
    .render_with(lambda r, a: _render(r, a, _format_recycling_record))

cli.subcommand("report-incident", "Report pollution incident") \
    .add("--location-id", required=True) \
    .add("--incident-type", required=True, help="chemical_spill, water_contamination, soil_contamination, air_pollution, waste_dumping") \
    .add("--severity", required=True, choices=["low", "medium", "high", "critical"]) \
    .add("--description", required=True) \
    .add("--affected-area", required=True) \
    .add("--reported-by") \
    .add("--json", action="store_true") \
    .run(_cmd_report_incident) \
    .render_with(lambda r, a: _render(r, a, _format_incident))

cli.subcommand("resolve-incident", "Resolve pollution incident") \
    .add("--incident-id", required=True) \
    .add("--remedial-action", required=True) \
    .add("--resolution-date", help="YYYY-MM-DD") \
    .add("--json", action="store_true") \
    .run(_cmd_resolve_incident) \
    .render_with(lambda r, a: _render(r, a, _format_resolve))

cli.subcommand("waste-summary", "Waste totals by type and disposal") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=30) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_waste_summary(db, a.location_id, days=a.days)) \
    .render_with(lambda r, a: _render(r, a, _format_waste_summary))

cli.subcommand("composting-efficiency", "Composting yield and quality") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_composting_efficiency(db, a.location_id)) \
    .render_with(lambda r, a: _render(r, a, _format_composting_efficiency))

cli.subcommand("open-incidents", "Unresolved pollution incidents") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_open_incidents(db, a.location_id)) \
    .render_with(lambda r, a: _render(r, a, _format_open_incidents))

cli.subcommand("dashboard", "Waste management dashboard") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_waste_dashboard(db, a.location_id)) \
    .render_with(lambda r, a: _render(r, a, _format_dashboard))


def main(argv=None):
    cli.run(argv)


# ============================================================
# Formatters
# ============================================================

def _format_waste_record(r: dict) -> str:
    return f"Recorded waste: {r['waste_name']} ({r['waste_type']}) {r['quantity_kg']} kg → {r['disposal_method']}"


def _format_composting_record(r: dict) -> str:
    yield_str = f" → {r['output_kg']} kg ({r['output_yield_pct']}%)" if r.get("output_kg") else ""
    return f"Recorded composting: {r['feedstock_type']} {r['feedstock_kg']} kg via {r['compost_method']}{yield_str}"


def _format_recycling_record(r: dict) -> str:
    rev_str = f", revenue ${r['revenue']:.2f}" if r.get("revenue") is not None else ""
    return f"Recorded recycling: {r['material_type']} {r['quantity_kg']} kg → {r['destination']}{rev_str}"


def _format_incident(r: dict) -> str:
    return f"Incident reported [{r['severity'].upper()}]: {r['incident_type']} — {r['affected_area']}"


def _format_resolve(r: dict) -> str:
    return f"Incident {r['incident_id'][:8]}... resolved: {r['remedial_action']}"


def _format_waste_summary(r: dict) -> str:
    lines = [f"Waste Summary — {r['location_id'][:8]}... ({r['period_days']}d) — total {r['total_waste_kg']:.1f} kg ({r['total_records']} records)"]
    for t in r["by_type"]:
        lines.append(f"  {t['waste_type']:20s} {t['total_kg']:8.1f} kg  ({t['record_count']} records)")
    lines.append("  Disposal:")
    for d in r["by_disposal_method"]:
        lines.append(f"    {d['disposal_method']:18s} {d['total_kg']:8.1f} kg")
    return "\n".join(lines)


def _format_composting_efficiency(r: dict) -> str:
    lines = [f"Composting Efficiency — {r['location_id'][:8]}... ({r['total_batches']} batches)"]
    if r.get("overall_yield_pct"):
        lines.append(f"  Overall yield: {r['overall_yield_pct']}%")
    for m in r["by_method"]:
        lines.append(f"  {m['compost_method']:20s} batches={m['batches']}  avg_yield={m['avg_yield_pct'] or 'N/A'}%  avg_feed={m['avg_feedstock_kg'] or 0:.0f} kg")
    return "\n".join(lines)


def _format_open_incidents(r: dict) -> str:
    lines = [f"Open Incidents — {r['location_id'][:8]}... ({r['open_count']} open, {r['resolved_count']} resolved)"]
    for inc in r["incidents"]:
        lines.append(f"  [{inc['severity'].upper():8s}] {inc['incident_type']}: {inc['description'][:60]}")
    if not r["incidents"]:
        lines.append("  No open incidents.")
    return "\n".join(lines)


def _format_dashboard(r: dict) -> str:
    km = r["key_metrics"]
    lines = [
        f"Waste Dashboard — {r['location_id'][:8]}...",
        f"  Waste: {km['total_waste_kg']:.1f} kg total | {km['recycled_kg']:.1f} recycled | {km['composted_kg']:.1f} composted | {km['landfill_kg']:.1f} landfill",
        f"  Diversion rate: {km['diversion_rate_pct'] or 'N/A'}%",
        f"  Composting: {km['composting_batches']} batches | yield {km['composting_yield_pct'] or 'N/A'}%",
        f"  Incidents: {km['open_incidents']} open ({km['critical_incidents']} critical)",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
