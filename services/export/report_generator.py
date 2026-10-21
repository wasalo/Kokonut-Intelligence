#!/usr/bin/env python3
"""
Report Generator — Farm Summary, Crop NOI, Environmental Impact

Generates structured report snapshots with hash verification.
Stores results in the report_snapshot table.

Generators live in services/export/reports/ (per-domain modules + shared
context/snapshot components); this module is the CLI facade that re-exports
the public report API.

Usage:
    python3 -m services.export.report_generator --type farm_summary --location-id UUID
    python3 -m services.export.report_generator --type crop_noi --location-id UUID
    python3 -m services.export.report_generator --type environmental --location-id UUID
    python3 -m services.export.report_generator --list
"""

import argparse
import uuid
from datetime import date

from .reports import (  # noqa: F401 (re-exported public report API)
    REPORT_GENERATORS,
    _check_report_empty,
    _verify_snapshot,
    attach_public_interest_context,
    build_negative_findings,
    compute_hash,
    fetch_public_interest_context,
    generate_adaptive_stewardship,
    generate_adoption_barriers,
    generate_algorithmic_redistribution,
    generate_anti_capture_governance,
    generate_bio_factory_batch,
    generate_bio_input_provenance,
    generate_bio_quality_test,
    generate_bio_recipe_library,
    generate_bio_regional_input,
    generate_business_model_canvas,
    generate_business_plan,
    generate_capability_assessment,
    generate_capability_dashboard,
    generate_capital_accounting,
    generate_capital_alignment,
    generate_capital_efficiency,
    generate_capital_provider_utility,
    generate_climate_impact,
    generate_community_governance,
    generate_comprehensive_status,
    generate_coordination_cockpit,
    generate_crop_noi,
    generate_cultural_preservation,
    generate_dao_proposal_history,
    generate_data_stream_summary,
    generate_ebf_scorecard,
    generate_ecological_modeling,
    generate_env_scan_report,
    generate_environmental,
    generate_farm_summary,
    generate_federation_mutual_aid,
    generate_financial_sustainability,
    generate_forecast_summary,
    generate_fork_opportunities,
    generate_foundational_wellbeing,
    generate_gnh_alignment,
    generate_governance_coordination_health,
    generate_governance_inclusion,
    generate_governance_throughput,
    generate_green_paper_publication_status,
    generate_holistic_wellbeing,
    generate_land_stewardship,
    generate_livestock_feed,
    generate_model_validation,
    generate_open_source_impact,
    generate_organic_certification_readiness,
    generate_organic_input_audit,
    generate_organic_transition_progress,
    generate_participatory_signal,
    generate_perpetual_value_stress,
    generate_pest_management,
    generate_pestel_assessment,
    generate_pin_dependency,
    generate_pitch_deck,
    generate_process_health,
    generate_promotion_ladder,
    generate_publics_market_landscape,
    generate_redistribution_policy,
    generate_regenerative_outcomes,
    generate_regional_readiness,
    generate_renewable_energy,
    generate_replication_readiness,
    generate_resource_efficiency,
    generate_revenue_multiplier,
    generate_revenue_streams,
    generate_reward_calibration,
    generate_risk_mitigation,
    generate_scaling_economics,
    generate_scaling_roadmap,
    generate_simulation_wargame,
    generate_stakeholder_cockpit,
    generate_stakeholder_decision_lineage,
    generate_stakeholder_ecosystem,
    generate_stakeholder_engagement,
    generate_stakeholder_grievance,
    generate_stakeholder_landscape,
    generate_stakeholder_outcomes,
    generate_stakeholder_representation,
    generate_stakeholder_trust,
    generate_stakeholder_value_streams,
    generate_state_of_kokonut,
    generate_state_of_kokonut_graphs,
    generate_statement_of_work,
    generate_strategic_reserve,
    generate_strategy_execution,
    generate_tactical_layer,
    generate_technology_roadmap,
    generate_time_liberation,
    generate_token_rewards,
    generate_training_impact,
    generate_trophic_pyramid,
    generate_value_stream_formal,
    generate_value_stream_map,
    generate_vulnerable_access,
    get_pg,
    list_snapshots,
    store_snapshot,
)

NETWORK_LEVEL_REPORTS = frozenset(
    {
        "state_of_kokonut",
        "dao_proposal_history",
        "state_of_kokonut_graphs",
        "comprehensive_status",
        "strategic_reserve",
    }
)

# These generators explicitly interpret a selected-location list or the
# literal ``all`` scope. Other generators receive one location UUID only.
MULTI_LOCATION_REPORTS = frozenset(
    {
        "business_plan",
        "comprehensive_status",
        "state_of_kokonut",
        "state_of_kokonut_graphs",
        "strategic_reserve",
    }
)
ALL_LOCATION_REPORTS = NETWORK_LEVEL_REPORTS | {"business_plan"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Kokonut report snapshots")
    parser.add_argument("--type", choices=list(REPORT_GENERATORS.keys()), help="Report type to generate")
    parser.add_argument(
        "--location-id",
        action="append",
        help="Location UUID (repeatable only for aggregate report types; or use --all when supported)",
    )
    parser.add_argument("--all", action="store_true", help="Use the report type's supported all-location scope")
    parser.add_argument("--period-start", help="Report period start (YYYY-MM-DD)")
    parser.add_argument("--period-end", help="Report period end (YYYY-MM-DD)")
    parser.add_argument("--list", action="store_true", help="List existing snapshots")
    parser.add_argument("--verify", help="Verify a snapshot by hash")
    parser.add_argument("--auto", action="store_true", help="Attempt all report types for one location or --all")
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Reject ambiguous or unscoped report CLI requests before opening a DB."""
    if args.type and args.auto:
        parser.error("--type and --auto are mutually exclusive")

    if args.list and (args.verify or args.type or args.auto or args.all or args.period_start or args.period_end):
        parser.error("--list may only be combined with --location-id")

    if args.list and args.location_id and len(args.location_id) > 1:
        parser.error("--list accepts at most one --location-id")

    if args.verify and (args.list or args.type or args.auto or args.all or args.location_id or args.period_start or args.period_end):
        parser.error("--verify cannot be combined with report generation or scope options")

    if args.all and args.location_id:
        parser.error("--all cannot be combined with --location-id")

    if args.auto and args.location_id and len(args.location_id) > 1:
        parser.error("--auto supports one --location-id or explicit --all, not multiple locations")

    if args.type and args.all and args.type not in ALL_LOCATION_REPORTS:
        parser.error(f"--all is not supported for report type {args.type}")

    if args.type and args.location_id and len(args.location_id) > 1:
        if args.type not in MULTI_LOCATION_REPORTS:
            parser.error(f"multiple --location-id values are not supported for report type {args.type}")

    if args.location_id:
        try:
            args.location_id = [str(uuid.UUID(value)) for value in args.location_id]
        except (AttributeError, TypeError, ValueError):
            parser.error("--location-id values must be valid UUIDs")
        if len(set(args.location_id)) != len(args.location_id):
            parser.error("--location-id values must be unique")

    parsed_periods = {}
    for option, value in (
        ("--period-start", args.period_start),
        ("--period-end", args.period_end),
    ):
        if value is None:
            continue
        try:
            parsed = date.fromisoformat(value)
        except (TypeError, ValueError):
            parser.error(f"{option} must be a valid date in YYYY-MM-DD format")
        if parsed.isoformat() != value:
            parser.error(f"{option} must be a valid date in YYYY-MM-DD format")
        parsed_periods[option] = parsed

    if (
        "--period-start" in parsed_periods
        and "--period-end" in parsed_periods
        and parsed_periods["--period-start"] > parsed_periods["--period-end"]
    ):
        parser.error("--period-start cannot be after --period-end")

    if args.list or args.verify:
        return

    if not args.type and not args.auto:
        parser.error("--type or --auto is required (or use --list or --verify)")

    if args.auto and not args.all and not args.location_id:
        parser.error("--auto requires --location-id or explicit --all")

    if args.type and not args.all and not args.location_id and args.type not in NETWORK_LEVEL_REPORTS:
        parser.error("--location-id is required (or use --all for network-level reports)")


def _report_failure_summary(exc: Exception) -> str:
    """Return a stable report failure without exposing exception details."""
    name = type(exc).__name__
    if not name.isascii() or not name.isidentifier() or len(name) > 64:
        name = "Exception"
    return f"report generation failed ({name})"


def generate_report_data_read_only(conn, generator, location_arg, period_start, period_end):
    """Calculate a report in a read-only PostgreSQL transaction.

    Snapshot persistence happens afterward in its own write transaction. The
    connection's session default keeps every query read-only after a generator
    commits. Autocommit is rejected because it would bypass transaction-level
    read-only enforcement.
    """
    previous_autocommit = conn.autocommit
    conn.set_session(readonly=True)
    try:
        return generator(
            _ReadOnlyReportConnection(conn), location_arg, period_start, period_end
        )
    finally:
        # End the calculation transaction before store_snapshot starts its
        # separate, intentional draft-snapshot write.
        try:
            conn.rollback()
        finally:
            try:
                conn.autocommit = previous_autocommit
            finally:
                conn.set_session(readonly=False)


class _ReadOnlyReportConnection:
    """Prevent report code from lowering the session's read-only default."""

    _BLOCKED = frozenset({"readonly", "deferrable", "set_session"})

    def __init__(self, conn):
        object.__setattr__(self, "_conn", conn)

    def cursor(self, *args, **kwargs):
        return _ReadOnlyReportCursor(self._conn.cursor(*args, **kwargs), self)

    def __getattr__(self, name):
        if name in self._BLOCKED:
            raise RuntimeError("report generators cannot lower the read-only database mode")
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        if name in self._BLOCKED:
            raise RuntimeError("report generators cannot lower the read-only database mode")
        if name == "autocommit" and value:
            raise RuntimeError("report generators cannot enable autocommit during calculation")
        setattr(self._conn, name, value)


class _ReadOnlyReportCursor:
    """Keep the raw psycopg connection from escaping through ``cursor.connection``."""

    def __init__(self, cursor, connection):
        object.__setattr__(self, "_cursor", cursor)
        object.__setattr__(self, "_connection", connection)

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self._cursor.__exit__(*args)

    def __getattr__(self, name):
        if name == "connection":
            return self._connection
        return getattr(self._cursor, name)


def _run_auto_generation(
    conn,
    *,
    location_arg: str | None,
    location_label: str,
    period_start: str | None,
    period_end: str | None,
) -> None:
    report_types = list(REPORT_GENERATORS.keys())
    run_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO report_generation_run (id, location_scope, total_reports) VALUES (%s, %s, %s)",
            (run_id, location_arg, len(report_types)),
        )
    conn.commit()
    print(f"Generating all {len(report_types)} report types for {location_label}...")
    print()

    success = 0
    failed = 0
    empty = 0

    for report_type in report_types:
        print(f"Generating {report_type}...")
        item_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO report_generation_run_item (id, run_id, report_type, status) VALUES (%s, %s, %s, 'running')",
                (item_id, run_id, report_type),
            )
        conn.commit()
        try:
            generator = REPORT_GENERATORS[report_type]
            report_data = generate_report_data_read_only(
                conn, generator, location_arg, period_start, period_end
            )
            _check_report_empty(report_data, report_type)
            snapshot_id = store_snapshot(
                conn, report_data, location_arg, period_start, period_end
            )
            snapshot_hash = compute_hash(report_data)
            print(f"  ✓ {report_type}: {snapshot_id} ({snapshot_hash[:16]})")
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE report_generation_run_item SET status = 'succeeded', snapshot_id = %s, completed_at = NOW() WHERE id = %s",
                    (snapshot_id, item_id),
                )
            conn.commit()
            success += 1
        except Exception as exc:  # noqa: BLE001 - persist failure and continue the batch
            safe_error = _report_failure_summary(exc)
            print(f"  ✗ {report_type}: {safe_error}")
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE report_generation_run_item SET status = 'failed', error_message = %s, completed_at = NOW() WHERE id = %s",
                    (safe_error, item_id),
                )
            conn.commit()
            failed += 1

    print(f"\nDone: {success} succeeded, {failed} failed, {empty} empty")
    run_status = "succeeded" if failed == 0 else "partial" if success else "failed"
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE report_generation_run SET status = %s, succeeded_reports = %s, failed_reports = %s, completed_at = NOW() WHERE id = %s",
            (run_status, success, failed, run_id),
        )
    conn.commit()
    if failed > 0:
        raise SystemExit(1)


def main():
    parser = build_parser()
    args = parser.parse_args()
    validate_args(parser, args)

    conn = get_pg()

    if args.list:
        list_loc = args.location_id[0] if args.location_id else None
        try:
            snapshots = list_snapshots(conn, list_loc)
            if not snapshots:
                print("No snapshots found.")
            else:
                print(f"{'ID':<38} {'Type':<20} {'Status':<12} {'Created':<20} Hash")
                print("-" * 120)
                for s in snapshots:
                    print(
                        f"{str(s['id']):<38} {s['report_type']:<20} {s['status']:<12} {str(s['created_at']):<20} {s['snapshot_hash'][:16]}"
                    )
        finally:
            conn.close()
        return

    if args.verify:
        try:
            _verify_snapshot(conn, args.verify)
        finally:
            conn.close()
        return

    # Normalize the location argument for single/all/multi selection.
    if args.all:
        location_arg = "all"
        location_label = "ALL locations"
    elif args.location_id:
        # args.location_id is a list (action="append"); join for generators that
        # accept a comma-separated list (state_of_kokonut) or pass the single one.
        if len(args.location_id) == 1:
            location_arg = args.location_id[0]
        else:
            location_arg = ",".join(args.location_id)
        location_label = location_arg
    else:
        location_arg = None
        location_label = "network (no location filter)"

    if args.auto:
        try:
            _run_auto_generation(
                conn,
                location_arg=location_arg,
                location_label=location_label,
                period_start=args.period_start,
                period_end=args.period_end,
            )
        finally:
            conn.close()
        return

    print(f"Generating {args.type} report for {location_label}...")

    try:
        generator = REPORT_GENERATORS[args.type]
        report_data = generate_report_data_read_only(
            conn, generator, location_arg, args.period_start, args.period_end
        )

        snapshot_id = store_snapshot(conn, report_data, location_arg, args.period_start, args.period_end)
        snapshot_hash = compute_hash(report_data)

        print(f"Snapshot stored: {snapshot_id}")
        print(f"Hash: {snapshot_hash}")
        print(f"Report type: {args.type}")
    except Exception as exc:
        safe_error = _report_failure_summary(exc)
        print(safe_error)
        raise RuntimeError(safe_error) from None
    finally:
        conn.close()



if __name__ == "__main__":
    main()
