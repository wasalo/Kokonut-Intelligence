"""Metrics computation flow."""

from prefect import flow


@flow(name="metrics-computation", retries=2, retry_delay_seconds=600)
def metrics_computation_flow():
    """Compute all governed metrics for all locations."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.metrics", "--compute", "--all-locations", "--verify"],
        capture_output=True, text=True, timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Metrics computation failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
