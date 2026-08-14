"""Integrated Pest Management CLI.

Extracted from services.analytics.pest_management so the domain module stays
focused on queries/business logic. Reachable via:

    python -m services.analytics.cli_pest_management record-scouting --location-id UUID ...
"""

from datetime import date

from ..common.commands import CommandLine
from .pest_management import (
    add_mode_of_action,
    add_pest_crop_interaction,
    add_pest_reference,
    add_trap,
    check_rotation,
    check_threshold,
    check_trap_threshold,
    compute_ipm_compliance_score,
    compute_organic_pest_score,
    create_scouting_schedule,
    evaluate_intervention,
    generate_ipm_audit,
    get_degree_day_tracking,
    get_due_scouting,
    get_optimal_spray_windows,
    get_pest_crop_interactions,
    get_pest_dashboard,
    get_pest_reference,
    get_pest_summary,
    get_pesticide_usage,
    get_rotation_history,
    get_scouting_compliance,
    get_trap_trends,
    list_pest_references,
    recommend_intervention,
    recommend_management_for_crop,
    record_degree_day,
    record_intervention,
    record_pesticide_application,
    record_resistance,
    record_scouting,
    record_scouting_completion,
    record_trap_catch,
    schedule_re_scout,
    set_action_threshold,
)

# ============================================================
# CLI
# ============================================================

def _cmd_record_scouting(db, a):
    sd = date.fromisoformat(a.date) if a.date else None
    return record_scouting(
        db, a.location_id, a.pest,
        pest_type=a.pest_type, severity=a.severity,
        incidence_pct=a.incidence, damage_pct=a.damage,
        plot_id=a.plot_id, zone_id=a.zone_id,
        scout_date=sd, beneficial_observed=a.beneficials,
        notes=a.notes,
    )


def _cmd_set_threshold(db, a):
    return set_action_threshold(
        db, a.location_id, a.pest, crop_name=a.crop,
        economic_injury_level=a.eil, economic_threshold=a.et,
        threshold_unit=a.unit, notes=a.notes,
    )


def _cmd_check_threshold(db, a):
    return check_threshold(
        db, a.location_id, a.pest, crop_name=a.crop,
        current_count=a.count,
    )


def _cmd_record_intervention(db, a):
    idate = date.fromisoformat(a.date) if a.date else None
    return record_intervention(
        db, a.location_id, a.intervention_type,
        scouting_record_id=a.scouting_id,
        method_name=a.method, target_pest=a.target_pest,
        application_rate=a.rate, application_unit=a.unit,
        area_ha=a.area, cost=a.cost,
        notes=a.notes, intervention_date=idate,
    )


def _cmd_record_pesticide(db, a):
    adate = date.fromisoformat(a.date) if a.date else None
    return record_pesticide_application(
        db, a.location_id, a.product,
        active_ingredient=a.ingredient,
        chemical_class=a.chemical_class,
        application_rate=a.rate, rate_unit=a.rate_unit,
        area_ha=a.area, total_volume=a.volume,
        volume_unit=a.volume_unit, target_pest=a.target_pest,
        rei_days=a.rei, phi_days=a.phi,
        notes=a.notes, application_date=adate,
    )


def _cmd_record_resistance(db, a):
    odate = date.fromisoformat(a.date) if a.date else None
    return record_resistance(
        db, a.location_id, a.pest, a.chemical_class,
        a.level, observation_date=odate, notes=a.notes,
    )


def _cmd_record_degree_day(db, a):
    rdate = date.fromisoformat(a.date) if a.date else None
    return record_degree_day(
        db, a.location_id, a.pest,
        record_date=rdate, base_temp=a.base,
        max_temp=a.max_temp, min_temp=a.min_temp,
        upper_temp=a.upper, source=a.source,
    )


def _cmd_summary(db, a):
    return get_pest_summary(db, a.location_id)


def _cmd_pesticide_usage(db, a):
    return get_pesticide_usage(db, a.location_id, days=a.days)


def _cmd_degree_day_tracking(db, a):
    return get_degree_day_tracking(db, a.location_id, a.pest)


def _cmd_recommend(db, a):
    return recommend_intervention(db, a.scouting_id)


def _cmd_dashboard(db, a):
    return get_pest_dashboard(db, a.location_id)


def _cmd_add_reference(db, a):
    return add_pest_reference(
        db, a.pest, scientific_name=a.scientific_name,
        common_name=a.common_name, pest_category=a.pest_category,
        base_temp=a.base_temp, upper_temp=a.upper_temp,
        total_degree_days=a.total_degree_days,
        host_crops=a.hosts, importance=a.importance,
    )


def _cmd_get_reference(db, a):
    return get_pest_reference(db, a.pest)


def _cmd_list_references(db, a):
    return list_pest_references(
        db, pest_category=a.pest_category, host_crop=a.host_crop,
    )


def _cmd_create_schedule(db, a):
    sd = date.fromisoformat(a.start_date) if a.start_date else None
    ed = date.fromisoformat(a.end_date) if a.end_date else None
    return create_scouting_schedule(
        db, a.location_id, a.pest,
        frequency_days=a.frequency_days, crop_name=a.crop,
        method=a.method, sample_size=a.sample_size,
        assigned_to=a.assigned_to, start_date=sd, end_date=ed,
    )


def _cmd_due_scouting(db, a):
    return get_due_scouting(db, a.location_id)


def _cmd_record_compliance(db, a):
    sd = date.fromisoformat(a.scout_date) if a.scout_date else None
    return record_scouting_completion(
        db, a.schedule_id, a.scouting_id,
        scout_date=sd, notes=a.notes,
    )


def _cmd_compliance_report(db, a):
    return get_scouting_compliance(db, a.location_id, days=a.days)


def _cmd_schedule_re_scout(db, a):
    rsd = date.fromisoformat(a.re_scout_date)
    return schedule_re_scout(db, a.intervention_id, rsd)


def _cmd_evaluate_intervention(db, a):
    return evaluate_intervention(
        db, a.intervention_id, a.re_scout_record_id,
        a.effectiveness,
    )


def _cmd_compliance_score(db, a):
    ps = date.fromisoformat(a.period_start) if a.period_start else None
    pe = date.fromisoformat(a.period_end) if a.period_end else None
    return compute_ipm_compliance_score(db, a.location_id, ps, pe)


def _cmd_add_interaction(db, a):
    return add_pest_crop_interaction(
        db, a.pest, a.crop,
        damage_type=a.damage_type,
        yield_loss_potential=a.yield_loss_potential,
        peak_risk_stage=a.peak_stage,
        preferred_management=a.management,
    )


def _cmd_get_interactions(db, a):
    return get_pest_crop_interactions(
        db, crop_name=a.crop, pest_name=a.pest,
    )


def _cmd_recommend_for_crop(db, a):
    return recommend_management_for_crop(db, a.crop, a.stage)


def _cmd_add_trap(db, a):
    idate = date.fromisoformat(a.date) if a.date else None
    return add_trap(
        db, a.location_id, a.trap_name, a.trap_type,
        target_pest=a.target_pest, lure_type=a.lure,
        plot_id=a.plot_id, lat=a.lat, lon=a.lon,
        install_date=idate,
    )


def _cmd_record_catch(db, a):
    cd = date.fromisoformat(a.check_date) if a.check_date else None
    return record_trap_catch(
        db, a.trap_id, check_date=cd,
        pest_count=a.pest_count, bycatch_count=a.bycatch,
        beneficial_count=a.beneficial,
        trap_condition=a.condition, notes=a.notes,
    )


def _cmd_trap_trends(db, a):
    return get_trap_trends(db, a.trap_id, days=a.days)


def _cmd_check_trap_threshold(db, a):
    return check_trap_threshold(db, a.trap_id)


def _cmd_add_moa(db, a):
    return add_mode_of_action(
        db, a.chemical_class, a.moa_code, a.mode_of_action,
        irac_group=a.irac, frac_group=a.frac, hrac_group=a.hrac,
        cross_resistance=a.cross_resistance,
        rotation_compatibility=a.compatible,
    )


def _cmd_check_rotation(db, a):
    return check_rotation(
        db, a.location_id, a.chemical_class,
        min_days=a.min_days,
    )


def _cmd_rotation_history(db, a):
    return get_rotation_history(db, a.location_id, days=a.days)


def _cmd_spray_windows(db, a):
    return get_optimal_spray_windows(
        db, a.location_id, a.pest,
        days_ahead=a.days_ahead,
    )


def _cmd_organic_pest_score(db, a):
    ps = date.fromisoformat(a.period_start) if a.period_start else None
    pe = date.fromisoformat(a.period_end) if a.period_end else None
    return compute_organic_pest_score(db, a.location_id, ps, pe)


def _cmd_generate_audit(db, a):
    ps = date.fromisoformat(a.period_start) if a.period_start else None
    pe = date.fromisoformat(a.period_end) if a.period_end else None
    return generate_ipm_audit(db, a.location_id, ps, pe)


cli = CommandLine("pest_management", "Integrated Pest Management")

cli.subcommand("record-scouting", "Record scouting observation") \
    .add("--location-id", required=True) \
    .add("--pest", required=True) \
    .add("--type", dest="pest_type", choices=["insect", "weed", "disease", "nematode", "other"]) \
    .add("--severity", choices=["none", "low", "moderate", "high", "severe"]) \
    .add("--incidence", type=float, help="Incidence percentage") \
    .add("--damage", type=float, help="Damage percentage") \
    .add("--plot-id") \
    .add("--zone-id") \
    .add("--date", help="Scout date YYYY-MM-DD") \
    .add("--beneficials", help="Beneficial insects observed") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_scouting)

cli.subcommand("set-threshold", "Set action threshold") \
    .add("--location-id", required=True) \
    .add("--pest", required=True) \
    .add("--crop") \
    .add("--eil", type=float, help="Economic injury level") \
    .add("--et", type=float, help="Economic threshold") \
    .add("--unit", help="Threshold unit (per_plant, per_leaf, etc.)") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_set_threshold)

cli.subcommand("check-threshold", "Check threshold") \
    .add("--location-id", required=True) \
    .add("--pest", required=True) \
    .add("--crop") \
    .add("--count", type=float, required=True, help="Current pest count") \
    .add("--json", action="store_true") \
    .run(_cmd_check_threshold)

cli.subcommand("record-intervention", "Record intervention") \
    .add("--location-id", required=True) \
    .add("--scouting-id") \
    .add("--type", dest="intervention_type", required=True,
         choices=["biological", "cultural", "mechanical", "chemical", "semiochemical", "genetic"]) \
    .add("--method") \
    .add("--pest", dest="target_pest") \
    .add("--rate", type=float) \
    .add("--unit") \
    .add("--area", type=float, help="Area in hectares") \
    .add("--cost", type=float) \
    .add("--date", help="Intervention date YYYY-MM-DD") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_intervention)

cli.subcommand("record-pesticide", "Log pesticide application") \
    .add("--location-id", required=True) \
    .add("--product", required=True) \
    .add("--ingredient") \
    .add("--class", dest="chemical_class") \
    .add("--rate", type=float) \
    .add("--rate-unit") \
    .add("--area", type=float, help="Area in hectares") \
    .add("--volume", type=float) \
    .add("--volume-unit") \
    .add("--pest", dest="target_pest") \
    .add("--rei", type=int, help="Re-entry interval days") \
    .add("--phi", type=int, help="Pre-harvest interval days") \
    .add("--notes") \
    .add("--date", help="Application date YYYY-MM-DD") \
    .add("--json", action="store_true") \
    .run(_cmd_record_pesticide)

cli.subcommand("record-resistance", "Record resistance observation") \
    .add("--location-id", required=True) \
    .add("--pest", required=True) \
    .add("--class", dest="chemical_class", required=True) \
    .add("--level", required=True, choices=["susceptible", "low", "moderate", "high", "confirmed"]) \
    .add("--date", help="Observation date YYYY-MM-DD") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_resistance)

cli.subcommand("record-degree-day", "Record temperature and compute degree days") \
    .add("--location-id", required=True) \
    .add("--pest", required=True) \
    .add("--base", type=float, default=10.0, help="Base temperature") \
    .add("--max", type=float, dest="max_temp", help="Max temperature") \
    .add("--min", type=float, dest="min_temp", help="Min temperature") \
    .add("--upper", type=float, help="Upper developmental threshold") \
    .add("--date", help="Record date YYYY-MM-DD") \
    .add("--source", default="sensor") \
    .add("--json", action="store_true") \
    .run(_cmd_record_degree_day)

cli.subcommand("summary", "Pest scouting summary") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_summary)

cli.subcommand("pesticide-usage", "Chemical use totals") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=30) \
    .add("--json", action="store_true") \
    .run(_cmd_pesticide_usage)

cli.subcommand("degree-day-tracking", "Cumulative degree days and lifecycle stage") \
    .add("--location-id", required=True) \
    .add("--pest", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_degree_day_tracking)

cli.subcommand("recommend", "Recommend IPM intervention") \
    .add("--scouting-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_recommend)

cli.subcommand("dashboard", "Aggregated pest management dashboard") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_dashboard)

cli.subcommand("add-reference", "Add pest biology reference") \
    .add("--pest", required=True) \
    .add("--scientific-name") \
    .add("--common-name") \
    .add("--category", dest="pest_category",
         choices=["insect", "mite", "nematode", "fungal", "bacterial", "viral", "weed", "rodent", "other"]) \
    .add("--base-temp", type=float) \
    .add("--upper-temp", type=float) \
    .add("--total-dd", type=float, dest="total_degree_days") \
    .add("--hosts", nargs="*", help="Host crops") \
    .add("--enemies", nargs="*", help="Natural enemies") \
    .add("--importance", choices=["critical", "high", "moderate", "low"]) \
    .add("--json", action="store_true") \
    .run(_cmd_add_reference)

cli.subcommand("get-reference", "Look up pest biology reference") \
    .add("--pest", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_get_reference)

cli.subcommand("list-references", "List pest biology references") \
    .add("--category", dest="pest_category") \
    .add("--host", dest="host_crop") \
    .add("--json", action="store_true") \
    .run(_cmd_list_references)

cli.subcommand("create-schedule", "Create scouting schedule") \
    .add("--location-id", required=True) \
    .add("--pest", required=True) \
    .add("--crop") \
    .add("--frequency", type=int, default=7, dest="frequency_days") \
    .add("--method") \
    .add("--sample-size", type=int) \
    .add("--assigned-to") \
    .add("--start-date") \
    .add("--end-date") \
    .add("--json", action="store_true") \
    .run(_cmd_create_schedule)

cli.subcommand("due-scouting", "Get due/overdue scouting schedules") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_due_scouting)

cli.subcommand("record-compliance", "Record scouting completion") \
    .add("--schedule-id", required=True) \
    .add("--scouting-id", required=True) \
    .add("--date", dest="scout_date") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_compliance)

cli.subcommand("compliance-report", "Scouting compliance statistics") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=30) \
    .add("--json", action="store_true") \
    .run(_cmd_compliance_report)

cli.subcommand("schedule-re-scout", "Schedule follow-up re-scout") \
    .add("--intervention-id", required=True) \
    .add("--date", required=True, dest="re_scout_date") \
    .add("--json", action="store_true") \
    .run(_cmd_schedule_re_scout)

cli.subcommand("evaluate-intervention", "Evaluate intervention effectiveness") \
    .add("--intervention-id", required=True) \
    .add("--scouting-id", required=True, dest="re_scout_record_id") \
    .add("--effectiveness", type=float, required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_evaluate_intervention)

cli.subcommand("compliance-score", "Compute IPM compliance score") \
    .add("--location-id", required=True) \
    .add("--period-start") \
    .add("--period-end") \
    .add("--json", action="store_true") \
    .run(_cmd_compliance_score)

cli.subcommand("add-interaction", "Add pest-crop interaction") \
    .add("--pest", required=True) \
    .add("--crop", required=True) \
    .add("--damage-type") \
    .add("--loss-potential", type=float, dest="yield_loss_potential") \
    .add("--peak-stage") \
    .add("--management", nargs="*") \
    .add("--json", action="store_true") \
    .run(_cmd_add_interaction)

cli.subcommand("get-interactions", "Get pest-crop interactions") \
    .add("--crop") \
    .add("--pest") \
    .add("--json", action="store_true") \
    .run(_cmd_get_interactions)

cli.subcommand("recommend-for-crop", "Recommend management for crop/stage") \
    .add("--crop", required=True) \
    .add("--stage", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_recommend_for_crop)

cli.subcommand("add-trap", "Register monitoring trap") \
    .add("--location-id", required=True) \
    .add("--name", required=True, dest="trap_name") \
    .add("--type", required=True, dest="trap_type",
         choices=["pheromone", "sticky", "light", "pitfall", "sweep_net"]) \
    .add("--pest", dest="target_pest") \
    .add("--lure") \
    .add("--plot-id") \
    .add("--lat", type=float) \
    .add("--lon", type=float) \
    .add("--date") \
    .add("--json", action="store_true") \
    .run(_cmd_add_trap)

cli.subcommand("record-catch", "Log trap catch") \
    .add("--trap-id", required=True) \
    .add("--date", dest="check_date") \
    .add("--pest-count", type=int, default=0) \
    .add("--bycatch", type=int, default=0) \
    .add("--beneficial", type=int, default=0) \
    .add("--condition", dest="trap_condition") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_catch)

cli.subcommand("trap-trends", "Trap catch time series") \
    .add("--trap-id", required=True) \
    .add("--days", type=int, default=30) \
    .add("--json", action="store_true") \
    .run(_cmd_trap_trends)

cli.subcommand("check-trap-threshold", "Compare trap catch to ET") \
    .add("--trap-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_check_trap_threshold)

cli.subcommand("add-moa", "Add mode of action reference") \
    .add("--class", dest="chemical_class", required=True) \
    .add("--code", dest="moa_code", required=True) \
    .add("--action", required=True, dest="mode_of_action") \
    .add("--irac") \
    .add("--frac") \
    .add("--hrac") \
    .add("--cross-resistance", nargs="*") \
    .add("--compatible", nargs="*") \
    .add("--json", action="store_true") \
    .run(_cmd_add_moa)

cli.subcommand("check-rotation", "Verify MoA rotation compliance") \
    .add("--location-id", required=True) \
    .add("--class", dest="chemical_class", required=True) \
    .add("--min-days", type=int, default=14) \
    .add("--json", action="store_true") \
    .run(_cmd_check_rotation)

cli.subcommand("rotation-history", "Chemical class usage timeline") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=90) \
    .add("--json", action="store_true") \
    .run(_cmd_rotation_history)

cli.subcommand("spray-windows", "Optimal spray windows from forecast") \
    .add("--location-id", required=True) \
    .add("--pest", required=True) \
    .add("--days-ahead", type=int, default=7) \
    .add("--json", action="store_true") \
    .run(_cmd_spray_windows)

cli.subcommand("organic-pest-score", "IPM score for organic certification") \
    .add("--location-id", required=True) \
    .add("--period-start") \
    .add("--period-end") \
    .add("--json", action="store_true") \
    .run(_cmd_organic_pest_score)

cli.subcommand("generate-audit", "Generate IPM audit report") \
    .add("--location-id", required=True) \
    .add("--period-start") \
    .add("--period-end") \
    .add("--json", action="store_true") \
    .run(_cmd_generate_audit)


def main(argv=None):
    return cli.run(argv)


if __name__ == "__main__":
    main()

