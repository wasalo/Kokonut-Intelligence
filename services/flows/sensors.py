"""Sensor ingestion flow."""

from prefect import flow


@flow(name="sensor-ingestion", retries=3, retry_delay_seconds=60)
def sensor_ingestion_flow():
    """Ingest sensor readings from CSV/API."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.ingestion.sensor_ingester"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Sensor ingestion failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
