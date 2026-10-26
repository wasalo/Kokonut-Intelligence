#!/usr/bin/env python3
"""Run and clean up an internal-only disposable Directus role acceptance."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.kernel-recovery-directus-role.yml"
PROJECT = f"kokonut-directus-role-check-{uuid.uuid4().hex[:10]}"
EVIDENCE = ROOT / "docs/refactor/builds/2026-10-15-recovery/directus-runtime-role-disposable.json"


def run(command: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    env = os.environ.copy()
    env["POSTGRES_PASSWORD"] = secrets.token_urlsafe(32)
    env["KOKONUT_DIRECTUS_RUNTIME_PASSWORD"] = secrets.token_urlsafe(32)
    command = [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "-p",
        PROJECT,
        "-f",
        str(COMPOSE_FILE),
    ]
    failure: subprocess.CompletedProcess[str] | None = None
    try:
        result = run(
            [*command, "up", "--abort-on-container-exit", "--exit-code-from", "runner", "runner"],
            env=env,
        )
        if result.returncode:
            failure = result
        else:
            output_lines = []
            for line in result.stdout.splitlines():
                payload = line.rsplit("|", 1)[-1].strip()
                if payload.startswith("{"):
                    output_lines.append(payload)
            if not output_lines:
                raise RuntimeError("disposable role runner returned no sanitized JSON evidence")
            evidence = json.loads(output_lines[-1])
            if evidence.get("status") != "passed":
                raise RuntimeError("disposable role runner did not report acceptance")
            evidence["checked_at"] = datetime.now(timezone.utc).isoformat()
            EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
            EVIDENCE.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(evidence, indent=2, sort_keys=True))
    finally:
        cleanup = run([*command, "down", "--volumes", "--remove-orphans"], env=env)
        if cleanup.returncode:
            raise RuntimeError("failed to remove the disposable Directus role project")

    if failure is not None:
        print(f"Disposable Directus role acceptance failed (exit {failure.returncode}).", file=sys.stderr)
        diagnostic = "\n".join((failure.stdout or "", failure.stderr or ""))
        for secret_name in ("POSTGRES_PASSWORD", "KOKONUT_DIRECTUS_RUNTIME_PASSWORD"):
            diagnostic = diagnostic.replace(env[secret_name], "[redacted]")
        if diagnostic.strip():
            print("\n".join(diagnostic.splitlines()[-35:]), file=sys.stderr)
        return failure.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
