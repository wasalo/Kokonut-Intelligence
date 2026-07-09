"""Carbon credit adjustment flow."""

from prefect import flow


@flow(name="credit-adjustment", retries=2, retry_delay_seconds=600)
def credit_adjustment_flow():
    """Check and auto-adjust carbon credits."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "services.analytics.carbon_credits", "--check-adjustments"],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Credit adjustment check failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
