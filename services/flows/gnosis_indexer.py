"""Gnosis Chain indexing flow."""

from prefect import flow


@flow(name="gnosis-indexing", retries=2, retry_delay_seconds=300)
def gnosis_indexing_flow():
    """Index Gnosis Chain governance events."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.ingestion.gnosis_indexer"],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Gnosis indexing failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
