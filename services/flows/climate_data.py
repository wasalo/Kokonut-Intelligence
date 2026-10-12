"""Climate data refresh flow."""

from services.core.adapters.prefect import flow
from services.core.climate_jobs import refresh_active_locations


@flow(name="climate-data-refresh", retries=1, retry_delay_seconds=3600)
def climate_data_flow():
    """Refresh climate covariates for all active locations."""
    return refresh_active_locations()
