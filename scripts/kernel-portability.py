#!/usr/bin/env python3
"""Print an isolated portability preparation command without executing it."""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docker-compose.kernel-portability.yml"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-platform", required=True,
                        choices=["linux/amd64", "linux/arm64"],
                        help="Select the platform for both evaluation images")
    parser.add_argument("--action", default="config",
                        choices=["config", "build-database", "build-app", "readiness", "ps"])
    parser.add_argument("--with-workers", action="store_true",
                        help="Include the optional native worker role in the printed selection")
    args = parser.parse_args()
    if not MANIFEST.is_file():
        parser.error(f"Required manifest is missing: {MANIFEST}")
    command = ["env", f"KOKONUT_DATABASE_PLATFORM={args.target_platform}",
               "docker", "compose", "--project-directory", str(ROOT),
               "--env-file", "/dev/null", "-p", "kokonut-kernel-portability",
               "-f", str(MANIFEST), "--profile", "application"]
    if args.with_workers:
        command.extend(["--profile", "workers"])
    if args.action == "config":
        command.extend(["config", "--quiet"])
    elif args.action == "build-database":
        command.extend(["build", "database"])
    elif args.action == "build-app":
        command.extend(["build", "app"])
    elif args.action == "readiness":
        command.extend(["run", "--rm", "--no-deps", "app", "python3", "-m",
                        "services.core.cli", "schema-readiness"])
    else:
        command.append("ps")
    print(shlex.join(command))


if __name__ == "__main__":
    main()
