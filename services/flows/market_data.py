"""Market data ingestion flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="market-data-ingestion", retries=2, retry_delay_seconds=600)
def market_data_flow():
    """Fetch World Bank commodity prices."""
    return run_job("market_data")
