"""Weather ingestion flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="weather-ingestion", retries=2, retry_delay_seconds=300)
def weather_ingestion_flow(location_id: str = None):
    """Fetch weather data for all active locations."""
    return run_job("weather", location_id=location_id if location_id else None)
