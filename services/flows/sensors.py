"""Sensor ingestion flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="sensor-ingestion", retries=3, retry_delay_seconds=60)
def sensor_ingestion_flow():
    """Ingest sensor readings from CSV/API."""
    return run_job("sensors")
