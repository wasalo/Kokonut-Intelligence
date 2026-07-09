"""RPC wallet indexing flow."""

from prefect import flow


@flow(name="rpc-indexing", retries=3, retry_delay_seconds=120)
def rpc_indexing_flow():
    """Index Ethereum/L2 wallet activity."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.ingestion.rpc_indexer"],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"RPC indexing failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
