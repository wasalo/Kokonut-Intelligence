"""Remote sensing fetch flow."""

from prefect import flow


@flow(name="remote-sensing-fetch", retries=2, retry_delay_seconds=600)
def remote_sensing_flow():
    """Run all due remote sensing fetch jobs."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.ingestion.remote_sensing_fetcher", "--run-jobs"],
        capture_output=True, text=True, timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Remote sensing fetch failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
