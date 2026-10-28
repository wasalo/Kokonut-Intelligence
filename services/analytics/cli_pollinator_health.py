"""Pollinator health CLI.

Extracted from services.analytics.pollinator_health so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_pollinator_health --help
"""

from uuid import UUID

from ..common.commands import CommandLine
from .pollinator_health import (
    get_habitat_inventory,
    get_hive_status,
    get_pesticide_risk,
    get_pollinator_dashboard,
    get_pollinator_summary,
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
    raise RuntimeError(
        "Unscoped pollinator habitat writes are retired; use the authenticated "
        "Kokonut Gateway habitat form with a location create grant."
    )


def _cmd_retired_record_pesticide(_db, _a):
    raise RuntimeError(
        "Unscoped pesticide-impact writes are retired; use the authenticated "
        "Kokonut Gateway pesticide-report form with a location create grant."
    )


def _cmd_add_hive(_db, _a):
    raise RuntimeError(
        "Unscoped managed-hive writes are retired; use the authenticated "
        "Kokonut Gateway hive form with a location create grant."
    )


def _cmd_record_inspection(_db, _a):
    raise RuntimeError(
        "Unscoped hive inspection writes are retired; use the authenticated "
        "Kokonut Gateway inspection form with a location create grant."
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

cli.subcommand("create-habitat", "Retired; use authenticated Gateway habitat capture") \
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
    .run(_cmd_create_habitat, needs_db=False)

cli.subcommand("record-pesticide", "Retired; use authenticated Gateway pesticide report") \
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
    .run(_cmd_retired_record_pesticide, needs_db=False)

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
    .run(_cmd_add_hive, needs_db=False)

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
    .run(_cmd_record_inspection, needs_db=False)

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
    parser = cli.build_parser()
    args = parser.parse_args(argv)
    database_reads = {
        "summary",
        "habitat-inventory",
        "pesticide-risk",
        "hive-status",
        "dashboard",
    }
    if args.command in database_reads:
        try:
            UUID(args.location_id)
        except (AttributeError, TypeError, ValueError):
            parser.error(f"--location-id must be a valid UUID for {args.command}")
    cli.run(argv)


if __name__ == "__main__":
    main()

