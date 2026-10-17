"""Sequential climate fan-out without an orchestration SDK."""

import subprocess

from services.core.jobs import JobFailed, kokonut_network_location_ids, run_job


class ClimateRefreshFailed(RuntimeError):
    """Retain per-location outcomes for the dispatcher's failure record."""

    def __init__(self, report: dict):
        self.report = report
        super().__init__(f"Climate refresh failed for {report['failed']} of {report['locations']} locations")


def refresh_active_locations() -> dict:
    """Close the read connection before invoking bounded per-location commands.

    Complete the remaining locations after a command failure, then fail the
    aggregate so its dispatcher can report/retry it. No retry loop lives here.
    """
    locations = kokonut_network_location_ids()

    results = []
    for location_id in locations:
        try:
            result = run_job("climate", location_id=location_id)
            outcome = {"location_id": location_id, "returncode": 0, "output": result["output"][-200:]}
        except JobFailed as exc:
            outcome = {"location_id": location_id, "returncode": exc.returncode, "output": exc.output[-200:]}
        except subprocess.TimeoutExpired:
            outcome = {"location_id": location_id, "returncode": None, "output": "Climate command timed out"}
        results.append(outcome)

    failed = sum(result["returncode"] != 0 for result in results)
    report = {
        "status": "failed" if failed else "success",
        "locations": len(locations), "failed": failed, "results": results,
    }
    if failed:
        raise ClimateRefreshFailed(report)
    return report
