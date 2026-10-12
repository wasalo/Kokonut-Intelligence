"""Dashboard refresh flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job


@flow(name="dashboard-refresh", retries=2, retry_delay_seconds=300)
def dashboard_refresh_flow():
    """Refresh all dashboard datasets."""
    return run_job("dashboards")
