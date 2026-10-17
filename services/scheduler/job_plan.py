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


def build_job_plan(
    job_id: str,
    cadence: str,
    *,
    location_id: str | None = None,
    driver_instance_id: str | None = None,
    chain: str | None = None,
) -> dict:
    """Map a command contract to existing scheduled_task fields, disabled.

    These are independent operations, not an equivalent pipeline DAG. The
    catalog never expands the scheduler's module allowlist.
    """
    spec = JOBS[job_id]
    arguments = list(spec.arguments)
    name = f"kernel-{job_id}-{cadence}"
    supplied_inputs = {
        "location_id": location_id,
        "driver_instance_id": driver_instance_id,
        "chain": chain,
    }
    missing_inputs = [
        key for key in spec.required_inputs if supplied_inputs.get(key) is None
    ]
    if missing_inputs:
        labels = {
            "location_id": "one location",
            "driver_instance_id": "one driver instance",
            "chain": "one chain",
        }
        required = " and ".join(labels.get(key, key) for key in missing_inputs)
        job_label = {
            "eas": "EAS",
            "rpc": "RPC",
        }.get(job_id, job_id.replace("_", " ").capitalize())
        raise ValueError(
            f"{job_label} schedule planning requires {required}"
        )
    unexpected_inputs = [
        key for key, value in supplied_inputs.items()
        if value is not None and key not in spec.required_inputs
    ]
    if unexpected_inputs:
        raise ValueError(
            f"{job_id.replace('_', ' ').capitalize()} does not accept {', '.join(unexpected_inputs)}"
        )
    if location_id is not None:
        location = str(UUID(str(location_id)))
        arguments.extend(("--location-id", location))
        name += f"-{location}"
    if driver_instance_id is not None:
        instance = str(UUID(str(driver_instance_id)))
        arguments.extend(("--driver-instance-id", instance))
        name += f"-{instance}"
    if chain is not None:
        arguments.extend(("--chain", chain))
        name += f"-{chain}"
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
