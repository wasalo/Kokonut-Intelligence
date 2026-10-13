#!/usr/bin/env python3
"""Print an explicit candidate Compose command without reading secrets or executing it."""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "docker-compose.kernel-candidate.yml"
PROFILES = {
    "minimal": [],
    "edge": ["docker-compose.kernel-edge.yml"],
    "standard": ["docker-compose.kernel-standard.yml"],
    "analytics": ["docker-compose.kernel-analytics.yml"],
}
OPTIONAL = {
    "proxy": "docker-compose.kernel-proxy.yml",
    "oidc": "docker-compose.kernel-oidc.yml",
    "grpc": "docker-compose.kernel-grpc.yml",
    "mqtt": "docker-compose.kernel-mqtt.yml",
    "http_sensors": "docker-compose.kernel-http-sensors.yml",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=[*PROFILES, "scale"])
    parser.add_argument("--target-platform", choices=["linux/amd64", "linux/arm64"], default="linux/amd64",
                        help="Declare the deployment architecture for compatibility checks")
    parser.add_argument("--separate-workers", action="store_true",
                        help="Select separate API/worker roles for analytics")
    for name in OPTIONAL:
        parser.add_argument(f"--{name.replace('_', '-')}", dest=name, action="store_true")
    parser.add_argument("--action", choices=["config", "build", "up", "ps"], default="config")
    args = parser.parse_args()
    if args.target_platform == "linux/arm64":
        parser.error("ARM64 deployment is blocked: the pinned PostGIS database manifest is AMD64-only")
    if args.profile == "scale":
        parser.error("Scale is not implemented: shared rate limits and replica recovery acceptance are pending")
    if args.separate_workers and args.profile != "analytics":
        parser.error("--separate-workers applies only to analytics; standard already separates roles")
    if args.oidc and not args.proxy:
        parser.error("--oidc requires --proxy so operator session cookies use the HTTPS origin")

    files = [BASE]
    if args.separate_workers:
        files.append("docker-compose.kernel-standard.yml")
    files.extend(PROFILES[args.profile])
    if args.separate_workers:
        files.append("docker-compose.kernel-standard-analytics.yml")
    files.extend(path for name, path in OPTIONAL.items() if getattr(args, name))
    for filename in files:
        if not (ROOT / filename).is_file():
            parser.error(f"Required manifest is missing: {filename}")

    # --env-file prevents Compose implicitly loading a plaintext .env. Export
    # required secrets explicitly before running the printed command.
    command = ["docker", "compose", "--project-directory", str(ROOT),
               "--env-file", "/dev/null", "-p", "kokonut-kernel-candidate"]
    for filename in files:
        command.extend(["-f", str(ROOT / filename)])
    if args.action == "config":
        command.extend(["config", "--quiet"])
    elif args.action == "up":
        command.extend(["up", "-d", "--build"])
    else:
        command.append(args.action)
    print(shlex.join(command))


if __name__ == "__main__":
    main()
