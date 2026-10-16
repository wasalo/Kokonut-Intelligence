#!/usr/bin/env python3
"""Print an explicit candidate Compose command without reading secrets or executing it."""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "docker-compose.kernel-candidate.yml"
ARM64 = "docker-compose.kernel-arm64.yml"
ARM64_STANDARD = "docker-compose.kernel-arm64-standard.yml"
ARM64_PROXY = "docker-compose.kernel-arm64-proxy.yml"
ARM64_ZITADEL = "docker-compose.kernel-arm64-zitadel.yml"
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
    "directus": "docker-compose.kernel-directus.yml",
    "zitadel": "docker-compose.kernel-zitadel.yml",
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
    is_arm64 = args.target_platform == "linux/arm64"
    if is_arm64 and args.profile not in {"minimal", "edge", "standard"}:
        parser.error("ARM64 currently supports only minimal, edge, and standard profiles")
    selected_optional = {name for name in OPTIONAL if getattr(args, name)}
    arm64_verified_optional = {"proxy", "oidc", "zitadel"}
    unverified_arm64_optional = selected_optional - arm64_verified_optional
    if is_arm64 and unverified_arm64_optional:
        parser.error(
            "ARM64 does not verify these optional overlays: "
            + ", ".join(sorted(unverified_arm64_optional))
        )
    if args.profile == "scale":
        parser.error("Scale is not implemented: shared rate limits and replica recovery acceptance are pending")
    if args.separate_workers and args.profile != "analytics":
        parser.error("--separate-workers applies only to analytics; standard already separates roles")
    if args.oidc and not args.proxy and not args.zitadel:
        parser.error("--oidc requires --proxy so operator session cookies use the HTTPS origin")

    files = [BASE]
    if args.separate_workers:
        files.append("docker-compose.kernel-standard.yml")
    files.extend(PROFILES[args.profile])
    if args.separate_workers:
        files.append("docker-compose.kernel-standard-analytics.yml")
    if args.zitadel:
        # The self-hosted provider needs the HTTPS ingress and the Gateway's
        # OIDC client settings. Keep all three opt-in while making one flag
        # produce a complete, ordered stack.
        selected_optional.update({"proxy", "oidc"})
    files.extend(path for name, path in OPTIONAL.items() if name in selected_optional)
    if is_arm64:
        files.append(ARM64)
        if args.profile == "standard":
            files.append(ARM64_STANDARD)
        if "proxy" in selected_optional:
            files.append(ARM64_PROXY)
        if args.zitadel:
            files.append(ARM64_ZITADEL)
    for filename in files:
        if not (ROOT / filename).is_file():
            parser.error(f"Required manifest is missing: {filename}")

    # --env-file prevents Compose implicitly loading a plaintext .env. Export
    # required secrets explicitly before running the printed command.
    project_name = "kokonut-kernel-candidate-arm64" if is_arm64 else "kokonut-kernel-candidate"
    command = ["docker", "compose", "--project-directory", str(ROOT),
               "--env-file", "/dev/null", "-p", project_name]
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
