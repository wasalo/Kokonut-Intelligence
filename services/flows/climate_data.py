"""Climate data refresh flow."""

from prefect import flow


@flow(name="climate-data-refresh", retries=1, retry_delay_seconds=3600)
def climate_data_flow():
    """Refresh climate covariates for all locations."""
    import subprocess
    # Get all active locations
    from services.common.db import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
    import psycopg2

    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD,
    )
    cur = conn.cursor()
    cur.execute("SELECT id FROM location WHERE status = 'active'")
    locations = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()

    results = []
    for loc_id in locations:
        result = subprocess.run(
            ["python3", "-m", "services.ingestion.climate_data", "--all", "--location-id", loc_id],
            capture_output=True, text=True, timeout=600,
        )
        results.append({
            "location_id": loc_id,
            "returncode": result.returncode,
            "output": result.stdout[-200:] if result.stdout else result.stderr[-200:],
        })

    failed = sum(1 for r in results if r["returncode"] != 0)
    return {"status": "success", "locations": len(locations), "failed": failed, "results": results}
