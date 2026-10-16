"""Reviewable, disabled scheduler definitions for known Kernel jobs.

No database access, execution, or schedule registration occurs here.
"""

from types import MappingProxyType
from uuid import UUID

from services.core.jobs import JOBS
from services.security.scheduled_command_contracts import validate_scheduled_command

CADENCES = MappingProxyType(
    {
        "hourly": "0 * * * *",
        "every-6h": "0 */6 * * *",
        "daily": "0 6 * * *",
        "weekly": "0 3 * * 0",
    }
)


def build_job_plan(job_id: str, cadence: str, *, location_id: str | None = None) -> dict:
    """Map a command contract to existing scheduled_task fields, disabled.

    These are independent operations, not an equivalent pipeline DAG. The
    catalog never expands the scheduler's module allowlist.
    """
    spec = JOBS[job_id]
    if job_id == "sensors":
        raise ValueError("Sensor scheduling requires an explicit input contract")
    arguments = list(spec.arguments)
    name = f"kernel-{job_id}-{cadence}"
    if "location_id" in spec.required_inputs and location_id is None:
        raise ValueError(f"{job_id.capitalize()} schedule planning requires one location")
    if location_id is not None:
        if job_id != "weather" and "location_id" not in spec.required_inputs:
            raise ValueError("Location override is supported only for weather and climate")
        location = str(UUID(str(location_id)))
        arguments.extend(("--location-id", location))
        name += f"-{location}"
    validate_scheduled_command(spec.module, arguments)
    return {
        "job_id": job_id,
        "timezone": "UTC",
        "activation_ready": False,
        "scheduled_task": {
            "name": name,
            "module_path": spec.module,
            "command_args": arguments,
            "cron_expression": CADENCES[cadence],
            "priority": "normal",
            "timeout_seconds": spec.timeout_seconds,
            "max_retries": spec.retries,
            "retry_delay_seconds": spec.retry_delay_seconds,
            "allow_overlap": False,
            "is_enabled": False,
            "depends_on": [],
            "dependency_mode": "same_window",
        },
        "required_review": [
            "Disable the previous dispatcher before activation",
            "Confirm profile dependencies and required credentials",
            "Review command outcomes and retry idempotency",
            "Reconcile in-flight runs and select the first next_run_at",
            "Validate dependency ordering for the current run window",
        ],
    }
