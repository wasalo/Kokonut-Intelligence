"""Crop rotation planning CLI.

Extracted from services.analytics.crop_rotation so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_crop_rotation --help
"""

from ..common.commands import CommandLine
from .crop_rotation import (
    add_slot,
    create_plan,
    record_impact,
)

# ============================================================
# CLI
# ============================================================

cli = CommandLine("crop_rotation", "Crop rotation planning")


def _render(result, args, human):
    print(json.dumps(result, indent=2, default=str) if args.json else human(result))


def _cmd_record_impact(db, a):
    rd = date.fromisoformat(a.date) if a.date else None
    return record_impact(
        db, plan_id=a.plan_id, slot_id=a.slot_id, location_id=a.location_id,
        impact_type=a.impact_type, impact_direction=a.direction,
        severity_pct=a.severity, measurement_value=a.value,
        measurement_unit=a.unit, record_date=rd, notes=a.notes,
    )


def _cmd_create_plan(db, a):
    return create_plan(
        db, a.location_id, a.name,
        plot_id=a.plot_id, zone_id=a.zone_id,
        duration_seasons=a.duration, start_season=a.start_season,
        notes=a.notes,
    )


def _cmd_add_slot(db, a):
    return add_slot(
        db, a.plan_id, a.season, a.crop,
        purpose=a.purpose, expected_area_ha=a.area,
        season_name=a.season_name, notes=a.notes,
    )


cli.subcommand("create-plan", "Create rotation plan") \
    .add("--location-id", required=True) \
    .add("--name", required=True) \
    .add("--plot-id") \
    .add("--zone-id") \
    .add("--duration", type=int, default=4, help="Duration in seasons") \
    .add("--start-season", help="Starting season label") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_create_plan) \
    .render_with(lambda r, a: _render(r, a, _format_plan_created))

cli.subcommand("add-slot", "Add season slot") \
    .add("--plan-id", required=True) \
    .add("--season", type=int, required=True, help="Season number") \
    .add("--crop", required=True) \
    .add("--purpose", choices=["cash_crop", "cover_crop", "nitrogen_fixer", "green_manure", "break_crop"]) \
    .add("--area", type=float, help="Expected area in hectares") \
    .add("--season-name", help="Season name label") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_add_slot) \
    .render_with(lambda r, a: _render(r, a, _format_slot_added))

cli.subcommand("get-plan", "Get plan with crop sequence") \
    .add("--plan-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_plan(db, a.plan_id)) \
    .render_with(lambda r, a: _render(r, a, _format_plan))

cli.subcommand("list-plans", "List rotation plans") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: list_plans(db, a.location_id)) \
    .render_with(lambda r, a: _render(r, a, _format_plan_list))

cli.subcommand("record-impact", "Record rotation impact") \
    .add("--plan-id") \
    .add("--slot-id") \
    .add("--location-id") \
    .add("--type", dest="impact_type", default="soil_health",
         choices=["disease_pressure", "pest_pressure", "soil_health", "yield_effect", "weed_pressure"]) \
    .add("--direction", default="positive", choices=["positive", "neutral", "negative"]) \
    .add("--severity", type=float, help="Severity percentage") \
    .add("--value", type=float, help="Measurement value") \
    .add("--unit", help="Measurement unit") \
    .add("--date", help="Record date YYYY-MM-DD") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_impact) \
    .render_with(lambda r, a: _render(r, a, _format_impact_recorded))

cli.subcommand("impact-summary", "Impact summary") \
    .add("--plan-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_impact_summary(db, a.plan_id)) \
    .render_with(lambda r, a: _render(r, a, _format_impact_summary))

cli.subcommand("family-usage", "Crop family usage") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_crop_family_usage(db, a.location_id)) \
    .render_with(lambda r, a: _render(r, a, _format_family_usage))

cli.subcommand("recommend", "Recommend rotation") \
    .add("--location-id", required=True) \
    .add("--plot-id") \
    .add("--json", action="store_true") \
    .run(lambda db, a: recommend_rotation(db, a.location_id, a.plot_id)) \
    .render_with(lambda r, a: _render(r, a, _format_recommendation))

cli.subcommand("validate", "Validate plan") \
    .add("--plan-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: validate_plan(db, a.plan_id)) \
    .render_with(lambda r, a: _render(r, a, _format_validation))

cli.subcommand("dashboard", "Rotation dashboard") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_rotation_dashboard(db, a.location_id)) \
    .render_with(lambda r, a: _render(r, a, _format_dashboard))


def main(argv=None):
    cli.run(argv)


def _format_plan_created(r: dict) -> str:
    return f"Created rotation plan: {r['plan_name']} ({r['plan_id'][:8]}...) — {r['duration_seasons']} seasons, status: {r['status']}"


def _format_slot_added(r: dict) -> str:
    fam = r.get("crop_family_id", "—")
    return f"Added season {r['season_number']}: {r['crop_name']} (family {fam[:8] if fam else '—'}...) purpose={r['purpose'] or '—'}"


def _format_plan(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    lines = [
        f"Rotation Plan — {r['plan_name']} ({r['status']})",
        f"  Location: {r['location_id'][:8]}...  Plot: {r['plot_id'][:8] if r['plot_id'] else '—'}...",
        f"  Duration: {r['duration_seasons']} seasons  Start: {r['start_season'] or '—'}",
        f"  Slots: {r['filled_slots']}/{r['duration_seasons']}",
    ]
    if r["crop_sequence"]:
        lines.append(f"  Sequence: {' → '.join(r['crop_sequence'])}")
    if r["family_sequence"]:
        lines.append(f"  Families: {' → '.join(r['family_sequence'])}")
    for s in r.get("slots", []):
        lines.append(f"    S{s['season_number']}: {s['crop_name']} ({s['family_name'] or '?'}) — {s['purpose'] or '—'}")
    return "\n".join(lines)


def _format_plan_list(r: dict) -> str:
    lines = [f"Rotation Plans — {r['total']} total"]
    for p in r["plans"]:
        lines.append(f"  {p['plan_name']:30s} [{p['status']:10s}] {p['slot_count']} slots  {p['id'][:8]}...")
    return "\n".join(lines) if r["plans"] else "No rotation plans."


def _format_impact_recorded(r: dict) -> str:
    return f"Recorded impact: {r['impact_type']}/{r['impact_direction']} severity={r['severity_pct'] or '—'}% ({r['record_date']})"


def _format_impact_summary(r: dict) -> str:
    lines = [f"Impact Summary — plan {r['plan_id'][:8]}... ({r['total_records']} records, {r['positive_count']} positive, {r['negative_count']} negative)"]
    for imp in r["impacts_by_type"]:
        lines.append(f"  {imp['impact_type']:20s} {imp['impact_direction']:10s} n={imp['record_count']} avg_sev={imp['avg_severity'] or '—'}%")
    return "\n".join(lines) if r["impacts_by_type"] else "No impact records."


def _format_family_usage(r: dict) -> str:
    lines = [f"Crop Family Usage — {r['families_used']} families used"]
    for d in r["family_distribution"]:
        lines.append(f"  {d['family_name']:25s} {d['total_slots']} slots across {d['plan_count']} plan(s)")
    return "\n".join(lines) if r["family_distribution"] else "No family data."


def _format_recommendation(r: dict) -> str:
    lines = [
        f"Rotation Recommendations — {r['location_id'][:8]}...",
        f"  History crops: {r['history_crops']}  Overused families: {', '.join(r['overused_families']) or 'none'}",
        f"  Unused families: {', '.join(r['unused_families']) or 'none'}",
    ]
    for rec in r["recommendations"][:5]:
        marker = "!!" if rec["is_overused"] else "  "
        lines.append(f"  {marker} {rec['recommended_crop']:20s} ({rec['family_name']}) conf={rec['confidence_score']:.1f} — {rec['reason']}")
    return "\n".join(lines)


def _format_validation(r: dict) -> str:
    if "error" in r:
        return f"Error: {r['error']}"
    status = "VALID" if r["valid"] else "INVALID"
    lines = [f"Validation — plan {r['plan_id'][:8]}... [{status}] score={r['score_pct']}% ({r['checks_passed']}/{r['total_checks']})"]
    for issue in r["issues"]:
        lines.append(f"  FAIL: {issue['check']} — {issue.get('details', '')}")
    for warn in r["warnings"]:
        lines.append(f"  WARN: {warn['check']} — {warn['message']}")
    return "\n".join(lines)


def _format_dashboard(r: dict) -> str:
    s = r["summary"]
    lines = [
        f"Rotation Dashboard — {r['location_id'][:8]}...",
        f"  Plans: {s['total_plans']} total ({s['active_plans']} active, {s['draft_plans']} draft, {s['completed_plans']} completed)",
        f"  Families used: {s['unique_families']}",
    ]
    for p in r["plans"]:
        lines.append(f"    {p['plan_name']:30s} [{p['status']}] {p['slot_count']} slots")
    for imp in r["impacts_by_type"]:
        lines.append(f"  {imp['impact_type']:20s} {imp['impact_direction']:10s} n={imp['cnt']} avg={imp['avg_severity'] or '—'}%")
    for f in r["family_diversity"]:
        lines.append(f"  {f['family_name']:25s} {f['slot_count']} slots")
    return "\n".join(lines)


if __name__ == "__main__":
    main()

