"""Pollinator health CLI.

Extracted from services.analytics.pollinator_health so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_pollinator_health --help
"""

from datetime import date

from ..common.commands import CommandLine
from .pollinator_health import (
    add_hive,
    create_habitat,
    get_habitat_inventory,
    get_hive_status,
    get_pesticide_risk,
    get_pollinator_dashboard,
    get_pollinator_summary,
    record_hive_inspection,
    record_pesticide_impact,
)

# ============================================================
# CLI
# ============================================================

cli = CommandLine("pollinator_health", "Pollinator health monitoring")


def _cmd_retired_record_observation(_db, _a):
    raise RuntimeError(
        "Unscoped pollinator observation writes are retired; use the authenticated "
        "Kokonut Gateway pollinator capture form with a location create grant."
    )


def _cmd_create_habitat(db, a):
    return create_habitat(
        db, a.location_id, a.name, a.habitat_type, a.area_m2,
        plant_species=a.plant_species,
        bloom_start_month=a.bloom_start_month,
        bloom_end_month=a.bloom_end_month,
        water_source=a.water_source,
        nesting_sites=a.nesting_sites,
        management_notes=a.management_notes,
    )


def _cmd_record_pesticide(db, a):
    app_date = date.fromisoformat(a.application_date)
    return record_pesticide_impact(
        db, a.location_id, app_date, a.product_name,
        a.active_ingredient, a.toxicity_class,
        application_rate=a.application_rate,
        rate_unit=a.rate_unit,
        area_treated_m2=a.area_treated_m2,
        bloom_stage_at_application=a.bloom_stage_at_application,
        pollinator_distance_m=a.pollinator_distance_m,
        pollinator_safe_period_days=a.pollinator_safe_period_days,
        pollinator_mortality_observed=a.pollinator_mortality_observed,
        mortality_pct=a.mortality_pct,
        notes=a.notes,
    )


def _cmd_add_hive(db, a):
    return add_hive(
        db, a.location_id, a.hive_id,
        colony_strength=a.colony_strength,
        queen_status=a.queen_status,
        hive_type=a.hive_type,
        frame_count=a.frame_count,
        queen_year=a.queen_year,
        notes=a.notes,
    )


def _cmd_record_inspection(db, a):
    return record_hive_inspection(
        db, a.location_id, a.hive_id,
        colony_strength=a.colony_strength,
        queen_status=a.queen_status,
        queen_seen=a.queen_seen,
        varroa_count=a.varroa_count,
        brood_pattern=a.brood_pattern,
        honey_stores=a.honey_stores,
        disease_signs=a.disease_signs,
        temperament=a.temperament,
        population_estimate=a.population_estimate,
        swarm_cells=a.swarm_cells,
        notes=a.notes,
    )


cli.subcommand("record-observation", "Retired; use authenticated Gateway capture") \
    .add("--location-id", required=True) \
    .add("--type", required=True, dest="pollinator_type",
         help="Pollinator type (honeybee, wild_bee, butterfly, moth, etc.)") \
    .add("--count", type=int, required=True) \
    .add("--method", default="visual_count", dest="observation_method") \
    .add("--duration", type=int, default=15, dest="duration_minutes") \
    .add("--plot-id", "--habitat-area-id", dest="habitat_area_id",
         help="Plot UUID (the legacy habitat-area-id spelling remains accepted)") \
    .add("--weather") \
    .add("--temperature", type=float) \
    .add("--date", dest="observation_date", help="Observation date (YYYY-MM-DD); defaults to today") \
    .add("--species-name") \
    .add("--hive-record-id", help="Optional UUID linking this observation to a managed hive") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_retired_record_observation, needs_db=False)

cli.subcommand("create-habitat", "Create pollinator habitat") \
    .add("--location-id", required=True) \
    .add("--name", required=True) \
    .add("--type", required=True, dest="habitat_type") \
    .add("--area", type=float, required=True, dest="area_m2") \
    .add("--plant-species", nargs="*", default=[]) \
    .add("--bloom-start", type=int, dest="bloom_start_month") \
    .add("--bloom-end", type=int, dest="bloom_end_month") \
    .add("--water-source", action="store_true") \
    .add("--nesting-sites") \
    .add("--notes", dest="management_notes") \
    .add("--json", action="store_true") \
    .run(_cmd_create_habitat)

cli.subcommand("record-pesticide", "Record pesticide impact") \
    .add("--location-id", required=True) \
    .add("--date", required=True, dest="application_date") \
    .add("--product", required=True, dest="product_name") \
    .add("--ingredient", required=True, dest="active_ingredient") \
    .add("--toxicity", required=True, dest="toxicity_class") \
    .add("--rate", type=float, dest="application_rate") \
    .add("--rate-unit", dest="rate_unit") \
    .add("--area", type=float, dest="area_treated_m2") \
    .add("--bloom-stage", dest="bloom_stage_at_application") \
    .add("--distance", type=float, dest="pollinator_distance_m") \
    .add("--safe-period-days", type=int, dest="pollinator_safe_period_days") \
    .add("--mortality-observed", action="store_true", dest="pollinator_mortality_observed") \
    .add("--mortality-pct", type=float) \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_pesticide)

cli.subcommand("add-hive", "Add managed hive") \
    .add("--location-id", required=True) \
    .add("--hive-id", required=True) \
    .add("--colony-strength", default="5", help="Category or legacy score from 0 to 10") \
    .add("--queen-status", default="present") \
    .add("--hive-type", default="langstroth") \
    .add("--frames", type=int, default=10, dest="frame_count") \
    .add("--queen-year", type=int) \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_add_hive)

cli.subcommand("record-inspection", "Record hive inspection") \
    .add("--location-id", required=True) \
    .add("--hive-id", required=True) \
    .add("--colony-strength", help="Category or legacy score from 0 to 10") \
    .add("--queen-status") \
    .add("--queen-seen", action="store_true", dest="queen_seen", default=None) \
    .add("--queen-not-seen", action="store_false", dest="queen_seen", default=None) \
    .add("--varroa-count", type=int) \
    .add("--brood-pattern") \
    .add("--honey-stores") \
    .add("--disease-signs") \
    .add("--temperament") \
    .add("--population", type=int, dest="population_estimate") \
    .add("--swarm-cells", action="store_true") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_record_inspection)

cli.subcommand("summary", "Pollinator summary") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=30) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_pollinator_summary(db, a.location_id, a.days))

cli.subcommand("habitat-inventory", "Habitat inventory") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_habitat_inventory(db, a.location_id))

cli.subcommand("pesticide-risk", "Pesticide risk") \
    .add("--location-id", required=True) \
    .add("--days", type=int, default=90) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_pesticide_risk(db, a.location_id, a.days))

cli.subcommand("hive-status", "Hive status") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_hive_status(db, a.location_id))

cli.subcommand("dashboard", "Pollinator dashboard") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_pollinator_dashboard(db, a.location_id))


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()

