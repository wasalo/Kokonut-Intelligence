"""RPC wallet indexing flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job_for_rpc_chains


@flow(name="rpc-indexing", retries=3, retry_delay_seconds=120)
def rpc_indexing_flow():
    """Index each supported RPC chain as a separately scoped operation."""
    return run_job_for_rpc_chains()
