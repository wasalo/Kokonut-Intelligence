"""EAS attestation indexing flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="eas-indexing", retries=3, retry_delay_seconds=60)
def eas_indexing_flow():
    """Index EAS attestations from Celo/Optimism/Base."""
    return run_job("eas")
