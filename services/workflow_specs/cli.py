"""Workflow specification command line interface."""

import argparse

from .registry import get_spec, list_specs
from .render import render_markdown, render_mermaid
from .validator import WorkflowValidationError, validate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Workflow specification tools")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("spec_id", nargs="?")
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("spec_id")
    render_parser.add_argument("--format", choices=("markdown", "mermaid"), default="markdown")
    args = parser.parse_args(argv)

    if args.command == "list":
        for spec in list_specs():
            print(f"{spec.id}\t{spec.title}")
        return 0

    specs = (get_spec(args.spec_id),) if args.spec_id else list_specs()
    if args.command == "validate":
        try:
            for spec in specs:
                validate(spec)
                print(f"valid\t{spec.id}")
        except WorkflowValidationError as exc:
            print(f"invalid\t{exc}")
            return 1
        return 0

    spec = specs[0]
    validate(spec)
    print(
        render_markdown(spec) if args.format == "markdown" else render_mermaid(spec),
        end="",
    )
    return 0
