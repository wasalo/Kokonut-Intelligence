"""Sensor ingestion flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="sensor-ingestion", retries=0)
def sensor_ingestion_flow(location_id: str, driver_instance_id: str):
    """Run one configured sensor pull instance for its owning location."""
    return run_job(
        "sensors",
        location_id=location_id,
        driver_instance_id=driver_instance_id,
    )
