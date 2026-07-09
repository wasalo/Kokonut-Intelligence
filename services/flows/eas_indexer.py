"""EAS attestation indexing flow."""

from prefect import flow


@flow(name="eas-indexing", retries=3, retry_delay_seconds=60)
def eas_indexing_flow():
    """Index EAS attestations from Celo/Optimism/Base."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.ingestion.eas_indexer"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"EAS indexing failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
