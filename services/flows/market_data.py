"""Market data ingestion flow."""

from prefect import flow


@flow(name="market-data-ingestion", retries=2, retry_delay_seconds=600)
def market_data_flow():
    """Fetch World Bank commodity prices."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.ingestion.market_data", "--source", "world_bank"],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Market data ingestion failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
