#!/usr/bin/env python3
"""Print an explicit candidate Compose command without reading secrets or executing it."""

from __future__ import annotations

import argparse
import os
import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIGEST_RE = re.compile(r"^\S+@sha256:[0-9a-f]{64}$")
BASE = "docker-compose.kernel-candidate.yml"
ARM64 = "docker-compose.kernel-arm64.yml"
ARM64_STANDARD = "docker-compose.kernel-arm64-standard.yml"
ARM64_PROXY = "docker-compose.kernel-arm64-proxy.yml"
ARM64_ZITADEL = "docker-compose.kernel-arm64-zitadel.yml"
ARM64_GRPC = "docker-compose.kernel-arm64-grpc.yml"
ARM64_MQTT = "docker-compose.kernel-arm64-mqtt.yml"
ARM64_HTTP_SENSORS = "docker-compose.kernel-arm64-http-sensors.yml"
ARM64_DIRECTUS = "docker-compose.kernel-arm64-directus.yml"
ARM64_ANALYTICS = "docker-compose.kernel-arm64-analytics.yml"
ARM64_SENSOR_ANOMALY_ML = "docker-compose.kernel-arm64-sensor-anomaly-ml.yml"
SCHEDULER_ROLE = "docker-compose.kernel-scheduler-role.yml"
WORKER_RUNTIME_ROLE = "docker-compose.kernel-worker-runtime-role.yml"
WORKER_RUNTIME_SUPERVISOR = "docker-compose.kernel-worker-runtime-supervisor.yml"
PROFILES = {
    "minimal": [],
    "core": ["docker-compose.kernel-core.yml"],
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
    "sensor_anomaly_ml": "docker-compose.kernel-sensor-anomaly-ml.yml",
    "web3": "docker-compose.kernel-core-web3.yml",
    "exports": "docker-compose.kernel-core-exports.yml",
    "local_media": "docker-compose.kernel-core-local-media.yml",
}
RELEASE_UNSUPPORTED_OPTIONALS = {
    # These overlays add a locally-built service or mutable extension artifact.
    # They remain available to source deployments but need their own published,
    # digest-addressed image contract before `release-up` can select them.
    "grpc",
    "http_sensors",
    "directus",
    "mqtt",
    "sensor_anomaly_ml",
}
ZITADEL_RELEASE_IMAGE_VARIABLES = (
    "KOKONUT_ZITADEL_POSTGRES_IMAGE",
    "KOKONUT_ZITADEL_API_IMAGE",
    "KOKONUT_ZITADEL_LOGIN_IMAGE",
)


def _is_digest_pinned_image(value: str) -> bool:
    return IMAGE_DIGEST_RE.fullmatch(value) is not None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=[*PROFILES, "scale"])
    parser.add_argument("--target-platform", choices=["linux/amd64", "linux/arm64"], default="linux/amd64",
                        help="Declare the deployment architecture for compatibility checks")
    parser.add_argument("--separate-workers", action="store_true",
                        help="Select separate API/worker roles for analytics")
    parser.add_argument(
        "--edge",
        action="store_true",
        help="add Edge local-media and resource settings to the Standard profile",
    )
    parser.add_argument(
        "--scheduler-role",
        action="store_true",
        help="select the opt-in restricted scheduler executor for Standard",
    )
    parser.add_argument(
        "--separate-api-worker-logins",
        action="store_true",
        help="give Standard (or separate-worker analytics) distinct API and worker logins; composes with --scheduler-role",
    )
    parser.add_argument(
        "--project", help="Explicit Compose project name (for example, a unique disposable test project)"
    )
    for name in OPTIONAL:
        parser.add_argument(f"--{name.replace('_', '-')}", dest=name, action="store_true")
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        help="omit the Standard profile's default Caddy ingress when using another ingress",
    )
    parser.add_argument(
        "--action",
        choices=["config", "build", "up", "release-up", "ps", "database-up", "migrate", "bootstrap-runtime-role"],
        default="config",
    )
    args = parser.parse_args()
    if args.project is not None and not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", args.project):
        parser.error("--project must be 1–63 lowercase letters, digits, hyphens, or underscores and start with a letter or digit")
    is_arm64 = args.target_platform == "linux/arm64"
    selected_optional = {name for name in OPTIONAL if getattr(args, name)}
    if args.no_proxy and args.profile != "standard":
        parser.error("--no-proxy applies only to standard; other profiles include ingress only when requested")
    if args.no_proxy and args.proxy:
        parser.error("--proxy and --no-proxy cannot be selected together")
    if args.no_proxy and args.zitadel:
        parser.error("--zitadel includes its Caddy routes and cannot be combined with --no-proxy")
    if args.profile == "standard" and not args.no_proxy:
        selected_optional.add("proxy")

    if is_arm64 and args.profile not in {"minimal", "core", "edge", "standard", "analytics"}:
        parser.error("ARM64 currently supports only core, minimal, edge, standard, and analytics profiles")
    core_capability_overlays = {"web3", "exports", "local_media"}
    selected_core_overlays = selected_optional & core_capability_overlays
    if selected_core_overlays and args.profile != "core":
        parser.error("--web3, --exports, and --local-media apply only to the core profile")
    if args.profile == "core" and (args.oidc or args.zitadel):
        parser.error("the core profile cannot use --oidc or --zitadel because those application overlays select the full OIDC image")
    arm64_verified_optional = {
        "proxy", "oidc", "zitadel", "grpc", "mqtt", "http_sensors", "directus",
        "sensor_anomaly_ml", "web3", "exports", "local_media",
    }
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
    role_separated = args.profile == "standard" or args.separate_workers
    if args.separate_api_worker_logins and not role_separated:
        parser.error("--separate-api-worker-logins applies only to Standard or analytics with --separate-workers")
    if args.separate_api_worker_logins and args.action not in {"database-up", "migrate"} and not os.environ.get(
        "KOKONUT_WORKER_RUNTIME_PASSWORD"
    ):
        parser.error(
            "--separate-api-worker-logins requires KOKONUT_WORKER_RUNTIME_PASSWORD loaded from encrypted secrets"
        )
    if args.action in {"database-up", "migrate", "bootstrap-runtime-role"} and not role_separated:
        parser.error(f"--action {args.action} applies only to standard or analytics with --separate-workers")
    if args.edge and args.profile != "standard":
        parser.error("--edge applies only to standard; use the edge profile for a standalone Edge deployment")
    if args.scheduler_role and args.profile != "standard":
        parser.error("--scheduler-role applies only to standard")
    if args.scheduler_role:
        missing_scheduler_values = [
            name for name in (
                "KOKONUT_SCHEDULER_PASSWORD",
                "KOKONUT_SCHEDULER_DATABASE_URL",
            ) if not os.environ.get(name)
        ]
        if missing_scheduler_values:
            parser.error(
                "--scheduler-role requires these variables to be loaded from the encrypted environment: "
                + ", ".join(missing_scheduler_values)
            )
    if args.oidc and "proxy" not in selected_optional and not args.zitadel and args.profile != "standard":
        parser.error("--oidc requires --proxy so operator session cookies use the HTTPS origin")

    files = [BASE]
    if args.separate_workers:
        files.append("docker-compose.kernel-standard.yml")
    files.extend(PROFILES[args.profile])
    if role_separated:
        files.append("docker-compose.kernel-runtime-role.yml")
    if args.separate_api_worker_logins and args.action not in {"database-up", "migrate"}:
        files.append(WORKER_RUNTIME_ROLE)
    if args.edge:
        # Add the Edge limits and local-media provider to the API app after
        # Standard splits the app and worker. The worker has no local-media
        # caller and must not inherit the app's key or private-media volume.
        files.append("docker-compose.kernel-edge.yml")
    if args.separate_workers:
        files.append("docker-compose.kernel-standard-analytics.yml")
    if args.zitadel:
        # The self-hosted provider needs the HTTPS ingress and the Gateway's
        # OIDC client settings. One flag produces a complete, ordered stack;
        # Standard already includes the shared proxy overlay by default.
        selected_optional.update({"proxy", "oidc"})
    if args.action == "release-up":
        if args.profile != "standard":
            parser.error("--action release-up applies only to standard")
        unsupported = selected_optional & RELEASE_UNSUPPORTED_OPTIONALS
        if unsupported:
            parser.error(
                "release-up does not yet publish immutable images for these optional overlays: "
                + ", ".join(sorted(unsupported))
                + "; use the source-build action or omit them from the release profile"
            )
        app_image = os.environ.get("KOKONUT_KERNEL_APP_IMAGE", "")
        if not _is_digest_pinned_image(app_image):
            parser.error(
                "release-up requires KOKONUT_KERNEL_APP_IMAGE to be an immutable "
                "image reference ending in @sha256:<64 lowercase hex digits>"
            )
        if "oidc" in selected_optional and not _is_digest_pinned_image(
            os.environ.get("KOKONUT_KERNEL_OIDC_IMAGE", "")
        ):
            parser.error(
                "release-up with --oidc/--zitadel requires KOKONUT_KERNEL_OIDC_IMAGE "
                "to be an immutable image reference ending in @sha256:<64 lowercase hex digits>"
            )
        if args.zitadel:
            for variable in ZITADEL_RELEASE_IMAGE_VARIABLES:
                override = os.environ.get(variable)
                if override and not _is_digest_pinned_image(override):
                    parser.error(
                        f"release-up with --zitadel requires {variable} overrides to be "
                        "immutable image references ending in @sha256:<64 lowercase hex digits>"
                    )
    elif args.action in {"build", "up"} and (
        _is_digest_pinned_image(os.environ.get("KOKONUT_KERNEL_APP_IMAGE", ""))
        or _is_digest_pinned_image(os.environ.get("KOKONUT_KERNEL_OIDC_IMAGE", ""))
    ):
        parser.error(
            "build/up use source-built local images; unset digest-pinned image variables "
            "or use --action release-up"
        )
    files.extend(path for name, path in OPTIONAL.items() if name in selected_optional)
    if is_arm64:
        files.append(ARM64)
        if args.profile == "standard" or args.separate_workers:
            files.append(ARM64_STANDARD)
        if args.profile == "analytics":
            files.append(ARM64_ANALYTICS)
        if "proxy" in selected_optional:
            files.append(ARM64_PROXY)
        if args.zitadel:
            files.append(ARM64_ZITADEL)
        if "grpc" in selected_optional:
            files.append(ARM64_GRPC)
        if "mqtt" in selected_optional:
            files.append(ARM64_MQTT)
        if "http_sensors" in selected_optional:
            files.append(ARM64_HTTP_SENSORS)
        if "directus" in selected_optional:
            files.append(ARM64_DIRECTUS)
        if "sensor_anomaly_ml" in selected_optional:
            files.append(ARM64_SENSOR_ANOMALY_ML)
    if args.scheduler_role:
        # This is a final opt-in worker identity override and must merge after
        # Standard, runtime-role, and any selected architecture/service overlays.
        files.append(SCHEDULER_ROLE)
    if args.scheduler_role and args.separate_api_worker_logins:
        # Keep the long-lived worker supervisor on its general worker login.
        # The scheduler child selects its dedicated DSN and strips these PG_*
        # values before it starts; this final overlay restores only the parent
        # service identity after the scheduler profile has selected its role.
        files.append(WORKER_RUNTIME_SUPERVISOR)
    for filename in files:
        if not (ROOT / filename).is_file():
            parser.error(f"Required manifest is missing: {filename}")

    # --env-file prevents Compose implicitly loading a plaintext .env. Export
    # required secrets explicitly before running the printed command.
    project_name = args.project or (
        "kokonut-kernel-candidate-arm64" if is_arm64 else "kokonut-kernel-candidate"
    )
    command = ["docker", "compose", "--project-directory", str(ROOT),
               "--env-file", "/dev/null", "-p", project_name]
    for filename in files:
        command.extend(["-f", str(ROOT / filename)])
    if args.action == "database-up":
        command.extend(["up", "-d", "--wait", "--wait-timeout", "300", "database"])
    elif args.action == "migrate":
        migration_command = [
            "python3", "-m", "services.migration", "migrate", "--schemas-only",
            "--compose-project", project_name,
        ]
        for filename in files:
            migration_command.extend(["--compose-file", str(ROOT / filename)])
        print(shlex.join(migration_command))
        return
    elif args.action == "bootstrap-runtime-role":
        # This provisioner reapplies broad compatibility grants. Keep it an
        # explicit one-shot after migrations, never part of routine `up`.
        command.extend([
            "--profile", "runtime-admin", "run", "--rm", "--build",
            "runtime-role-bootstrap",
        ])
    elif args.action == "config":
        command.extend(["config", "--quiet"])
    elif args.action == "release-up":
        pull_command = [*command, "pull"]
        up_command = [
            *command,
            "up",
            "-d",
            "--no-build",
            "--wait",
            "--wait-timeout",
            "300",
        ]
        print(f"{shlex.join(pull_command)} && {shlex.join(up_command)}")
        return
    elif args.action == "up":
        command.extend(["up", "-d", "--build"])
    else:
        command.append(args.action)
    print(shlex.join(command))


if __name__ == "__main__":
    main()
