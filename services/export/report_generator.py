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


def main():
    parser = argparse.ArgumentParser(description="Generate Kokonut report snapshots")
    parser.add_argument("--type", choices=list(REPORT_GENERATORS.keys()), help="Report type to generate")
    parser.add_argument(
        "--location-id", action="append", help="Location UUID (repeatable; or use --all for every location)"
    )
    parser.add_argument("--all", action="store_true", help="Generate the report across ALL locations")
    parser.add_argument("--period-start", help="Report period start (YYYY-MM-DD)")
    parser.add_argument("--period-end", help="Report period end (YYYY-MM-DD)")
    parser.add_argument("--list", action="store_true", help="List existing snapshots")
    parser.add_argument("--verify", help="Verify a snapshot by hash")
    parser.add_argument("--auto", action="store_true", help="Generate all report types for the location")
    args = parser.parse_args()

    if not args.list:
        if not args.type and not args.auto:
            parser.error("--type or --auto is required (or use --list)")

        # Location requirement: network-level reports (state_of_kokonut, dao_proposal_history)
        # accept --all or no location; others require at least one --location-id.
        network_level = args.type in (
            "state_of_kokonut",
            "dao_proposal_history",
            "state_of_kokonut_graphs",
            "comprehensive_status",
            "strategic_reserve",
        )
        if not args.location_id and not args.all and not network_level:
            parser.error("--location-id is required (or use --all for network-level reports)")

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
                report_data = generator(conn, location_arg, args.period_start, args.period_end)
                _check_report_empty(report_data, report_type)
                snapshot_id = store_snapshot(conn, report_data, location_arg, args.period_start, args.period_end)
                snapshot_hash = compute_hash(report_data)
                print(f"  ✓ {report_type}: {snapshot_id} ({snapshot_hash[:16]})")
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE report_generation_run_item SET status = 'succeeded', snapshot_id = %s, completed_at = NOW() WHERE id = %s",
                        (snapshot_id, item_id),
                    )
                conn.commit()
                success += 1
            except Exception as e:
                print(f"  ✗ {report_type}: {e}")
                conn.rollback()
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE report_generation_run_item SET status = 'failed', error_message = %s, completed_at = NOW() WHERE id = %s",
                        (str(e)[:4000], item_id),
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
        conn.close()
        if failed > 0:
            exit(1)
        return

    print(f"Generating {args.type} report for {location_label}...")

    try:
        generator = REPORT_GENERATORS[args.type]
        report_data = generator(conn, location_arg, args.period_start, args.period_end)

        snapshot_id = store_snapshot(conn, report_data, location_arg, args.period_start, args.period_end)
        snapshot_hash = compute_hash(report_data)

        print(f"Snapshot stored: {snapshot_id}")
        print(f"Hash: {snapshot_hash}")
        print(f"Report type: {args.type}")
    except Exception as exc:
        print(f"Report generation failed: {exc}")
        raise
    finally:
        conn.close()



if __name__ == "__main__":
    main()
