"""Enterprise planning CLI: financial plans and budgets (FP&A)."""

from __future__ import annotations

import argparse
import sys

from services.common.database import get_db
from services.planning import budget, performance, portfolio, sandop
from services.common.cli import print_json

def _dump(rows):
    if rows is None:
        print("null")
        return
    if isinstance(rows, dict):
        rows = [rows]
    print_json([dict(r) for r in rows])


def _cmd_plan_create(args):
    conn = get_db()
    try:
        _dump(budget.create_plan(
            conn, args.org_id, args.name, args.start, args.end,
            currency=args.currency, objective_id=args.objective_id,
            created_by_type=args.created_by_type, created_by_id=args.created_by_id,
        ))
    finally:
        conn.close()


def _cmd_plan_list(args):
    conn = get_db()
    try:
        _dump(budget.list_plans(conn, args.org_id, status=args.status))
    finally:
        conn.close()


def _cmd_plan_show(args):
    conn = get_db()
    try:
        _dump(budget.get_plan(conn, args.id))
    finally:
        conn.close()


def _cmd_plan_add_line(args):
    conn = get_db()
    try:
        _dump(budget.add_budget_line(conn, args.id, args.category, args.amount, location_id=args.location_id))
    finally:
        conn.close()


def _cmd_plan_approve(args):
    conn = get_db()
    try:
        _dump(budget.approve(conn, args.id, args.actor_type, args.actor_id, note=args.note))
    finally:
        conn.close()


def _cmd_plan_activate(args):
    conn = get_db()
    try:
        _dump(budget.activate(conn, args.id, args.actor_type, args.actor_id, note=args.note))
    finally:
        conn.close()


def _cmd_plan_close(args):
    conn = get_db()
    try:
        _dump(budget.close(conn, args.id, args.actor_type, args.actor_id, note=args.note))
    finally:
        conn.close()


def _cmd_plan_cancel(args):
    conn = get_db()
    try:
        _dump(budget.cancel(conn, args.id, args.actor_type, args.actor_id, note=args.note))
    finally:
        conn.close()


def _cmd_plan_actuals(args):
    conn = get_db()
    try:
        _dump(budget.actuals_rollup(conn, args.id))
    finally:
        conn.close()


def _cmd_obj_kpi(args):
    conn = get_db()
    try:
        _dump(performance.assign_kpi(
            conn, args.id, args.target_value, direction=args.direction,
            metric_key=args.metric_key, metric_definition_id=args.metric_definition_id,
            crisp_dimension=args.crisp_dimension, current_value_snapshot=args.current_value,
            source_ref=args.source_ref,
        ))
    finally:
        conn.close()


def _cmd_obj_review(args):
    conn = get_db()
    try:
        review, wi = performance.record_review(
            conn, args.id, args.reviewer_type, args.status,
            reviewer_id=args.reviewer_id, notes=args.notes, organization_id=args.org_id,
        )
        out = dict(review)
        out["corrective_work_item_id"] = wi
        _dump(out)
    finally:
        conn.close()


def _cmd_obj_kpis(args):
    conn = get_db()
    try:
        _dump(performance.list_kpis(conn, args.id))
    finally:
        conn.close()


def _cmd_obj_reviews(args):
    conn = get_db()
    try:
        _dump(performance.list_reviews(conn, args.id))
    finally:
        conn.close()


def _cmd_obj_health(args):
    conn = get_db()
    try:
        print(performance.objective_health(conn, args.id))
    finally:
        conn.close()


def _cmd_ppm_program_create(args):
    conn = get_db()
    try:
        _dump(portfolio.create_program(
            conn, args.org_id, args.name, objective_id=args.objective_id, budget_id=args.budget_id,
        ))
    finally:
        conn.close()


def _cmd_ppm_project_create(args):
    conn = get_db()
    try:
        _dump(portfolio.create_project(
            conn, args.org_id, args.name, program_id=args.program_id,
            objective_id=args.objective_id, budget_id=args.budget_id, due_at=args.due_at,
        ))
    finally:
        conn.close()


def _cmd_ppm_list_programs(args):
    conn = get_db()
    try:
        _dump(portfolio.list_programs(conn, args.org_id, status=args.status))
    finally:
        conn.close()


def _cmd_ppm_start(args):
    conn = get_db()
    try:
        _dump(portfolio.start(conn, args.id, args.actor_type, args.actor_id))
    finally:
        conn.close()


def _cmd_ppm_hold(args):
    conn = get_db()
    try:
        _dump(portfolio.hold(conn, args.id, args.note, args.actor_type, args.actor_id))
    finally:
        conn.close()


def _cmd_ppm_resume(args):
    conn = get_db()
    try:
        _dump(portfolio.resume(conn, args.id, args.actor_type, args.actor_id))
    finally:
        conn.close()


def _cmd_ppm_complete(args):
    conn = get_db()
    try:
        _dump(portfolio.complete(conn, args.id, args.actor_type, args.actor_id))
    finally:
        conn.close()


def _cmd_ppm_cancel(args):
    conn = get_db()
    try:
        _dump(portfolio.cancel(conn, args.id, args.actor_type, args.actor_id))
    finally:
        conn.close()


def _cmd_ppm_rollup(args):
    conn = get_db()
    try:
        _dump(portfolio.project_rollup(conn, args.id))
    finally:
        conn.close()


def _cmd_sandop_show(args):
    conn = get_db()
    try:
        _dump(sandop.cockpit(conn, args.org_id))
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="planning", description="Kokonut enterprise planning")
    sub = parser.add_subparsers(dest="group", required=True)

    p = sub.add_parser("plan", help="financial plans and budgets")
    ps = p.add_subparsers(dest="action", required=True)

    c = ps.add_parser("create")
    c.add_argument("--org-id", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--start", required=True)
    c.add_argument("--end", required=True)
    c.add_argument("--currency", default="USD")
    c.add_argument("--objective-id")
    c.add_argument("--created-by-type", default="system")
    c.add_argument("--created-by-id")
    c.set_defaults(func=_cmd_plan_create)

    c = ps.add_parser("list")
    c.add_argument("--org-id", required=True)
    c.add_argument("--status")
    c.set_defaults(func=_cmd_plan_list)

    c = ps.add_parser("show")
    c.add_argument("--id", required=True)
    c.set_defaults(func=_cmd_plan_show)

    c = ps.add_parser("add-line")
    c.add_argument("--id", required=True)
    c.add_argument("--category", required=True)
    c.add_argument("--amount", type=float, required=True)
    c.add_argument("--location-id")
    c.set_defaults(func=_cmd_plan_add_line)

    c = ps.add_parser("approve")
    c.add_argument("--id", required=True)
    c.add_argument("--actor-type", default="human reviewer")
    c.add_argument("--actor-id")
    c.add_argument("--note")
    c.set_defaults(func=_cmd_plan_approve)

    c = ps.add_parser("activate")
    c.add_argument("--id", required=True)
    c.add_argument("--actor-type", default="planner")
    c.add_argument("--actor-id")
    c.add_argument("--note")
    c.set_defaults(func=_cmd_plan_activate)

    c = ps.add_parser("close")
    c.add_argument("--id", required=True)
    c.add_argument("--actor-type", default="planner")
    c.add_argument("--actor-id")
    c.add_argument("--note")
    c.set_defaults(func=_cmd_plan_close)

    c = ps.add_parser("cancel")
    c.add_argument("--id", required=True)
    c.add_argument("--actor-type", default="planner")
    c.add_argument("--actor-id")
    c.add_argument("--note")
    c.set_defaults(func=_cmd_plan_cancel)

    c = ps.add_parser("actuals")
    c.add_argument("--id", required=True)
    c.set_defaults(func=_cmd_plan_actuals)

    # ---- objective (performance management) ----
    o = sub.add_parser("objective", help="objectives, KPIs, reviews")
    os_ = o.add_subparsers(dest="action", required=True)

    c = os_.add_parser("assign-kpi")
    c.add_argument("--id", required=True)
    c.add_argument("--target-value", required=True)
    c.add_argument("--direction", default="gte")
    c.add_argument("--metric-key")
    c.add_argument("--metric-definition-id")
    c.add_argument("--crisp-dimension")
    c.add_argument("--current-value")
    c.add_argument("--source-ref")
    c.set_defaults(func=_cmd_obj_kpi)

    c = os_.add_parser("review")
    c.add_argument("--id", required=True)
    c.add_argument("--reviewer-type", default="staff")
    c.add_argument("--reviewer-id")
    c.add_argument("--status", required=True, choices=["on_track", "at_risk", "off_track", "closed"])
    c.add_argument("--notes")
    c.add_argument("--org-id")
    c.set_defaults(func=_cmd_obj_review)

    c = os_.add_parser("list-kpis")
    c.add_argument("--id", required=True)
    c.set_defaults(func=_cmd_obj_kpis)

    c = os_.add_parser("list-reviews")
    c.add_argument("--id", required=True)
    c.set_defaults(func=_cmd_obj_reviews)

    c = os_.add_parser("health")
    c.add_argument("--id", required=True)
    c.set_defaults(func=_cmd_obj_health)

    # ---- portfolio (program / project) ----
    pp = sub.add_parser("portfolio", help="programs and projects")
    pps = pp.add_subparsers(dest="action", required=True)

    c = pps.add_parser("create-program")
    c.add_argument("--org-id", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--objective-id")
    c.add_argument("--budget-id")
    c.set_defaults(func=_cmd_ppm_program_create)

    c = pps.add_parser("create-project")
    c.add_argument("--org-id", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--program-id")
    c.add_argument("--objective-id")
    c.add_argument("--budget-id")
    c.add_argument("--due-at")
    c.set_defaults(func=_cmd_ppm_project_create)

    c = pps.add_parser("list-programs")
    c.add_argument("--org-id", required=True)
    c.add_argument("--status")
    c.set_defaults(func=_cmd_ppm_list_programs)

    c = pps.add_parser("start")
    c.add_argument("--id", required=True)
    c.add_argument("--actor-type", default="manager")
    c.add_argument("--actor-id")
    c.set_defaults(func=_cmd_ppm_start)

    c = pps.add_parser("hold")
    c.add_argument("--id", required=True)
    c.add_argument("--note", required=True)
    c.add_argument("--actor-type", default="manager")
    c.add_argument("--actor-id")
    c.set_defaults(func=_cmd_ppm_hold)

    c = pps.add_parser("resume")
    c.add_argument("--id", required=True)
    c.add_argument("--actor-type", default="manager")
    c.add_argument("--actor-id")
    c.set_defaults(func=_cmd_ppm_resume)

    c = pps.add_parser("complete")
    c.add_argument("--id", required=True)
    c.add_argument("--actor-type", default="manager")
    c.add_argument("--actor-id")
    c.set_defaults(func=_cmd_ppm_complete)

    c = pps.add_parser("cancel")
    c.add_argument("--id", required=True)
    c.add_argument("--actor-type", default="manager")
    c.add_argument("--actor-id")
    c.set_defaults(func=_cmd_ppm_cancel)

    c = pps.add_parser("rollup")
    c.add_argument("--id", required=True)
    c.set_defaults(func=_cmd_ppm_rollup)

    # ---- S&OP cockpit (read-only) ----
    sc = sub.add_parser("cockpit", help="S&OP cockpit (read-only)")
    scs = sc.add_subparsers(dest="action", required=True)
    c = scs.add_parser("show")
    c.add_argument("--org-id", required=True)
    c.set_defaults(func=_cmd_sandop_show)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
