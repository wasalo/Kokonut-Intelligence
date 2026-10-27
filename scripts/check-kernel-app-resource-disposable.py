#!/usr/bin/env python3
"""Build and smoke the Kernel API under an isolated, bounded ARM64 runtime."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs/refactor/builds/2026-10-27-recovery/kernel-app-arm64-constrained-runtime.json"


class CheckFailure(RuntimeError):
    """A bounded disposable-smoke failure without leaking process output."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def run(command: list[str], *, timeout: int = 60, check: bool = True) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode:
        raise CheckFailure("docker", "a bounded Docker command failed")
    return result.stdout.strip()


def inspect_runtime(container: str) -> dict[str, object]:
    raw = run([
        "docker", "inspect", "--format",
        "{{.HostConfig.Memory}}|{{.HostConfig.MemorySwap}}|{{.HostConfig.NanoCpus}}|"
        "{{.HostConfig.PidsLimit}}|{{.HostConfig.ReadonlyRootfs}}|{{.HostConfig.NetworkMode}}|"
        "{{.Config.User}}|{{.State.Status}}",
        container,
    ])
    fields = raw.split("|")
    if len(fields) != 8:
        raise CheckFailure("runtime_contract", "Docker returned an invalid runtime inspection")
    memory, memory_swap, nano_cpus, pids, read_only, network, user, state = fields
    runtime = {
        "memory_bytes": int(memory),
        "memory_swap_bytes": int(memory_swap),
        "nano_cpus": int(nano_cpus),
        "pids_limit": int(pids),
        "root_filesystem_read_only": read_only.lower() == "true",
        "network_mode": network,
        "image_user": user,
        "state": state,
    }
    if (
        runtime["memory_bytes"] != 512 * 1024 * 1024
        or runtime["memory_swap_bytes"] != 512 * 1024 * 1024
        or runtime["nano_cpus"] != 1_000_000_000
        or runtime["pids_limit"] != 64
        or runtime["root_filesystem_read_only"] is not True
        or runtime["network_mode"] != "none"
        or runtime["image_user"] != "appuser"
        or runtime["state"] != "running"
    ):
        raise CheckFailure("runtime_contract", "the running container does not match the bounded runtime contract")
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("linux/arm64", "linux/amd64"), default="linux/arm64")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--health-timeout", type=int, default=120)
    args = parser.parse_args()
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    if args.health_timeout < 20 or args.health_timeout > 600:
        parser.error("--health-timeout must be between 20 and 600 seconds")

    token = uuid.uuid4().hex[:12]
    image = f"kokonut-kernel-app-resource-smoke:{token}"
    container = f"kokonut-kernel-app-resource-smoke-{token}"
    architecture = {"linux/arm64": "aarch64", "linux/amd64": "x86_64"}[args.platform]
    evidence: dict[str, object] = {
        "result": "failed",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": run(["git", "rev-parse", "--short", "HEAD"]),
        "source_tree": "working-tree snapshot",
        "platform": args.platform,
        "execution_host_architecture": platform.machine(),
        "target_architecture": architecture,
        "runtime_contract": {
            "memory_mib": 512,
            "memory_swap_mib": 512,
            "cpus": 1,
            "pids_limit": 64,
            "network": "none",
            "root_filesystem": "read-only",
            "tmpfs": {"/tmp_mib": 64, "/gateway_audit_mib": 16},
            "published_ports": 0,
        },
        "database_or_provider_calls": False,
        "candidate_or_legacy_touched": False,
        "container_removed": False,
        "temporary_image_removed": False,
        "limitations": [
            "The API is launched without PostgreSQL or external providers; this is process liveness, not schema readiness or data-path acceptance.",
            "Docker software emulation does not establish Raspberry Pi hardware power-loss, thermal, sustained-performance, or endurance behavior.",
            "The 512 MiB, one-CPU budget is a reproducible local profile sample, not a production sizing recommendation.",
        ],
    }
    failure: CheckFailure | None = None
    try:
        evidence["stage"] = "build"
        run([
            "docker", "buildx", "build", "--file", "Dockerfile.kernel", "--platform", args.platform,
            "--target", "kernel", "--tag", image, "--load", "--progress=quiet", ".",
        ], timeout=2400)
        image_info = run([
            "docker", "image", "inspect", image, "--format", "{{.Os}}/{{.Architecture}}|{{.Id}}|{{.Size}}",
        ]).split("|")
        if len(image_info) != 3 or image_info[0] != args.platform:
            raise CheckFailure("image_validation", "the built image platform did not match the requested target")
        evidence["image"] = {
            "platform": image_info[0],
            "image_id": image_info[1],
            "size_bytes": int(image_info[2]),
        }

        evidence["stage"] = "runtime_start"
        python = (
            "import uvicorn; from services.gateway.app import create_app; "
            "uvicorn.run(create_app(), host='127.0.0.1', port=8099, log_level='error')"
        )
        run([
            "docker", "run", "--detach", "--name", container,
            "--label", "com.kokonut.refactor=kernel-app-resource-smoke",
            "--platform", args.platform,
            "--network", "none",
            "--memory", "512m", "--memory-swap", "512m", "--cpus", "1.0", "--pids-limit", "64",
            "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=67108864",
            "--tmpfs", "/var/lib/kokonut/gateway-audit:rw,noexec,nosuid,size=16777216,uid=10001,gid=10001",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "-e", "KOKONUT_ENV=development",
            "-e", "KOKONUT_OPERATOR_OIDC_ENABLED=false",
            "-e", "KOKONUT_RATE_LIMIT_PROVIDER=local",
            "-e", "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH=/var/lib/kokonut/gateway-audit/audit.sqlite3",
            "-e", "PG_HOST=127.0.0.1", "-e", "PG_PORT=5432", "-e", "PG_DB=kokonut_intelligence",
            "-e", "PG_USER=kokonut",
            image, "python3", "-c", python,
        ])
        runtime = inspect_runtime(container)
        evidence["runtime"] = runtime

        evidence["stage"] = "health"
        deadline = time.monotonic() + args.health_timeout
        health = "starting"
        while time.monotonic() < deadline:
            state = run([
                "docker", "inspect", "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
                container,
            ], check=False)
            if not state:
                raise CheckFailure("health", "the API container stopped before health acceptance")
            state_fields = state.split("|")
            if len(state_fields) != 2:
                raise CheckFailure("health", "Docker returned an invalid health state")
            if state_fields[0] != "running":
                raise CheckFailure("health", "the API container stopped before health acceptance")
            health = state_fields[1]
            if health == "healthy":
                break
            if health == "unhealthy":
                raise CheckFailure("health", "the API health check reported unhealthy")
            time.sleep(1)
        if health != "healthy":
            raise CheckFailure("health", "the API health check did not become healthy before timeout")

        body = run([
            "docker", "exec", container, "python3", "-c",
            "import json,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8099/health', timeout=3); "
            "print(json.dumps(json.load(r), sort_keys=True))",
        ])
        try:
            health_body = json.loads(body)
        except json.JSONDecodeError as exc:
            raise CheckFailure("health", "the Gateway returned invalid health JSON") from exc
        if health_body.get("status") != "ok" or health_body.get("service") != "gateway":
            raise CheckFailure("health", "the Gateway liveness response did not match its contract")
        evidence["health"] = {
            "docker_health": health,
            "status": health_body["status"],
            "service": health_body["service"],
            "version": health_body.get("version"),
            "audit_capture": health_body.get("audit_capture"),
        }
        evidence["result"] = "passed"
    except CheckFailure as exc:
        failure = exc
        evidence["failed_stage"] = exc.stage
        evidence["failure"] = str(exc)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        failure = CheckFailure(str(evidence.get("stage", "unknown")), type(exc).__name__)
        evidence["failed_stage"] = failure.stage
        evidence["failure"] = str(failure)
    finally:
        if run(["docker", "inspect", container, "--format", "{{.Id}}"], check=False):
            run(["docker", "rm", "--force", container], check=False)
        evidence["container_removed"] = not bool(
            run(["docker", "inspect", container, "--format", "{{.Id}}"], check=False)
        )
        if run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], check=False):
            run(["docker", "image", "rm", "--force", image], check=False)
        evidence["temporary_image_removed"] = not bool(
            run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], check=False)
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    if failure:
        print(f"Kernel ARM64 constrained runtime check failed at {failure.stage}; see {output_path}")
        return 1
    try:
        display_path = output_path.relative_to(ROOT)
    except ValueError:
        display_path = output_path
    print(f"Kernel API ARM64 constrained runtime check passed; evidence: {display_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
