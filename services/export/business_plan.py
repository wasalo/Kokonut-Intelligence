"""Business-plan assembler (composes existing EPS / VSM / analytics).

Builds a structured business plan at either the organization grain
(``org_id``) or the single-location grain (``location_id``), reusing:
  * Market overview            (services.analytics.marketplace)
  * Management & S&OP cockpit   (services.planning.sandop)
  * Financial plan + variance   (services.planning.budget)
  * Operational flow / VSM       (services.analytics.value_stream)
  * SWOT framework               (services.analytics.swot)
  * Reference-class dampening    (services.forecast.reference_class)

Read-only analysis; never mutates governed data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _section(conn, fn):
    try:
        return fn()
    except Exception as exc:  # best-effort: one missing source must not break the plan
        # A failed query aborts the whole transaction; roll back so the
        # remaining sections can still execute on a clean connection.
        try:
            conn.rollback()
        except Exception:
            pass
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def _org_locations(conn, org_id: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location WHERE organization_id = %s", (org_id,))
        return [str(r[0]) for r in cur.fetchall()]


def _market(conn, org_id: Optional[str], location_id: Optional[str]) -> Dict[str, Any]:
    from services.analytics.marketplace import get_market_overview

    if location_id:
        return {"grain": "location", "overview": get_market_overview(conn, location_id)}
    locs = _org_locations(conn, org_id)
    overviews = {}
    for loc in locs:
        try:
            overviews[loc] = get_market_overview(conn, loc)
        except Exception:
            continue
    return {"grain": "organization", "location_count": len(overviews), "overviews": overviews}


def _management(conn, org_id: Optional[str], location_id: Optional[str]) -> Dict[str, Any]:
    if not org_id:
        return {"note": "Management & S&OP cockpit is organization-scoped; provide --org-id."}
    from services.planning.sandop import cockpit

    return {"cockpit": cockpit(conn, org_id)}


def _financial(conn, org_id: Optional[str], location_id: Optional[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if location_id:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT noi, operating_margin_pct, calculated_at FROM noi_snapshot "
                "WHERE location_id = %s ORDER BY calculated_at DESC LIMIT 1",
                (location_id,),
            )
            row = cur.fetchone()
            if row:
                out["latest_noi_snapshot"] = {
                    "noi": float(row[0]) if row[0] is not None else None,
                    "operating_margin_pct": float(row[1]) if row[1] is not None else None,
                    "as_of": str(row[2]) if row[2] else None,
                }
    else:
        from services.planning.budget import list_plans, get_plan

        plans = list_plans(conn, org_id)
        out["plans"] = [
            {"id": str(p["id"]), "name": p.get("name"), "status": p.get("status")}
            for p in plans
        ]
    # Reference-class dampening (location grain required for comparable actuals).
    try:
        from services.forecast.reference_class import apply_reference_class

        rc_loc = location_id or (_org_locations(conn, org_id)[0] if org_id else None)
        if rc_loc:
            out["reference_class"] = apply_reference_class(conn, rc_loc, "crop_noi", 0.5)
    except Exception as exc:
        out["reference_class"] = {"available": False, "error": str(exc)}
    return out


def _flow(conn, org_id: Optional[str], location_id: Optional[str]) -> Dict[str, Any]:
    from services.analytics.value_stream import current_state_map, bottleneck_ranking

    if location_id:
        locs = [location_id]
    else:
        locs = _org_locations(conn, org_id)
    result = {}
    for loc in locs:
        try:
            result[loc] = {
                "current_state": current_state_map(conn, loc),
                "bottlenecks": bottleneck_ranking(conn, loc),
            }
        except Exception:
            continue
    return {"grain": "location" if location_id else "organization", "flow": result}


def _swot(conn, org_id: Optional[str], location_id: Optional[str]) -> Dict[str, Any]:
    from services.analytics.swot import list_swot, suggest

    try:
        existing = list_swot(conn, org_id, location_id)
    except Exception:
        existing = []
    if existing:
        return {"existing": existing}
    return {"suggested": suggest(conn, org_id, location_id)}


def _strategy(conn, org_id: Optional[str], location_id: Optional[str]) -> Dict[str, Any]:
    from services.analytics.strategy_execution import dashboard
    from services.analytics.strategy_kernel import list_strategy_plans
    from services.analytics.strategy_coherence import list_findings
    from services.analytics.competitive_report import report as competitive_report

    scope_type = "location" if location_id else "organization"
    scope_id = location_id or org_id
    plans = list_strategy_plans(conn, scope_type=scope_type, scope_id=scope_id)
    active = [plan for plan in plans if plan["status"] == "active"]
    out = {"scope_type": scope_type, "plans": plans, "active_plan_count": len(active), "execution": dashboard(conn, scope_type=scope_type, scope_id=scope_id)}
    if active:
        out["coherence_findings"] = list_findings(conn, str(active[0]["id"]))
        out["competitive_position"] = competitive_report(conn, str(active[0]["id"]))
    return out


def generate_business_plan(
    conn, location_id: Optional[str] = None, org_id: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    if not org_id and not location_id:
        raise ValueError("provide org_id or location_id")
    # Read-only analysis: autocommit keeps a failed query from poisoning
    # later sections (no aborted-transaction propagation).
    prev_autocommit = conn.autocommit
    conn.autocommit = True
    grain = "location" if location_id else "organization"

    plan = {
        "meta": {
            "grain": grain,
            "org_id": org_id,
            "location_id": location_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "market_analysis": _section(conn, lambda: _market(conn, org_id, location_id)),
        "management_governance": _section(conn, lambda: _management(conn, org_id, location_id)),
        "financial_plan": _section(conn, lambda: _financial(conn, org_id, location_id)),
        "operational_flow": _section(conn, lambda: _flow(conn, org_id, location_id)),
        "swot": _section(conn, lambda: _swot(conn, org_id, location_id)),
        "strategy_kernel": _section(conn, lambda: _strategy(conn, org_id, location_id)),
    }
    plan["executive_summary"] = _summarize(plan)
    conn.autocommit = prev_autocommit
    return plan


def _summarize(plan: Dict[str, Any]) -> str:
    grain = plan["meta"]["grain"]
    scope = plan["meta"].get("location_id") or plan["meta"].get("org_id")
    parts = [f"Business plan ({grain}): {scope}."]
    flow = plan.get("operational_flow", {})
    if isinstance(flow, dict) and "flow" in flow:
        parts.append(f"Operational flow captured for {len(flow['flow'])} location(s).")
    rc = plan.get("financial_plan", {}).get("reference_class") if isinstance(plan.get("financial_plan"), dict) else None
    if isinstance(rc, dict) and rc.get("damped_estimate") is not None:
        parts.append(
            f"Reference-class damped NOI estimate: {rc['damped_estimate']} "
            f"(alpha={rc['alpha']} over {rc['comparable_locations']} comparable locations)."
        )
    return " ".join(parts)


def main() -> None:
    import argparse
    import json

    from services.ingestion.base import get_db

    p = argparse.ArgumentParser(description="Generate business plan")
    p.add_argument("--org-id")
    p.add_argument("--location-id")
    args = p.parse_args()
    conn = get_db()
    try:
        out = generate_business_plan(conn, org_id=args.org_id, location_id=args.location_id)
    finally:
        conn.close()
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
