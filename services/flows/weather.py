"""Weather ingestion flow."""

from prefect import flow


@flow(name="weather-ingestion", retries=2, retry_delay_seconds=300)
def weather_ingestion_flow(location_id: str = None):
    """Fetch weather data for all active locations."""
    import subprocess
    cmd = ["python3", "-m", "services.ingestion.weather"]
    if location_id:
        cmd.extend(["--location-id", location_id])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Weather ingestion failed: {result.stderr}")
    return {"status": "success", "output": result.stdout[-500:]}
