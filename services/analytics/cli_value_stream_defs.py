"""CLI for Value Stream Definitions."""

from __future__ import annotations

import argparse
import sys

from services.analytics.value_stream_defs import (
    create_stage,
    create_stream,
    get_observations,
    get_stage,
    get_stream,
    get_stream_performance,
    get_stream_summary,
    get_stream_with_stages,
    list_stages,
    list_streams,
    record_observation,
    update_stream,
)
from services.common.cli import print_json


def _out(data):
    print_json(data)


def cmd_create(args):
    data = create_stream(
        args.name,
        description=args.description or "",
        stakeholder_type=args.stakeholder,
        trigger_event=args.trigger,
        end_state=args.end_state,
        owner_role=args.owner,
    )
    _out(data)


def cmd_get(args):
    data = get_stream(args.id)
    if not data:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_list(args):
    data = list_streams(
        stakeholder_type=args.stakeholder,
        status=args.status,
    )
    _out(data)


def cmd_update(args):
    fields = {}
    if args.name:
        fields["name"] = args.name
    if args.description:
        fields["description"] = args.description
    if args.status:
        fields["status"] = args.status
    data = update_stream(args.id, **fields)
    if not data:
        print("Not found or no changes", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_create_stage(args):
    data = create_stage(
        args.stream_id,
        args.name,
        description=args.description or "",
        sequence_order=args.order or 1,
        process_key=args.process,
        target_lead_time_hours=args.target_lead_time,
        target_fty_pct=args.target_fty,
    )
    _out(data)


def cmd_get_stage(args):
    data = get_stage(args.id)
    if not data:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _out(data)


def cmd_list_stages(args):
    data = list_stages(args.stream_id)
    _out(data)


def cmd_observe(args):
    data = record_observation(
        args.stage_id,
        args.entity_type,
        args.entity_id,
        actual_lead_time_hours=args.lead_time,
        actual_fty_pct=args.fty,
        notes=args.notes,
    )
    _out(data)


def cmd_observations(args):
    data = get_observations(args.stage_id, limit=args.limit or 50)
    _out(data)


def cmd_performance(args):
    data = get_stream_performance(args.stream_id)
    _out(data)


def cmd_summary(args):
    data = get_stream_summary()
    _out(data)


def cmd_full(args):
    data = get_stream_with_stages(args.stream_id)
    if not data:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _out(data)


def build_parser(p):
    sub = p.add_subparsers(dest="vs_cmd")

    # stream CRUD
    c = sub.add_parser("create", help="Create value stream")
    c.add_argument("name")
    c.add_argument("--description", default="")
    c.add_argument("--stakeholder", default=None,
                   choices=["farmer", "buyer", "investor", "regulator", "community", "internal"])
    c.add_argument("--trigger", default=None)
    c.add_argument("--end-state", default=None)
    c.add_argument("--owner", default=None)
    c.set_defaults(func=cmd_create)

    g = sub.add_parser("get", help="Get value stream")
    g.add_argument("id")
    g.set_defaults(func=cmd_get)

    l = sub.add_parser("list", help="List value streams")
    l.add_argument("--stakeholder", default=None)
    l.add_argument("--status", default="active")
    l.set_defaults(func=cmd_list)

    u = sub.add_parser("update", help="Update value stream")
    u.add_argument("id")
    u.add_argument("--name", default=None)
    u.add_argument("--description", default=None)
    u.add_argument("--status", default=None)
    u.set_defaults(func=cmd_update)

    # stages
    sc = sub.add_parser("stage-create", help="Create stage")
    sc.add_argument("stream_id")
    sc.add_argument("name")
    sc.add_argument("--description", default="")
    sc.add_argument("--order", type=int, default=1)
    sc.add_argument("--process", default=None)
    sc.add_argument("--target-lead-time", type=float, default=None)
    sc.add_argument("--target-fty", type=float, default=None)
    sc.set_defaults(func=cmd_create_stage)

    sg = sub.add_parser("stage-get", help="Get stage")
    sg.add_argument("id")
    sg.set_defaults(func=cmd_get_stage)

    sl = sub.add_parser("stages", help="List stages for a stream")
    sl.add_argument("stream_id")
    sl.set_defaults(func=cmd_list_stages)

    # observations
    so = sub.add_parser("observe", help="Record observation")
    so.add_argument("stage_id")
    so.add_argument("entity_type")
    so.add_argument("entity_id")
    so.add_argument("--lead-time", type=float, default=None)
    so.add_argument("--fty", type=float, default=None)
    so.add_argument("--notes", default=None)
    so.set_defaults(func=cmd_observe)

    sol = sub.add_parser("observations", help="List observations")
    sol.add_argument("stage_id")
    sol.add_argument("--limit", type=int, default=50)
    sol.set_defaults(func=cmd_observations)

    # performance
    sp = sub.add_parser("performance", help="Stage performance for a stream")
    sp.add_argument("stream_id")
    sp.set_defaults(func=cmd_performance)

    ss = sub.add_parser("summary", help="Stream-level summary")
    ss.set_defaults(func=cmd_summary)

    sf = sub.add_parser("full", help="Stream with all stages")
    sf.add_argument("stream_id")
    sf.set_defaults(func=cmd_full)


def main():
    parser = argparse.ArgumentParser(description="Value Stream Definitions CLI")
    build_parser(parser)
    args = parser.parse_args()
    if not hasattr(args, "vs_cmd"):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
