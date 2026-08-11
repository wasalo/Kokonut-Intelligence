"""State-of-Kokonut and network-level report generators."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from ..kokonut_graphs import build_all
from .common import (
    _serialize_rows,
)
from .commons import (
    generate_community_governance,
    generate_foundational_wellbeing,
    generate_gnh_alignment,
    generate_regenerative_outcomes,
)
from .core import (
    generate_climate_impact,
    generate_crop_noi,
    generate_environmental,
    generate_farm_summary,
)
from .operations import generate_training_impact
from .strategy import generate_capital_accounting, generate_stakeholder_outcomes
from .wellbeing import (
    generate_capital_efficiency,
    generate_financial_sustainability,
    generate_holistic_wellbeing,
)


def _state_of_kokonut_locations(conn, location_ids, period_start, period_end):
    """Compose per-location reports across one, many, or all locations."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_ids:
        cur.execute(
            "SELECT id, name, slug, country, region, status FROM location WHERE id = ANY(%s) ORDER BY name",
            (list(location_ids),),
        )
    else:
        cur.execute("SELECT id, name, slug, country, region, status FROM location ORDER BY name")
    locations = [dict(r) for r in cur.fetchall()]
    cur.close()

    composed = []
    for loc in locations:
        loc_id = str(loc["id"])
        entry = {
            "location_id": loc_id,
            "name": loc.get("name"),
            "slug": loc.get("slug"),
            "country": loc.get("country"),
            "region": loc.get("region"),
            "sections": {},
        }
        # Compose existing per-location generators; one failure must not break the composite.
        for section, fn in (
            ("farm_summary", generate_farm_summary),
            ("crop_noi", generate_crop_noi),
            ("environmental", generate_environmental),
            ("climate_impact", generate_climate_impact),
            ("financial_sustainability", generate_financial_sustainability),
            ("capital_efficiency", generate_capital_efficiency),
            ("holistic_wellbeing", generate_holistic_wellbeing),
            ("community_governance", generate_community_governance),
            ("gnh_alignment", generate_gnh_alignment),
            ("training_impact", generate_training_impact),
            ("regenerative_outcomes", generate_regenerative_outcomes),
        ):
            try:
                entry["sections"][section] = fn(conn, loc_id, period_start, period_end)
            except Exception as exc:  # noqa: BLE001 - keep composite resilient
                entry["sections"][section] = {"error": f"{type(exc).__name__}: {exc}"}
        composed.append(entry)
    return locations, composed


def _state_of_kokonut_actors(conn, period_start, period_end):
    """Ecosystem-actor view: funding raised + participation by actor type."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    period_filter = """
        AND (%s::date IS NULL OR fr.period_start IS NULL OR fr.period_start >= %s::date)
        AND (%s::date IS NULL OR fr.period_end IS NULL OR fr.period_end <= %s::date)
    """
    params = [period_start, period_start, period_end, period_end]

    cur.execute(
        f"""
        SELECT fr.actor_type, fr.actor_name,
               COUNT(*) AS rounds,
               COALESCE(SUM(fr.raised_amount), 0) AS total_raised,
               fr.currency
        FROM funding_round fr
        WHERE 1=1 {period_filter}
        GROUP BY fr.actor_type, fr.actor_name, fr.currency
        ORDER BY fr.actor_type
        """,
        params,
    )
    by_actor = [dict(r) for r in cur.fetchall()]

    cur.execute(
        f"""
        SELECT fr.source_type, COALESCE(SUM(fr.raised_amount), 0) AS total_raised
        FROM funding_round fr
        WHERE 1=1 {period_filter}
        GROUP BY fr.source_type
        ORDER BY total_raised DESC
        """,
        params,
    )
    by_source = [dict(r) for r in cur.fetchall()]

    cur.execute(
        f"""
        SELECT pf.actor_type, pf.decision_status,
               COUNT(*) AS count, COALESCE(SUM(pf.amount), 0) AS amount
        FROM project_funding pf
        JOIN funding_round fr ON fr.id = pf.funding_round_id
        WHERE 1=1 {period_filter}
        GROUP BY pf.actor_type, pf.decision_status
        ORDER BY pf.actor_type, pf.decision_status
        """,
        params,
    )
    participation = [dict(r) for r in cur.fetchall()]

    cur.execute(
        f"""
        SELECT fr.round_code, fr.actor_type, fr.actor_name, fr.round_name,
               fr.raised_amount, fr.currency, fr.source_type, fr.period_start, fr.period_end,
               fr.location_id
        FROM funding_round fr
        WHERE 1=1 {period_filter}
        ORDER BY fr.period_start, fr.actor_type
        """,
        params,
    )
    rounds = [dict(r) for r in cur.fetchall()]

    total_raised = sum(float(r.get("total_raised") or 0) for r in by_actor)
    cur.close()
    return {
        "by_actor": _serialize_rows(by_actor),
        "by_source": _serialize_rows(by_source),
        "participation": _serialize_rows(participation),
        "rounds": _serialize_rows(rounds),
        "total_raised": round(total_raised, 2),
    }


def generate_state_of_kokonut(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a network/ecosystem-level "State of Kokonut" report.

    Aggregates existing per-location generators across one, many, or all
    locations (selected via ``location_id`` as a comma-separated list or repeated
    flag) within an optional date range, and adds an ecosystem-actor view
    (Network / DAO / Foundation / Genesis / Seeds) showing funding raised,
    funding sources, and per-project participation decisions.

    Read-only; never modifies governed data.
    """
    # Normalize location selection: comma-separated list or single id.
    location_ids = None
    if location_id and location_id.lower() != "all":
        location_ids = [lid.strip() for lid in location_id.split(",") if lid.strip()]

    locations, composed = _state_of_kokonut_locations(conn, location_ids, period_start, period_end)
    actors = _state_of_kokonut_actors(conn, period_start, period_end)

    # Lightweight ecosystem rollups from composed sections.
    total_revenue = 0.0
    total_expenses = 0.0
    total_harvest = 0.0
    locations_with_data = 0
    for entry in composed:
        fs = entry.get("sections", {}).get("farm_summary")
        if isinstance(fs, dict) and "financial_summary" in fs:
            locations_with_data += 1
            try:
                total_revenue += float(fs["financial_summary"].get("total_revenue") or 0)
                total_expenses += float(fs["financial_summary"].get("total_expenses") or 0)
            except (TypeError, ValueError):
                pass
        hs = entry.get("sections", {}).get("farm_summary")
        if isinstance(hs, dict) and "harvest_summary" in hs:
            try:
                total_harvest += float(hs["harvest_summary"].get("total_quantity") or 0)
            except (TypeError, ValueError):
                pass

    return {
        "report_type": "state_of_kokonut",
        "scope": "all_locations" if location_ids is None else "selected_locations",
        "selected_location_ids": location_ids,
        "period_start": period_start,
        "period_end": period_end,
        "ecosystem_overview": {
            "total_locations": len(locations),
            "locations_with_financial_data": locations_with_data,
            "total_revenue_usd": round(total_revenue, 2),
            "total_expenses_usd": round(total_expenses, 2),
            "net_income_usd": round(total_revenue - total_expenses, 2),
            "total_harvest_quantity": round(total_harvest, 2),
        },
        "actor_view": actors,
        "locations": composed,
        "limitations": [
            "Composite of existing per-location generators; one failing section is isolated and reported as an error rather than breaking the composite.",
            "Funding raised, funding sources, and actor participation come from the funding_round / project_funding tables (seeded pilot data); they are self-reported and not on-chain verified.",
            "Ecosystem actors (Network / DAO / Foundation / Genesis / Seeds) are modeled as funding/participation actors, not as separate legal-entity records.",
            "Multimedia, narrative storytelling, and community-impact stories are out of scope for this structured report.",
            "Public aggregate views exclude unverified metrics per platform governance.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_state_of_kokonut_graphs(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate visual graph descriptors for the State of Kokonut report.

    Builds structured graph descriptors (nodes, edges, layout) and Mermaid text
    for the ecosystem journey tree, the circular Ikigai framework view (v1 and
    v2), and -- when a location is selected -- farm development phases and
    Kokonut Seeds short-cycle crop timelines. Output is JSON + Mermaid only;
    no charting library is required and nothing is rendered server-side.

    Read-only; never modifies governed data.
    """
    descriptors = build_all(conn, location_id=location_id, period_start=period_start, period_end=period_end)
    graphs = []
    for desc in descriptors:
        try:
            graphs.append(
                {
                    "name": desc.name,
                    "layout": desc.layout,
                    "title": desc.title,
                    "descriptor": desc.to_json(),
                    "mermaid": desc.to_mermaid(),
                }
            )
        except Exception as exc:  # isolate a failing graph, mirror state_of_kokonut
            print(f"  ⚠ graph {desc.name} failed: {exc}")
            graphs.append(
                {
                    "name": desc.name,
                    "layout": desc.layout,
                    "title": desc.title,
                    "error": str(exc),
                }
            )

    return {
        "report_type": "state_of_kokonut_graphs",
        "scope": "all_locations" if location_id in (None, "all") else "selected_locations",
        "selected_location_ids": None if location_id in (None, "all") else location_id,
        "period_start": period_start,
        "period_end": period_end,
        "graphs": graphs,
        "limitations": [
            "Graphs are rendered as dependency-free Mermaid text + JSON descriptors; a true radial SVG/chord layout for the circular Ikigai view is a separate follow-up (HTML/SVG) task.",
            "Funding rounds and DAO proposals drive the ecosystem tree and Ikigai quadrants; these are seeded pilot data, self-reported, not on-chain verified.",
            "Farm development phases come from farm_zone zone_type; crop timelines come from crop_cycle plant/harvest dates.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_comprehensive_status(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate a single Comprehensive Status Report for a location or network-wide.

    Composes the canonical per-location sections (farm, crop NOI, environmental,
    climate impact, financial sustainability, capital efficiency, holistic and
    foundational wellbeing, community governance, GNH alignment, training
    impact, regenerative outcomes, stakeholder outcomes) into one document for
    one, many, or all locations. When no location is selected (or ``--all``),
    the report is network-wide: it nests per-location bundles and adds an
    ecosystem rollup. Each section is called defensively; one failure is
    isolated and reported as an error rather than breaking the composite.

    Read-only; never modifies governed data.
    """
    location_ids = None
    if location_id and location_id.lower() != "all":
        location_ids = [lid.strip() for lid in location_id.split(",") if lid.strip()]

    # Reuse the per-location composition helper from state_of_kokonut, then
    # extend the section set with wellbeing/stakeholder outcomes.
    locations, composed = _state_of_kokonut_locations(conn, location_ids, period_start, period_end)

    extended = []
    for entry in composed:
        loc_id = entry["location_id"]
        for section, fn in (
            ("foundational_wellbeing", generate_foundational_wellbeing),
            ("stakeholder_outcomes", generate_stakeholder_outcomes),
        ):
            try:
                entry["sections"][section] = fn(conn, loc_id, period_start, period_end)
            except Exception as exc:  # noqa: BLE001 - keep composite resilient
                entry["sections"][section] = {"error": f"{type(exc).__name__}: {exc}"}
        try:
            entry["sections"]["capital_accounting"] = generate_capital_accounting(
                conn, loc_id, period_start, period_end
            )
        except Exception as exc:  # noqa: BLE001 - keep composite resilient
            entry["sections"]["capital_accounting"] = {"error": f"{type(exc).__name__}: {exc}"}
        extended.append(entry)

    # Network-wide rollup from composed financial/environmental summaries.
    total_revenue = 0.0
    total_expenses = 0.0
    total_harvest = 0.0
    locations_with_data = 0
    for entry in extended:
        fs = entry.get("sections", {}).get("farm_summary")
        if isinstance(fs, dict) and "financial_summary" in fs:
            locations_with_data += 1
            try:
                total_revenue += float(fs["financial_summary"].get("total_revenue") or 0)
                total_expenses += float(fs["financial_summary"].get("total_expenses") or 0)
            except (TypeError, ValueError):
                pass
        hs = entry.get("sections", {}).get("farm_summary")
        if isinstance(hs, dict) and "harvest_summary" in hs:
            try:
                total_harvest += float(hs["harvest_summary"].get("total_quantity") or 0)
            except (TypeError, ValueError):
                pass

    return {
        "report_type": "comprehensive_status",
        "scope": "all_locations" if location_ids is None else "selected_locations",
        "selected_location_ids": location_ids,
        "period_start": period_start,
        "period_end": period_end,
        "ecosystem_overview": {
            "total_locations": len(locations),
            "locations_with_financial_data": locations_with_data,
            "total_revenue_usd": round(total_revenue, 2),
            "total_expenses_usd": round(total_expenses, 2),
            "net_income_usd": round(total_revenue - total_expenses, 2),
            "total_harvest_quantity": round(total_harvest, 2),
        },
        "locations": extended,
        "limitations": [
            "Composite of existing per-location generators; one failing section is isolated and reported as an error rather than breaking the composite.",
            "Public aggregate views exclude unverified metrics per platform governance.",
            "Funding/actor views are covered by the separate state_of_kokonut report; this report focuses on operational status per location and a network rollup.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_strategic_reserve(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a Strategic Reserve resilience report (location + network-wide).

    Surfaces shock-absorption capacity across the five reserve types
    (carbon_buffer, commons_reserve, financial_ringfence, capability_standby,
    seed_vault) with per-reserve adequacy, drawdown headroom, and
    trigger/breach status. When a location is selected, also includes the
    biodiversity/seed-vault proxy (distinct species/crop lines held as
    agro-biodiversity insurance). Network-wide (``--all`` / no location) covers
    every reserve and adds an ecosystem rollup.

    The mere existence of an adequately-funded reserve is surfaced as a
    fundability/due-diligence signal (the energy-reserve "investment
    incentive" parallel from the strategic-reserve literature).

    Read-only; never modifies governed data.
    """
    from services.strategic_reserve import health as srh

    location_ids = None
    if location_id and location_id.lower() != "all":
        location_ids = [lid.strip() for lid in location_id.split(",") if lid.strip()]

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_ids:
        cur.execute(
            "SELECT id, name FROM location WHERE id = ANY(%s) ORDER BY name",
            (list(location_ids),),
        )
    else:
        cur.execute("SELECT id, name FROM location ORDER BY name")
    locations = [dict(r) for r in cur.fetchall()]
    cur.close()

    # Network-level reserve health.
    net_health = srh.reserve_health(conn)
    reserves = net_health["reserves"]

    per_location = []
    for loc in locations:
        loc_id = str(loc["id"])
        try:
            seed = srh.seed_vault_health(conn, loc_id)
        except Exception as exc:  # noqa: BLE001 - isolate per-location failure
            seed = {"error": f"{type(exc).__name__}: {exc}"}
        per_location.append(
            {
                "location_id": loc_id,
                "name": loc.get("name"),
                "seed_vault": seed,
            }
        )

    # Fundability signal: fraction of reserves that are adequately funded.
    adequate = [
        r
        for r in reserves
        if isinstance(r.get("adequacy", {}).get("adequacy_pct"), (int, float)) and r["adequacy"]["adequacy_pct"] >= 100
    ]
    fundability_pct = round((len(adequate) / len(reserves)) * 100, 2) if reserves else None

    return {
        "report_type": "strategic_reserve",
        "scope": "all_locations" if location_ids is None else "selected_locations",
        "selected_location_ids": location_ids,
        "period_start": period_start,
        "period_end": period_end,
        "reserve_count": net_health["reserve_count"],
        "reserves": reserves,
        "fundability_signal": {
            "adequately_funded_reserves": len(adequate),
            "total_reserves": len(reserves),
            "fundability_pct": fundability_pct,
            "note": "Reserve adequacy reduces perceived risk and supports funding-round due diligence (strategic-reserve investment-incentive parallel).",
        },
        "locations": per_location,
        "limitations": [
            "Reserve health is monitor + propose only; release decisions require human approval via decision_policy.requires_approval / agents/safety.py. No automatic on-chain drawdown.",
            "Seed-vault biodiversity proxy uses distinct tree species + crop lines held; it is a resilience indicator, not a physical logistics system.",
            "Pilot reserves are seeded targets; held_quantity for derived reserves is computed from existing pilot tables and may be zero where source rows are absent.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_capital_provider_utility(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe capital-provider utility scenario report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_capital_provider_utility_summary
        WHERE location_id = %s
        ORDER BY utility_score DESC NULLS LAST, scenario_name
        """,
        (location_id,),
    )
    scenarios = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "capital_provider_utility",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "scenarios": _serialize_rows(scenarios),
        "limitations": [
            "Capital-provider utility scenarios are planning evidence, not an offer of securities or guaranteed returns.",
            "Private funder terms, side letters, and unpublished negotiations are excluded.",
            "Public-goods, verification, and learning outputs should be evaluated alongside financial risk.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
