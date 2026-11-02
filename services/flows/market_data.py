"""Market data ingestion flow."""

from services.core.adapters.prefect import flow
from services.core.features import is_enabled
from services.core.jobs import run_job


def dispatch_market_data_job():
    """Skip the isolated provider job unless its dedicated worker is enabled."""
    if not is_enabled("isolated_market_data_worker"):
        return {
            "status": "skipped",
            "reason": "isolated_market_data_worker_disabled",
        }
    return run_job("market_data")


@flow(name="market-data-ingestion", retries=2, retry_delay_seconds=600)
def market_data_flow():
    """Fetch World Bank commodity prices."""
    return dispatch_market_data_job()
