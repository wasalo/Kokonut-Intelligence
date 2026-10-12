"""Gnosis Chain indexing flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="gnosis-indexing", retries=2, retry_delay_seconds=300)
def gnosis_indexing_flow():
    """Index Gnosis Chain governance events."""
    return run_job("gnosis")
