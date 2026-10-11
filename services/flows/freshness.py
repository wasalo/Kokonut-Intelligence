"""Data freshness check flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="data-freshness-check", retries=2, retry_delay_seconds=120)
def freshness_check_flow():
    """Check data freshness across all sources."""
    return run_job("freshness")
