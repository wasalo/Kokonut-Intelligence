"""CLI for gRPC server."""

from __future__ import annotations

import argparse
import sys


def cmd_serve(args):
    from services.core.adapters.grpc import serve

    serve()


def cmd_health(args):
    from services.core.adapters.grpc import check_health

    target = args.target or "localhost:50051"
    try:
        print(f"Status: {check_health(target)}")
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Kokonut gRPC Server")
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="Start gRPC server")
    p_serve.set_defaults(func=cmd_serve)

    p_health = sub.add_parser("health", help="Check gRPC server health")
    p_health.add_argument("--target", default=None, help="gRPC server target (default: localhost:50051)")
    p_health.set_defaults(func=cmd_health)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
