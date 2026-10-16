"""Sensor ingestion flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="sensor-ingestion", retries=0)
def sensor_ingestion_flow():
    """Reject recurring dispatch until a real sensor source is configured."""
    return run_job("sensors")
