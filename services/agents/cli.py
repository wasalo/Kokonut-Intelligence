"""Agent task catalogue CLI — lists available agent tasks and their schemas."""

from __future__ import annotations

import argparse
import json
import sys

from .tasks import get_task, list_tasks


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="services.agents",
        description="Kokonut agent task catalogue",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all task keys")

    desc = sub.add_parser("describe", help="Describe a single task")
    desc.add_argument("task_key", help="Task key to describe")

    if argv is None:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)

    if args.command == "list":
        print("\n".join(list_tasks()))
    elif args.command == "describe":
        print(json.dumps(get_task(args.task_key), indent=2, sort_keys=True))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
