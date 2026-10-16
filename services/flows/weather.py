"""Weather ingestion flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job, run_job_for_kokonut_network_locations


@flow(name="weather-ingestion", retries=2, retry_delay_seconds=300)
def weather_ingestion_flow(location_id: str = None):
    """Fetch weather for one location or fan out across Kokonut Network."""
    if location_id:
        return run_job("weather", location_id=location_id)
    return run_job_for_kokonut_network_locations("weather")
