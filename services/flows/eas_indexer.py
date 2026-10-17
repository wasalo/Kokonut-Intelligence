"""EAS attestation indexing flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job_for_eas_chains


@flow(name="eas-indexing", retries=3, retry_delay_seconds=60)
def eas_indexing_flow():
    """Index Celo first, then the other supported EAS chains explicitly."""
    return run_job_for_eas_chains()
