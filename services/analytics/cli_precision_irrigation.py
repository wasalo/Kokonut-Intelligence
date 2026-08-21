"""Precision irrigation (zones, targets, schedules, rules) CLI.

Extracted from services.analytics.precision_irrigation so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_precision_irrigation --help
"""

import argparse
import json
from datetime import datetime

from ..common.cli import print_json
from .precision_irrigation import (
    compute_water_balance,
    create_automation_rule,
    create_zone,
    evaluate_automation_rules,
    generate_schedule,
    get_efficiency_report,
    get_irrigation_status,
    get_water_efficiency,
    get_zone_status,
    optimize_schedule,
    record_irrigation_event,
    set_moisture_target,
)

# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Precision irrigation automation")
    sub = parser.add_subparsers(dest="command")

    # create-zone
    cz = sub.add_parser("create-zone", help="Create irrigation zone")
    cz.add_argument("--location-id", required=True)
    cz.add_argument("--name", required=True)
    cz.add_argument("--zone-code")
    cz.add_argument("--soil-type")
    cz.add_argument("--crop")
    cz.add_argument("--area-ha", type=float)
    cz.add_argument("--depth-cm", type=float, default=30.0)
    cz.add_argument("--field-capacity", type=float)
    cz.add_argument("--wilting-point", type=float)
    cz.add_argument("--bulk-density", type=float)
    cz.add_argument("--sensor-id")
    cz.add_argument("--actuator-id")
    cz.add_argument("--plot-id")
    cz.add_argument("--json", action="store_true")

    # set-target
    st = sub.add_parser("set-target", help="Set soil moisture target")
    st.add_argument("--zone-id", required=True)
    st.add_argument("--crop-stage", required=True)
    st.add_argument("--target-min", type=float, required=True)
    st.add_argument("--target-max", type=float, required=True)
    st.add_argument("--trigger-pct", type=float, required=True)
    st.add_argument("--refill-pct", type=float, required=True)
    st.add_argument("--crop-id")
    st.add_argument("--stress-threshold", type=float)
    st.add_argument("--notes")
    st.add_argument("--json", action="store_true")

    # schedule
    sc = sub.add_parser("schedule", help="Generate irrigation schedule")
    sc.add_argument("--zone-id", required=True)
    sc.add_argument("--etc", type=float, required=True, help="ETc in mm")
    sc.add_argument("--rainfall", type=float, default=0.0, help="Rainfall forecast in mm")
    sc.add_argument("--moisture", type=float, help="Current soil moisture %")
    sc.add_argument("--target-moisture", type=float, help="Target soil moisture %")
    sc.add_argument("--start", help="Schedule start ISO timestamp")
    sc.add_argument("--triggered-by", default="scheduled", choices=["manual", "scheduled", "automation", "advisory"])
    sc.add_argument("--crop-cycle-id")
    sc.add_argument("--json", action="store_true")

    # record-event
    re = sub.add_parser("record-event", help="Record irrigation event")
    re.add_argument("--zone-id", required=True)
    re.add_argument("--volume", type=float, required=True, help="Volume in liters")
    re.add_argument("--duration", type=float, required=True, help="Duration in minutes")
    re.add_argument("--method", required=True, choices=["drip", "sprinkler", "flood", "pivot", "manual"])
    re.add_argument("--moisture-before", type=float)
    re.add_argument("--moisture-after", type=float)
    re.add_argument("--schedule-id")
    re.add_argument("--etc", type=float)
    re.add_argument("--water-source")
    re.add_argument("--trigger-type", default="manual", choices=["manual", "scheduled", "automation", "advisory"])
    re.add_argument("--efficiency", type=float)
    re.add_argument("--runoff-pct", type=float, default=0.0)
    re.add_argument("--deep-percolation-pct", type=float, default=0.0)
    re.add_argument("--energy-cost", type=float)
    re.add_argument("--notes")
    re.add_argument("--json", action="store_true")

    # create-rule
    cr = sub.add_parser("create-rule", help="Create automation rule")
    cr.add_argument("--location-id", required=True)
    cr.add_argument("--zone-id")
    cr.add_argument("--name", required=True)
    cr.add_argument("--description")
    cr.add_argument("--metric", required=True, help="Sensor metric name")
    cr.add_argument("--operator", required=True, choices=["lt", "lte", "gt", "gte", "eq", "neq", "between"])
    cr.add_argument("--threshold", type=float, required=True)
    cr.add_argument("--threshold-high", type=float)
    cr.add_argument("--unit", default="%")
    cr.add_argument("--action", default="irrigate")
    cr.add_argument("--cooldown", type=int, default=60)
    cr.add_argument("--max-per-day", type=int, default=5)
    cr.add_argument("--time-window-start")
    cr.add_argument("--time-window-end")
    cr.add_argument("--priority", type=int, default=50)
    cr.add_argument("--no-approval", action="store_true")
    cr.add_argument("--json", action="store_true")

    # eval-rules
    er = sub.add_parser("eval-rules", help="Evaluate automation rules")
    er.add_argument("--zone-id", required=True)
    er.add_argument("--readings", required=True, help="JSON dict of metric: value")
    er.add_argument("--json", action="store_true")

    # zone-status
    zs = sub.add_parser("zone-status", help="Get zone status")
    zs.add_argument("--zone-id", required=True)
    zs.add_argument("--json", action="store_true")

    # irrigation-status
    ist = sub.add_parser("irrigation-status", help="Get all zones status for location")
    ist.add_argument("--location-id", required=True)
    ist.add_argument("--json", action="store_true")

    # water-efficiency
    we = sub.add_parser("water-efficiency", help="Water use efficiency metrics")
    we.add_argument("--location-id", required=True)
    we.add_argument("--days", type=int, default=30)
    we.add_argument("--json", action="store_true")

    # water-balance
    wb = sub.add_parser("water-balance", help="Compute water balance for zone")
    wb.add_argument("--zone-id", required=True)
    wb.add_argument("--json", action="store_true")

    # optimize
    op = sub.add_parser("optimize", help="Optimize irrigation schedule")
    op.add_argument("--zone-id", required=True)
    op.add_argument("--json", action="store_true")

    # efficiency-report
    ef = sub.add_parser("efficiency-report", help="Water use efficiency report")
    ef.add_argument("--location-id", required=True)
    ef.add_argument("--json", action="store_true")

    args = parser.parse_args()

    from ..ingestion.base import get_db

    if args.command is None:
        parser.print_help()
        return

    db = get_db()
    try:
        if args.command == "create-zone":
            result = create_zone(
                db, args.location_id, args.name,
                zone_code=args.zone_code, soil_type=args.soil_type,
                crop_name=args.crop, area_ha=args.area_ha,
                depth_cm=args.depth_cm,
                field_capacity_pct=args.field_capacity,
                wilting_point_pct=args.wilting_point,
                bulk_density=args.bulk_density,
                sensor_id=args.sensor_id, actuator_id=args.actuator_id,
                plot_id=args.plot_id,
            )
        elif args.command == "set-target":
            result = set_moisture_target(
                db, args.zone_id, args.crop_stage,
                args.target_min, args.target_max,
                args.trigger_pct, args.refill_pct,
                crop_id=args.crop_id,
                stress_threshold=args.stress_threshold,
                notes=args.notes,
            )
        elif args.command == "schedule":
            start = datetime.fromisoformat(args.start) if args.start else None
            result = generate_schedule(
                db, args.zone_id, args.etc,
                rainfall_forecast_mm=args.rainfall,
                current_moisture_pct=args.moisture,
                target_soil_moisture_pct=args.target_moisture,
                scheduled_start=start,
                triggered_by=args.triggered_by,
                crop_cycle_id=args.crop_cycle_id,
            )
        elif args.command == "record-event":
            result = record_irrigation_event(
                db, args.zone_id, args.volume, args.duration,
                args.method, args.moisture_before, args.moisture_after,
                schedule_id=args.schedule_id, etc_mm=args.etc,
                water_source=args.water_source,
                trigger_type=args.trigger_type,
                efficiency_pct=args.efficiency,
                run_off_pct=args.runoff_pct,
                deep_percolation_pct=args.deep_percolation_pct,
                energy_cost_usd=args.energy_cost,
                notes=args.notes,
            )
        elif args.command == "create-rule":
            result = create_automation_rule(
                db, args.location_id, args.name,
                args.metric, args.operator, args.threshold,
                actuator_command=args.action, zone_id=args.zone_id,
                description=args.description, unit=args.unit,
                threshold_high=args.threshold_high,
                cooldown_min=args.cooldown, max_per_day=args.max_per_day,
                time_window_start=args.time_window_start,
                time_window_end=args.time_window_end,
                requires_approval=not args.no_approval,
                priority=args.priority,
            )
        elif args.command == "eval-rules":
            readings = json.loads(args.readings)
            result = evaluate_automation_rules(db, args.zone_id, readings)
        elif args.command == "zone-status":
            result = get_zone_status(db, args.zone_id)
        elif args.command == "irrigation-status":
            result = get_irrigation_status(db, args.location_id)
        elif args.command == "water-efficiency":
            result = get_water_efficiency(db, args.location_id, args.days)
        elif args.command == "water-balance":
            result = compute_water_balance(db, args.zone_id)
        elif args.command == "optimize":
            result = optimize_schedule(db, args.zone_id)
        elif args.command == "efficiency-report":
            result = get_efficiency_report(db, args.location_id)
        else:
            parser.print_help()
            return

        print_json(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()

