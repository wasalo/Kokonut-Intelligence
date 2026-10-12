"""RPC wallet indexing flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="rpc-indexing", retries=3, retry_delay_seconds=120)
def rpc_indexing_flow():
    """Index Ethereum/L2 wallet activity."""
    return run_job("rpc")
