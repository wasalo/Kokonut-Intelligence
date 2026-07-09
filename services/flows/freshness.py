"""Data freshness check flow."""

from prefect import flow


@flow(name="data-freshness-check", retries=2, retry_delay_seconds=120)
def freshness_check_flow():
    """Check data freshness across all sources."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.ingestion.data_freshness", "--check"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Freshness check failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
