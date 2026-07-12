"""CLI for the API gateway.

Usage:
    python3 -m services.gateway --port 8099
    python3 -m services.gateway --health
"""

from __future__ import annotations

import argparse
import sys


def cmd_serve(args):
    """Start the gateway server."""
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required: pip install uvicorn")
        return 1

    from services.gateway.app import create_app
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
    return 0


def cmd_health(args):
    """Check gateway health."""
    from services.core.health import overall_health
    import json
    result = overall_health()
    print(json.dumps(result, indent=2))
    return 0 if result.get("healthy") else 1


def main():
    parser = argparse.ArgumentParser(description="API Gateway CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--serve", action="store_true", help="Start the gateway server")
    group.add_argument("--health", action="store_true", help="Check gateway health")

    parser.add_argument("--port", type=int, default=8099, help="Server port")

    args = parser.parse_args()

    if args.serve:
        rc = cmd_serve(args)
    elif args.health:
        rc = cmd_health(args)
    else:
        parser.print_help()
        rc = 1

    sys.exit(rc)


if __name__ == "__main__":
    main()
