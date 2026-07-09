"""Health check flow."""

from prefect import flow


@flow(name="health-check", retries=1, retry_delay_seconds=60)
def health_check_flow():
    """Run infrastructure health checks."""
    import subprocess
    result = subprocess.run(
        ["bash", "scripts/health-check.sh", "--json"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Health check failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
