"""Price feed ingestion flow."""

from prefect import flow


@flow(name="price-feed-ingestion", retries=2, retry_delay_seconds=600)
def price_feed_flow():
    """Fetch commodity prices from Yahoo Finance and attestation."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.ingestion.yahoo_finance"],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Yahoo Finance fetch failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
