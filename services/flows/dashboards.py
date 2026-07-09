"""Dashboard refresh flow."""

from prefect import flow


@flow(name="dashboard-refresh", retries=2, retry_delay_seconds=300)
def dashboard_refresh_flow():
    """Refresh all dashboard datasets."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.export.dataset_refresh", "--all"],
        capture_output=True, text=True, timeout=900,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Dashboard refresh failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
