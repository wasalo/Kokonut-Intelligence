"""Energy monitoring CLI.

Extracted from services.analytics.energy_monitoring so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_energy_monitoring --help
"""

import json
from datetime import date

from ..common.commands import CommandLine
from .energy_monitoring import (
    add_renewable,
    add_source,
    compute_carbon_intensity,
    get_consumption,
    get_cost_analysis,
    get_efficiency,
    get_energy_dashboard,
    get_renewable_summary,
    record_reading,
)

# ============================================================
# CLI
# ============================================================

cli = CommandLine("energy_monitoring", "Energy monitoring")


def _render(result, args, human):
    print(json.dumps(result, indent=2, default=str) if args.json else human(result))


def _cmd_add_source(db, a):
    inst = date.fromisoformat(a.installation_date) if a.installation_date else None
    return add_source(
        db, a.location_id, a.name, a.source_type,
        capacity_kw=a.capacity, installation_date=inst,
    )


def _cmd_record_reading(db, a):
    rd = date.fromisoformat(a.date) if a.date else date.today()
    return record_reading(
        db, a.source_id, rd, a.reading_type, a.kwh,
        cost_per_kwh=a.cost_per_kwh, activity_type=a.activity_type,
        equipment_id=a.equipment_id, notes=a.notes,
    )


def _cmd_add_renewable(db, a):
    return add_renewable(
        db, a.location_id, a.source_id, a.renewable_type,
        a.rated_capacity_kw, annual_generation_kwh=a.annual_generation,
        carbon_offset_kg=a.carbon_offset,
    )


cli.subcommand("add-source", "Add energy source") \
    .add("--location-id", required=True) \
    .add("--name", required=True) \
    .add("--type", required=True, dest="source_type",
         choices=["grid", "diesel_generator", "solar", "wind", "biogas", "biomass", "battery"]) \
    .add("--capacity", type=float, help="Capacity in kW") \
    .add("--installation-date", help="YYYY-MM-DD") \
    .add("--json", action="store_true") \
    .run(_cmd_add_source) \
    .render_with(lambda r, a: _render(r, a, _format_source))

cli.subcommand("record", "Record energy reading") \
    .add("--source-id", required=True) \
    .add("--date", default=None, help="Reading date YYYY-MM-DD") \
    .add("--type", required=True, dest="reading_type",
         choices=["consumption", "production"]) \
    .add("--kwh", type=float, required=True) \
    .add("--cost", type=float, dest="cost_per_kwh", help="Cost per kWh") \
    .add("--activity", dest="activity_type",
         choices=["irrigation", "processing", "storage", "lighting", "pump", "other"]) \
    .add("--equipment-id") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_reading) \
    .render_with(lambda r, a: _render(r, a, _format_reading))

cli.subcommand("consumption", "Consumption summary") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=30) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_consumption(db, a.location_id, a.days)) \
    .render_with(lambda r, a: _render(r, a, _format_consumption))

cli.subcommand("efficiency", "Efficiency metrics") \
    .add("--location-id", required=True) \
    .add("--period", default="daily", choices=["daily", "weekly", "monthly"]) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_efficiency(db, a.location_id, a.period)) \
    .render_with(lambda r, a: _render(r, a, _format_efficiency))

cli.subcommand("add-renewable", "Register renewable source") \
    .add("--location-id", required=True) \
    .add("--source-id", required=True) \
    .add("--renewable-type", required=True,
         choices=["solar_pv", "solar_thermal", "wind", "biogas", "micro_hydro"]) \
    .add("--capacity", type=float, required=True, dest="rated_capacity_kw") \
    .add("--annual-generation", type=float, help="Annual generation kWh") \
    .add("--carbon-offset", type=float, help="Carbon offset kg/year") \
    .add("--json", action="store_true") \
    .run(_cmd_add_renewable) \
    .render_with(lambda r, a: _render(r, a, _format_renewable))

cli.subcommand("renewable-summary", "Renewable energy summary") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_renewable_summary(db, a.location_id)) \
    .render_with(lambda r, a: _render(r, a, _format_renewable_summary))

cli.subcommand("dashboard", "Energy dashboard") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_energy_dashboard(db, a.location_id)) \
    .render_with(lambda r, a: _render(r, a, _format_dashboard))

cli.subcommand("carbon-intensity", "Compute carbon intensity") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: compute_carbon_intensity(db, a.location_id)) \
    .render_with(lambda r, a: _render(r, a, _format_carbon))

cli.subcommand("cost-analysis", "Energy cost analysis") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=30) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_cost_analysis(db, a.location_id, a.days)) \
    .render_with(lambda r, a: _render(r, a, _format_cost))


def main(argv=None):
    cli.run(argv)


# ============================================================
# Formatters
# ============================================================

def _format_source(r: dict) -> str:
    return f"Added source: {r['source_name']} ({r['source_type']}) {r['capacity_kw']} kW at {r['location_id'][:8]}..."


def _format_reading(r: dict) -> str:
    cost = f" @ ${r['cost_per_kwh']}/kWh = ${r['total_cost']}" if r['total_cost'] else ""
    return f"Recorded {r['reading_type']}: {r['kwh']} kWh{cost} ({r['reading_date']})"


def _format_consumption(r: dict) -> str:
    lines = [f"Consumption — {r['location_id'][:8]}... ({r['period_days']}d)"]
    lines.append(f"  Total: {r['total_kwh']:.1f} kWh  Cost: ${r['total_cost']:.2f}  Avg: ${r['avg_cost_per_kwh'] or 0:.4f}/kWh")
    for a in r["by_activity"]:
        act = a["activity_type"] or "unclassified"
        lines.append(f"  {act:15s}  {a['total_kwh']:8.1f} kWh  ${a['total_cost'] or 0:.2f}  ({a['readings']} readings)")
    return "\n".join(lines) if len(lines) > 1 else "No consumption data."


def _format_efficiency(r: dict) -> str:
    cm = r["current_metrics"]
    lines = [
        f"Efficiency — {r['location_id'][:8]}... ({r['period']})",
        f"  Consumption: {cm['total_consumption_kwh']:.1f} kWh",
        f"  Production:  {cm['total_production_kwh']:.1f} kWh",
        f"  Net:         {cm['net_energy_kwh']:.1f} kWh",
        f"  Renewable:   {cm['renewable_pct']:.1f}%",
    ]
    return "\n".join(lines)


def _format_renewable(r: dict) -> str:
    return (
        f"Renewable registered: {r['renewable_type']} ({r['rated_capacity_kw']} kW)\n"
        f"  Est. generation: {r['annual_generation_kwh']:.0f} kWh/year  Offset: {r['carbon_offset_kg']:.0f} kg CO2e/year"
    )


def _format_renewable_summary(r: dict) -> str:
    lines = [
        f"Renewable Summary — {r['location_id'][:8]}... ({r['active_sources']} sources)",
        f"  Capacity: {r['total_capacity_kw']:.1f} kW  Generation: {r['annual_generation_kwh']:.0f} kWh/year",
        f"  Carbon Offset: {r['total_carbon_offset_kg']:.0f} kg CO2e/year",
        f"  Renewable Share: {r['renewable_share_pct']:.1f}%",
    ]
    for s in r["sources"]:
        lines.append(f"    {s['renewable_type']:15s}  {s['rated_capacity_kw']:6.1f} kW  {s['annual_generation_kwh'] or 0:.0f} kWh/yr")
    return "\n".join(lines)


def _format_dashboard(r: dict) -> str:
    cons = r["consumption"]
    eff = r["efficiency"]
    ren = r["renewable"]
    lines = [
        f"Energy Dashboard — {r['location_id'][:8]}...",
        f"  Sources: {cons['sources_used']}  Readings: {cons['readings']}",
        f"  Total Consumption: {cons['total_kwh']:.1f} kWh  Cost: ${cons['total_cost']:.2f}",
        f"  Renewable Share: {ren['renewable_share_pct']:.1f}%",
        f"  Carbon Offset: {ren['total_carbon_offset_kg']:.0f} kg CO2e/year",
    ]
    for sb in r["source_breakdown"]:
        lines.append(f"    {sb['source_type']:20s}  {int(sb['count'])} sources  {sb['total_capacity']:.1f} kW")
    return "\n".join(lines)


def _format_carbon(r: dict) -> str:
    lines = [
        f"Carbon Intensity — {r['location_id'][:8]}... (30d)",
        f"  Intensity: {r['carbon_intensity_kg_co2e_kwh']:.4f} kg CO2e/kWh",
        f"  Total Emissions: {r['total_emissions_kg_co2e']:.1f} kg CO2e",
        f"  Renewable: {r['renewable_share_pct']:.1f}%",
        f"  Monthly Offset: {r['monthly_carbon_offset_kg']:.1f} kg",
        f"  Net Emissions: {r['net_monthly_emissions_kg']:.1f} kg CO2e/month",
    ]
    for b in r["breakdown"]:
        lines.append(f"    {b['source_type']:20s}  {b['consumption_kwh']:8.1f} kWh  {b['emissions_kg']:8.1f} kg CO2e")
    return "\n".join(lines)


def _format_cost(r: dict) -> str:
    lines = [
        f"Cost Analysis — {r['location_id'][:8]}... ({r['period_days']}d)",
        f"  Total: ${r['total_cost']:.2f}  ({r['total_kwh']:.1f} kWh @ ${r['avg_cost_per_kwh'] or 0:.4f}/kWh)",
        f"  Projected monthly: ${r['monthly_projected_cost']:.2f}",
    ]
    for a in r["by_activity"]:
        act = a["activity_type"] or "unclassified"
        lines.append(f"    {act:15s}  ${a['total_cost'] or 0:>8.2f}  {a['total_kwh']:8.1f} kWh")
    lines.append("  By source:")
    for s in r["by_source_type"]:
        lines.append(f"    {s['source_type']:20s}  ${s['total_cost'] or 0:>8.2f}  {s['total_kwh']:8.1f} kWh")
    return "\n".join(lines)


if __name__ == "__main__":
    main()

