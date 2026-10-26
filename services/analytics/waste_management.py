#!/usr/bin/env python3
"""
Waste Management

Records waste streams, composting operations, recycling activities,
and pollution incidents. Provides summaries, efficiency metrics, and dashboards.

Usage:
    python -m services.analytics.waste_management record-waste --location-id UUID (retired; use the authenticated Gateway console)
    python -m services.analytics.waste_management record-composting --location-id UUID (retired; use the authenticated Gateway console)
    python -m services.analytics.waste_management record-recycling --location-id UUID (retired; use the authenticated Gateway console)
    python -m services.analytics.waste_management report-incident --location-id UUID (retired; use the authenticated Gateway console)
    python -m services.analytics.waste_management resolve-incident --incident-id UUID (retired; use the authenticated Gateway console)
    python -m services.analytics.waste_management waste-summary --location-id UUID (retired; use the authenticated Gateway)
    python -m services.analytics.waste_management composting-efficiency --location-id UUID (retired; use the authenticated Gateway)
    python -m services.analytics.waste_management open-incidents --location-id UUID (retired; use authenticated Gateway review)
    python -m services.analytics.waste_management dashboard --location-id UUID
"""

import json

from services.common.commands import CommandLine
from services.common.tenant_context import TenantContextDenied

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
    """Reject legacy direct writes that lack authenticated tenant context.

    The location argument is caller-selected and is not authorization. New
    waste-stream captures must use the Gateway path, which installs signed
    operator context and checks the current exact-location create grant in
    PostgreSQL.
    """
    del conn, location_id, waste_type, waste_name, quantity_kg, disposal_method
    del source, notes, metadata
    raise TenantContextDenied(
        "Unscoped waste writes are disabled; use the authenticated operator "
        "Gateway waste-capture workflow"
    )


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
    """Reject legacy direct writes that lack authenticated tenant context.

    Use the authenticated Gateway composting capture path, which verifies the
    exact current location grant and records a new batch without quality review.
    """
    del conn, location_id, feedstock_type, feedstock_kg, compost_method
    del duration_days, output_kg, temperature_c, ph, moisture_pct, notes, metadata
    raise TenantContextDenied(
        "Unscoped composting writes are disabled; use the authenticated operator "
        "Gateway composting-capture workflow"
    )


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
    """Reject recycling writes that lack authenticated tenant context."""
    del conn, location_id, material_type, quantity_kg, destination, revenue, notes, metadata
    raise TenantContextDenied(
        "Unscoped recycling writes are disabled; use the authenticated operator "
        "Gateway recycling-capture workflow"
    )


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
    """Reject reports that lack authenticated tenant context."""
    del conn, location_id, incident_type, severity, description, affected_area
    del reported_by, metadata
    raise TenantContextDenied(
        "Unscoped incident reports are disabled; use the authenticated operator "
        "Gateway incident-capture workflow"
    )


def resolve_incident(
    conn,
    incident_id: str,
    remedial_action: str,
    resolution_date: str = None,
) -> dict:
    """Reject resolution writes that lack authenticated review context."""
    del conn, incident_id, remedial_action, resolution_date
    raise TenantContextDenied(
        "Unscoped incident resolution is disabled; use the authenticated operator "
        "Gateway review workflow"
    )


# ============================================================
# Waste Summary
# ============================================================

def get_waste_summary(conn, location_id: str, days: int = 30) -> dict:
    """Reject location-argument-only reads without authenticated tenant context."""
    del conn, location_id, days
    raise TenantContextDenied(
        "Unscoped waste summaries are disabled; use the authenticated operator "
        "Gateway waste summary"
    )


# ============================================================
# Composting Efficiency
# ============================================================

def get_composting_efficiency(conn, location_id: str) -> dict:
    """Reject location-argument-only reads without authenticated tenant context."""
    del conn, location_id
    raise TenantContextDenied(
        "Unscoped composting summaries are disabled; use the authenticated operator "
        "Gateway waste summary"
    )


# ============================================================
# Open Incidents
# ============================================================

def get_open_incidents(conn, location_id: str) -> dict:
    """Reject unscoped incident-detail reads before database access."""
    del conn, location_id
    raise TenantContextDenied(
        "Unscoped incident review is disabled; use the authenticated operator Gateway"
    )


# ============================================================
# Dashboard
# ============================================================

def get_waste_dashboard(conn, location_id: str) -> dict:
    """Reject the legacy mixed-scope dashboard before database access."""
    del conn, location_id
    raise TenantContextDenied(
        "Unscoped waste dashboard is disabled; use the authenticated operator Gateway"
    )


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


cli.subcommand("record-waste", "Retired unscoped writer; use the authenticated Gateway") \
    .add("--location-id", required=True) \
    .add("--waste-type", required=True, help="organic, plastic, metal, chemical, electronic, other") \
    .add("--waste-name", required=True) \
    .add("--quantity", type=float, required=True, help="Quantity in kg") \
    .add("--disposal-method", required=True, help="composting, recycling, landfill, incineration") \
    .add("--source") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_waste, needs_db=False) \
    .render_with(lambda r, a: _render(r, a, _format_waste_record))

cli.subcommand("record-composting", "Retired unscoped writer; use the authenticated Gateway") \
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
    .run(_cmd_record_composting, needs_db=False) \
    .render_with(lambda r, a: _render(r, a, _format_composting_record))

cli.subcommand("record-recycling", "Retired unscoped writer; use the authenticated Gateway") \
    .add("--location-id", required=True) \
    .add("--material", required=True, help="plastic, glass, metal, paper, organic") \
    .add("--quantity", type=float, required=True, help="Quantity in kg") \
    .add("--destination", required=True) \
    .add("--revenue", type=float) \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_recycling, needs_db=False) \
    .render_with(lambda r, a: _render(r, a, _format_recycling_record))

cli.subcommand("report-incident", "Retired unscoped writer; use the authenticated Gateway") \
    .add("--location-id", required=True) \
    .add("--incident-type", required=True, help="chemical_spill, water_contamination, soil_contamination, air_pollution, waste_dumping") \
    .add("--severity", required=True, choices=["low", "medium", "high", "critical"]) \
    .add("--description", required=True) \
    .add("--affected-area", required=True) \
    .add("--reported-by") \
    .add("--json", action="store_true") \
    .run(_cmd_report_incident, needs_db=False) \
    .render_with(lambda r, a: _render(r, a, _format_incident))

cli.subcommand("resolve-incident", "Retired unscoped writer; use the authenticated Gateway") \
    .add("--incident-id", required=True) \
    .add("--remedial-action", required=True) \
    .add("--resolution-date", help="YYYY-MM-DD") \
    .add("--json", action="store_true") \
    .run(_cmd_resolve_incident, needs_db=False) \
    .render_with(lambda r, a: _render(r, a, _format_resolve))

cli.subcommand("waste-summary", "Retired unscoped read; use the authenticated Gateway") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=30) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_waste_summary(db, a.location_id, days=a.days), needs_db=False) \
    .render_with(lambda r, a: _render(r, a, _format_waste_summary))

cli.subcommand("composting-efficiency", "Retired unscoped read; use the authenticated Gateway") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_composting_efficiency(db, a.location_id), needs_db=False) \
    .render_with(lambda r, a: _render(r, a, _format_composting_efficiency))

cli.subcommand("open-incidents", "Retired unscoped read; use the authenticated Gateway") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_open_incidents(db, a.location_id), needs_db=False) \
    .render_with(lambda r, a: _render(r, a, _format_open_incidents))

cli.subcommand("dashboard", "Retired unscoped dashboard; use the authenticated Gateway") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_waste_dashboard(db, a.location_id), needs_db=False) \
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
