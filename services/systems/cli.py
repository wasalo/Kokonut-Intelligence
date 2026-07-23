"""Systems-thinking CLI — help-only stub.

Systems modules (causal_loops, leverage, archetypes, stock_flow, etc.) are
pure libraries with no CLI entry points.  This stub exists so the meta-CLI
(``python3 -m services.cli systems``) does not break.
"""

from __future__ import annotations

import argparse
import sys

from . import (
    archetypes,
    causal_loops,
    delays,
    double_loop,
    leverage,
    mental_models,
    stock_flow,
)

MODULES = {
    "causal_loops": causal_loops,
    "leverage": leverage,
    "archetypes": archetypes,
    "delays": delays,
    "double_loop": double_loop,
    "stock_flow": stock_flow,
    "mental_models": mental_models,
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="services.systems",
        description="Systems-thinking tooling (library-only, no CLI commands)",
    )
    parser.add_argument(
        "--list-modules",
        action="store_true",
        help="List available systems-thinking modules",
    )

    if argv is None:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)

    if args.list_modules:
        for name in sorted(MODULES):
            mod = MODULES[name]
            doc = (mod.__doc__ or "").strip().split("\n")[0]
            print(f"  {name:<20} {doc}")
    else:
        parser.print_help()
        print("\nSystems modules are used programmatically, e.g.:", file=sys.stderr)
        print("  from systems.causal_loops import evaluate_loop", file=sys.stderr)
        print("  from systems.stock_flow import StockFlowSimulator", file=sys.stderr)


if __name__ == "__main__":
    main()
