#!/usr/bin/env python3
"""Compare shared JobSpec defaults with Kernel scheduler command contracts.

The report is a source-only catalog inventory. It does not query persisted
tasks, enable a schedule, or invoke a job.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.core.jobs import JOBS  # noqa: E402
from services.security.execution_allowlist import ALLOWED_SCHEDULED_MODULES  # noqa: E402
from services.security.scheduled_command_contracts import (  # noqa: E402
    ScheduledCommandRejected,
    validate_scheduled_command,
)


def build_inventory() -> dict:
    entries = []
    statuses = Counter()
    for name, job in sorted(JOBS.items()):
        if job.module not in ALLOWED_SCHEDULED_MODULES:
            status = "module_not_allowlisted"
            reason = "JobSpec module is outside the Kernel scheduled-module allowlist"
        else:
            try:
                validate_scheduled_command(job.module, list(job.arguments))
            except ScheduledCommandRejected as exc:
                status = "default_arguments_rejected"
                reason = str(exc)
            else:
                status = "default_arguments_accepted"
                reason = None
        statuses[status] += 1
        entries.append(
            {
                "job": name,
                "module": job.module,
                "argument_count": len(job.arguments),
                "status": status,
                "reason": reason,
            }
        )
    return {
        "version": 1,
        "generated_by": "scripts/worker_job_contract_inventory.py",
        "scope": (
            "Static comparison of the shared JobSpec catalog with the current module allowlist and command contracts. "
            "It does not inspect or modify persisted tasks, external Prefect schedules, provider state, or runtime execution."
        ),
        "summary": {
            "catalog_jobs": len(entries),
            "allowlisted_modules": len(ALLOWED_SCHEDULED_MODULES),
            "outcomes": dict(sorted(statuses.items())),
        },
        "jobs": entries,
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write generated job-contract inventory")
    group.add_argument("--check", type=Path, help="Fail if saved inventory is stale")
    args = parser.parse_args(argv)
    expected = _serialize(build_inventory())
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")
        return 0
    check = args.check if args.check.is_absolute() else ROOT / args.check
    try:
        actual = check.read_text(encoding="utf-8")
    except OSError:
        print(f"Missing worker JobSpec contract inventory: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Worker JobSpec contract inventory is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
