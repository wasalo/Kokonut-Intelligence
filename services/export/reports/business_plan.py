"""CLI-compatible adapter for the existing business-plan generator."""

from ..business_plan import generate_business_plan


def generate_business_plan_report(
    conn,
    location_id: str | None = None,
    _period_start: str | None = None,
    _period_end: str | None = None,
) -> dict:
    """Generate one business plan per requested location.

    The report CLI passes every generator the same four arguments. The
    standalone business-plan service instead accepts a location or org ID, so
    this adapter preserves that service while supporting a single location,
    comma-separated location selection, and the CLI's explicit ``--all``
    selection.
    """
    if not location_id:
        raise ValueError("business_plan requires a location scope")

    if location_id == "all":
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM location ORDER BY id")
            location_ids = [str(row[0]) for row in cur.fetchall()]
        scope = "all_locations"
    else:
        location_ids = [item.strip() for item in location_id.split(",")]
        if any(not item for item in location_ids):
            raise ValueError("business_plan location scope contains an empty identifier")
        scope = "location" if len(location_ids) == 1 else "selected_locations"

    plans = [
        generate_business_plan(conn, location_id=selected_location)
        for selected_location in location_ids
    ]
    if scope == "location":
        return {"report_type": "business_plan", **plans[0]}
    return {
        "report_type": "business_plan",
        "scope": scope,
        "location_count": len(plans),
        "plans": plans,
    }
