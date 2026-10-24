"""Anomaly detection flow."""

from services.core.adapters.prefect import flow
from services.core.jobs import run_job_for_kokonut_network_locations


@flow(name="anomaly-detection", retries=2, retry_delay_seconds=300)
def anomaly_detection_flow():
    """Run rule-based and ML anomaly detection."""
    return run_job_for_kokonut_network_locations("anomaly")
