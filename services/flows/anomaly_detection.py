"""Anomaly detection flow."""

from prefect import flow


@flow(name="anomaly-detection", retries=2, retry_delay_seconds=300)
def anomaly_detection_flow():
    """Run rule-based and ML anomaly detection."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.ingestion.anomaly_detector"],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Anomaly detection failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
