"""Provider-independent operations shared by workflow adapters.

This catalog does not register schedules or implement retries. The selected
durable dispatcher owns retries, leases, and run state.
"""

import subprocess
import sys
from dataclasses import dataclass
from types import MappingProxyType

from services.security.execution_allowlist import ALLOWED_SCHEDULED_MODULES
from services.security.scheduled_command_contracts import validate_scheduled_command


@dataclass(frozen=True)
class JobSpec:
    module: str
    arguments: tuple[str, ...]
    timeout_seconds: int
    retries: int
    retry_delay_seconds: int
    label: str
    required_inputs: tuple[str, ...] = ()

    @property
    def scheduler_allowed(self) -> bool:
        """Existing module policy; catalog membership does not grant permission."""
        return self.module in ALLOWED_SCHEDULED_MODULES


JOBS = MappingProxyType(
    {
        "weather": JobSpec(
            "services.ingestion.weather",
            (),
            300,
            2,
            300,
            "Weather ingestion",
            required_inputs=("location_id",),
        ),
        "sensors": JobSpec("services.ingestion.sensor_ingester", (), 120, 3, 60, "Sensor ingestion"),
        "market_data": JobSpec(
            "services.ingestion.market_data", ("--source", "world_bank"), 600, 2, 600, "Market data ingestion"
        ),
        "eas": JobSpec("services.ingestion.eas_indexer", (), 120, 3, 60, "EAS indexing"),
        "rpc": JobSpec("services.ingestion.rpc_indexer", (), 300, 3, 120, "RPC indexing"),
        "gnosis": JobSpec("services.ingestion.gnosis_indexer", (), 600, 2, 300, "Gnosis indexing"),
        "anomaly": JobSpec("services.ingestion.anomaly_detector", (), 300, 2, 300, "Anomaly detection"),
        "freshness": JobSpec("services.ingestion.data_freshness", ("--check",), 120, 2, 120, "Freshness check"),
        "metrics": JobSpec(
            "services.metrics",
            ("--compute", "--all"),
            1800,
            2,
            600,
            "Metrics computation",
            required_inputs=("location_id",),
        ),
        "noi_snapshots": JobSpec(
            "services.metrics", ("--reconcile-noi-snapshots",), 300, 2, 600, "Crop-cycle NOI snapshot reconciliation"
        ),
        "dashboards": JobSpec("services.export.dataset_refresh", ("--all",), 900, 2, 300, "Dashboard refresh"),
        "credit_adjustment": JobSpec(
            "services.analytics.carbon_credit_adjustment_check",
            (),
            600,
            2,
            600,
            "Credit adjustment check",
            required_inputs=("location_id",),
        ),
        "remote_sensing": JobSpec(
            "services.ingestion.remote_sensing_fetcher",
            ("--run-jobs", "--limit", "1"),
            1800,
            2,
            600,
            "Remote sensing fetch",
        ),
        "climate": JobSpec(
            "services.ingestion.climate_data",
            ("--all",),
            600,
            1,
            3600,
            "Climate data refresh",
            required_inputs=("location_id",),
        ),
        "projections": JobSpec(
            "services.ingestion.clickhouse_outbox",
            ("--run-once", "--limit", "100"),
            300,
            0,
            60,
            "Sensor and ingestion projection delivery",
        ),
    }
)


class JobFailed(RuntimeError):
    """A known command exited unsuccessfully."""

    def __init__(self, label: str, result: subprocess.CompletedProcess):
        self.returncode = result.returncode
        self.output = (result.stderr or result.stdout)[-500:]
        super().__init__(f"{label} failed: {result.stderr}")


def run_job(job_id: str, *, location_id: str | None = None) -> dict[str, str]:
    """Invoke one known operation; never accept arbitrary modules or arguments.

    Explicit invocation is separate from database-driven scheduler authorization.
    Metrics remain draft and credit checks do not confirm retirements.
    """
    spec = JOBS[job_id]
    arguments = list(spec.arguments)
    if "location_id" in spec.required_inputs and location_id is None:
        raise ValueError(f"{job_id.replace('_', ' ').capitalize()} refresh requires a location")
    if location_id is not None:
        if "location_id" not in spec.required_inputs:
            raise ValueError(f"{job_id.replace('_', ' ').capitalize()} does not accept a location")
        from uuid import UUID

        arguments.extend(("--location-id", str(UUID(str(location_id)))))
    if spec.scheduler_allowed:
        validate_scheduled_command(spec.module, arguments)
    result = subprocess.run(
        [sys.executable, "-m", spec.module, *arguments],
        capture_output=True,
        text=True,
        timeout=spec.timeout_seconds,
    )
    if result.returncode != 0:
        raise JobFailed(spec.label, result)
    return {"status": "success", "output": result.stdout[-500:]}


def kokonut_network_location_ids() -> list[str]:
    """List active locations assigned to the owner-selected Kokonut Network org."""
    from services.common.database import get_connection

    with get_connection(readonly=True) as connection:
        rows = connection.execute(
            """
            SELECT location.id
            FROM location
            JOIN organization ON organization.id = location.organization_id
            WHERE location.status = 'active'
              AND organization.status = 'active'
              AND organization.org_key = :org_key
            ORDER BY location.id
            """,
            {"org_key": "kokonut-network"},
        ).all()
    return [str(row["id"]) for row in rows]


def run_job_for_kokonut_network_locations(job_id: str) -> dict:
    """Run a location-scoped catalog job for active Kokonut Network locations.

    Native scheduled commands still take one explicit location per task. This
    helper preserves the optional Prefect adapter's historical fan-out without
    selecting unassigned or other-organization locations.
    """
    spec = JOBS[job_id]
    if "location_id" not in spec.required_inputs:
        raise ValueError(f"{job_id.replace('_', ' ').capitalize()} is not location-scoped")

    location_ids = kokonut_network_location_ids()
    if not location_ids:
        return {"status": "skipped", "reason": "No active Kokonut Network locations are assigned"}

    results = [
        {"location_id": location_id, **run_job(job_id, location_id=location_id)}
        for location_id in location_ids
    ]
    return {"status": "success", "locations_processed": len(results), "results": results}
