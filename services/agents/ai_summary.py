#!/usr/bin/env python3
"""
AI Summary Generator — Agent-generated narratives for locations

Queries recent operational, financial, and environmental data for a location
and generates a structured text summary. Stores results in the ai_summary table
only when --store is passed.

Usage:
    python3 -m services.agents.ai_summary --location-id UUID
    python3 -m services.agents.ai_summary --location-id UUID --summary-type financial
    python3 -m services.agents.ai_summary --location-id UUID --store
    python3 -m services.agents.ai_summary --list
    python3 -m services.agents.ai_summary --verify <id>  # digest inspection only; no lifecycle change
"""

import argparse
import hashlib
import uuid
from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import (
    validate_output,
    validate_task_capabilities,
    validate_task_inputs,
)
from services.common.database import get_db

_SOURCE_REFERENCE_LIMIT = 50
_SOURCE_REFERENCE_TABLES = {
    "harvest_event",
    "sales_event",
    "crop_cycle",
    "sensor_reading",
    "expense_event",
    "noi_snapshot",
    "soil_carbon_measurement",
    "species_observation",
    "remote_sensing_observation",
    "weather_observation",
    "crop",
    "expense_category",
}


def _collect_source_references(conn, location_id: str, scopes: dict[str, tuple[str, tuple, str, bool]]) -> dict:
    """Return bounded, location-qualified record references for a summary.

    Each scope tuple contains a fixed SQL predicate, its bind parameters, a
    fixed ordering expression, and whether the summary uses only the newest
    matching row. Table names and SQL fragments come from this module's static
    generator definitions; callers cannot supply query fragments.
    """
    if any(table not in _SOURCE_REFERENCE_TABLES for table in scopes):
        unsupported = next(table for table in scopes if table not in _SOURCE_REFERENCE_TABLES)
        raise ValueError(f"Unsupported AI-summary source table: {unsupported}")
    manifest = {}
    with conn.cursor() as cursor:
        for table, (predicate, parameters, ordering, latest_only) in scopes.items():
            if table == "crop":
                # Crop rows are shared reference data. Link only crops that
                # contributed to verified sales at this location.
                query = """
                    SELECT selected.id::text, COUNT(*) OVER () AS row_count
                      FROM (
                          SELECT DISTINCT crop.id
                            FROM public.crop AS crop
                            JOIN public.crop_cycle AS cycle ON cycle.crop_id = crop.id
                            JOIN public.sales_event AS sale ON sale.crop_cycle_id = cycle.id
                           WHERE cycle.location_id = %s
                             AND sale.location_id = %s
                             AND cycle.location_id = sale.location_id
                             AND sale.status IN ('verified', 'published')
                           ORDER BY crop.id
                      ) AS selected
                     ORDER BY selected.id
                     LIMIT %s
                """
                query_parameters = (location_id, location_id, _SOURCE_REFERENCE_LIMIT)
            elif table == "expense_category":
                # Expense categories are global taxonomy rows. Restrict them
                # to the same top-five, location-backed groups shown above.
                query = """
                    SELECT selected.id::text, COUNT(*) OVER () AS row_count
                      FROM (
                          SELECT category.id
                            FROM public.expense_category AS category
                            JOIN public.expense_event AS expense
                              ON expense.category = category.name
                           WHERE expense.location_id = %s
                             AND expense.status IN ('verified', 'published')
                           GROUP BY category.id, category.name
                           ORDER BY SUM(expense.amount) DESC, category.name
                           LIMIT 5
                      ) AS selected
                     ORDER BY selected.id
                     LIMIT %s
                """
                query_parameters = (location_id, _SOURCE_REFERENCE_LIMIT)
            elif latest_only:
                query = f"""
                    SELECT selected.id::text, COUNT(*) OVER () AS row_count
                      FROM (
                          SELECT id FROM public.{table}
                           WHERE location_id = %s AND ({predicate})
                           ORDER BY {ordering}
                           LIMIT 1
                      ) AS selected
                """
                query_parameters = (location_id, *parameters)
            else:
                query = f"""
                    SELECT id::text, COUNT(*) OVER () AS row_count
                      FROM public.{table}
                     WHERE location_id = %s AND ({predicate})
                     ORDER BY {ordering}
                     LIMIT %s
                """
                query_parameters = (location_id, *parameters, _SOURCE_REFERENCE_LIMIT)
            cursor.execute(query, query_parameters)
            rows = cursor.fetchall()
            count = int(rows[0][1]) if rows else 0
            record_ids = [str(row[0]) for row in rows]
            manifest[table] = {
                "record_ids": record_ids,
                "row_count": count,
                "truncated": count > len(record_ids),
            }
    return manifest


def get_pg():
    return get_db()


def _check_registry_backed(conn, location_id: str) -> bool:
    """Verify the location has a verified/published farm registry record."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM farm_registry_record fr
            WHERE fr.location_id = %s AND fr.status IN ('verified', 'published')
        )
        """,
        (location_id,),
    )
    result = cur.fetchone()[0]
    cur.close()
    return result


def generate_operations_summary(conn, location_id: str) -> dict:
    """Generate an operations summary from recent activity data."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT COUNT(*) as count, COALESCE(SUM(quantity), 0) as total_kg
        FROM harvest_event WHERE location_id = %s
        AND status IN ('verified', 'published')
        AND harvest_date >= CURRENT_DATE - INTERVAL '90 days'
    """, (location_id,))
    harvests = dict(cur.fetchone())

    cur.execute("""
        SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as total_usd
        FROM sales_event WHERE location_id = %s
        AND sale_date >= CURRENT_DATE - INTERVAL '90 days'
        AND status IN ('verified', 'published')
    """, (location_id,))
    sales = dict(cur.fetchone())

    cur.execute("""
        SELECT COUNT(*) as count
        FROM crop_cycle WHERE location_id = %s AND status = 'active'
    """, (location_id,))
    cycles = dict(cur.fetchone())

    cur.execute("""
        SELECT COUNT(*) as count, sensor_type
        FROM sensor_reading WHERE location_id = %s
        AND reading_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY sensor_type ORDER BY count DESC, sensor_type NULLS LAST LIMIT 3
    """, (location_id,))
    sensors = [dict(r) for r in cur.fetchall()]

    cur.close()

    source_references = _collect_source_references(conn, location_id, {
        "harvest_event": (
            "status IN ('verified', 'published') AND harvest_date >= CURRENT_DATE - INTERVAL '90 days'",
            (), "harvest_date, id", False,
        ),
        "sales_event": (
            "status IN ('verified', 'published') AND sale_date >= CURRENT_DATE - INTERVAL '90 days'",
            (), "sale_date, id", False,
        ),
        "crop_cycle": ("status = 'active'", (), "id", False),
        "sensor_reading": (
            "reading_date >= CURRENT_DATE - INTERVAL '30 days' AND EXISTS ("
            "SELECT 1 FROM (SELECT sensor_type FROM public.sensor_reading "
            "WHERE location_id = %s AND reading_date >= CURRENT_DATE - INTERVAL '30 days' "
            "GROUP BY sensor_type ORDER BY COUNT(*) DESC, sensor_type NULLS LAST LIMIT 3) "
            "AS top_sensor_types WHERE top_sensor_types.sensor_type "
            "IS NOT DISTINCT FROM sensor_reading.sensor_type)",
            (location_id,), "reading_date, id", False,
        ),
    })

    lines = [
        "## Operations Summary (Last 90 Days)",
        "",
        f"**Harvests:** {harvests['count']} events, {harvests['total_kg']:.1f} kg total",
        f"**Sales:** {sales['count']} transactions, ${sales['total_usd']:,.2f} revenue",
        f"**Active Cycles:** {cycles['count']} crop cycles in progress",
    ]

    if sensors:
        sensor_strs = [f"{s['sensor_type']} ({s['count']} readings)" for s in sensors]
        lines.append(f"**Sensors:** {', '.join(sensor_strs)}")

    return {
        "content": "\n".join(lines),
        "source_tables": ["harvest_event", "sales_event", "crop_cycle", "sensor_reading"],
        "source_references": source_references,
        "summary_type": "operations",
    }


def generate_financial_summary(conn, location_id: str) -> dict:
    """Generate a financial summary from revenue and expense data."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT c.name as crop_name, COALESCE(SUM(se.total_amount), 0) as revenue
        FROM sales_event se
        JOIN crop_cycle cc ON se.crop_cycle_id = cc.id
                           AND cc.location_id = se.location_id
        JOIN crop c ON cc.crop_id = c.id
        WHERE se.location_id = %s AND se.status IN ('verified', 'published')
        GROUP BY c.name ORDER BY revenue DESC
    """, (location_id,))
    revenue_by_crop = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT ec.name as category, COALESCE(SUM(ee.amount), 0) as total
        FROM expense_event ee
        JOIN expense_category ec ON ee.category = ec.name
        WHERE ee.location_id = %s AND ee.status IN ('verified', 'published')
        GROUP BY ec.name ORDER BY total DESC, ec.name LIMIT 5
    """, (location_id,))
    expenses = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT COALESCE(SUM(noi), 0) as total_noi,
               COALESCE(AVG(operating_margin_pct), 0) as avg_margin
        FROM noi_snapshot WHERE location_id = %s
    """, (location_id,))
    noi = dict(cur.fetchone())

    cur.close()

    source_references = _collect_source_references(conn, location_id, {
        "sales_event": (
            "status IN ('verified', 'published') AND EXISTS ("
            "SELECT 1 FROM public.crop_cycle AS cycle "
            "WHERE cycle.id = sales_event.crop_cycle_id "
            "AND cycle.location_id = sales_event.location_id)",
            (), "sale_date, id", False,
        ),
        "crop_cycle": (
            "id IN (SELECT DISTINCT se.crop_cycle_id FROM public.sales_event AS se "
            "WHERE se.location_id = %s AND se.status IN ('verified', 'published') "
            "AND se.crop_cycle_id IS NOT NULL)",
            (location_id,),
            "id",
            False,
        ),
        "expense_event": (
            "status IN ('verified', 'published') AND category IN ("
            "SELECT ee.category FROM public.expense_event AS ee "
            "JOIN public.expense_category AS ec ON ee.category = ec.name "
            "WHERE ee.location_id = %s AND ee.status IN ('verified', 'published') "
            "GROUP BY ee.category ORDER BY SUM(ee.amount) DESC, ee.category LIMIT 5)",
            (location_id,), "expense_date, id", False,
        ),
        "expense_category": ("TRUE", (), "id", False),
        "crop": ("TRUE", (), "id", False),
        "noi_snapshot": ("TRUE", (), "period_end, id", False),
    })

    total_revenue = sum(r["revenue"] for r in revenue_by_crop)
    total_expenses = sum(e["total"] for e in expenses)

    lines = [
        "## Financial Summary",
        "",
        f"**Total Revenue:** ${total_revenue:,.2f}",
    ]

    if revenue_by_crop:
        lines.append("**Revenue by Crop:**")
        for r in revenue_by_crop:
            lines.append(f"  - {r['crop_name']}: ${r['revenue']:,.2f}")

    lines.append("")
    lines.append(f"**Total Expenses:** ${total_expenses:,.2f}")

    if expenses:
        lines.append("**Top Expense Categories:**")
        for e in expenses[:3]:
            lines.append(f"  - {e['category']}: ${e['total']:,.2f}")

    lines.append("")
    lines.append(f"**Net Operating Income:** ${noi['total_noi']:,.2f}")
    lines.append(f"**Average Operating Margin:** {noi['avg_margin']:.1f}%")

    return {
        "content": "\n".join(lines),
        "source_tables": ["sales_event", "expense_event", "noi_snapshot", "crop_cycle", "crop", "expense_category"],
        "source_references": source_references,
        "summary_type": "financial",
    }


def generate_environmental_summary(conn, location_id: str) -> dict:
    """Generate an environmental summary from ecological data."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT carbon_tonnes_per_ha, measurement_date
        FROM soil_carbon_measurement
        WHERE location_id = %s ORDER BY measurement_date DESC, id DESC LIMIT 1
    """, (location_id,))
    carbon = cur.fetchone()

    cur.execute("""
        SELECT COUNT(DISTINCT species_name) as species_count,
               COUNT(*) as total_observations
        FROM species_observation WHERE location_id = %s
    """, (location_id,))
    biodiversity = dict(cur.fetchone())

    cur.execute("""
        SELECT ndvi, observation_date
        FROM remote_sensing_observation
        WHERE location_id = %s AND ndvi IS NOT NULL
        ORDER BY observation_date DESC, id DESC LIMIT 1
    """, (location_id,))
    ndvi = cur.fetchone()

    cur.execute("""
        SELECT COALESCE(SUM(rainfall_mm), 0) as total_rainfall,
               COALESCE(AVG(temperature_c), 0) as avg_temp
        FROM weather_observation
        WHERE location_id = %s
        AND observation_date >= CURRENT_DATE - INTERVAL '90 days'
    """, (location_id,))
    weather = dict(cur.fetchone())

    cur.close()

    source_references = _collect_source_references(conn, location_id, {
        "soil_carbon_measurement": ("TRUE", (), "measurement_date DESC, id DESC", True),
        "species_observation": ("TRUE", (), "observation_date, id", False),
        "remote_sensing_observation": (
            "ndvi IS NOT NULL", (), "observation_date DESC, id DESC", True,
        ),
        "weather_observation": (
            "observation_date >= CURRENT_DATE - INTERVAL '90 days'",
            (), "observation_date, id", False,
        ),
    })

    lines = ["## Environmental Summary", ""]

    if carbon:
        lines.append(f"**Soil Carbon:** {carbon['carbon_tonnes_per_ha']:.2f} tonnes/ha (measured {carbon['measurement_date']})")

    lines.append(f"**Biodiversity:** {biodiversity['species_count']} species observed across {biodiversity['total_observations']} observations")

    if ndvi:
        ndvi_val = float(ndvi['ndvi'])
        ndvi_health = "excellent" if ndvi_val > 0.7 else "good" if ndvi_val > 0.5 else "moderate" if ndvi_val > 0.3 else "poor"
        lines.append(f"**Vegetation Health:** NDVI {ndvi_val:.3f} ({ndvi_health}) — observed {ndvi['observation_date']}")

    lines.append(f"**Rainfall (90 days):** {weather['total_rainfall']:.1f} mm")
    lines.append(f"**Average Temperature:** {weather['avg_temp']:.1f}°C")

    return {
        "content": "\n".join(lines),
        "source_tables": ["soil_carbon_measurement", "species_observation", "remote_sensing_observation", "weather_observation"],
        "source_references": source_references,
        "summary_type": "environmental",
    }


GENERATORS = {
    "operations": generate_operations_summary,
    "financial": generate_financial_summary,
    "environmental": generate_environmental_summary,
}


def generate_combined(conn, location_id: str) -> dict:
    """Generate a combined summary from all generators."""
    sections = []
    all_sources = []
    all_references = {}

    for summary_type, gen_func in GENERATORS.items():
        if summary_type == "combined":
            continue
        result = gen_func(conn, location_id)
        sections.append(result["content"])
        all_sources.extend(result["source_tables"])
        all_references.update(result.get("source_references", {}))

    return {
        "content": "\n\n".join(sections),
        "source_tables": list(dict.fromkeys(all_sources)),
        "source_references": all_references,
        "summary_type": "combined",
    }


GENERATORS["combined"] = generate_combined


def store_summary(conn, location_id: str, summary_type: str, content: str,
                  source_tables: list, model_version: str = "rules-v1") -> str:
    """Store AI summary in the database as a draft."""
    validate_task_capabilities("ai_summary_synthesis")
    errors = validate_task_inputs(
        "ai_summary_synthesis",
        {"location_id": location_id, "summary_type": summary_type, "store": True},
    )
    if errors:
        raise ValueError("; ".join(errors))
    if summary_type not in GENERATORS:
        raise ValueError("Unsupported AI summary type")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("AI summary content must be a non-empty string")
    if not isinstance(source_tables, list) or any(
        not isinstance(table, str) or not table for table in source_tables
    ):
        raise ValueError("AI summary source_tables must be a list of non-empty strings")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("AI summary model_version must be a non-empty string")
    assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
    cur = conn.cursor()
    summary_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO ai_summary
            (id, subject_type, subject_id, summary_type, content,
             source_tables, model_version, status)
        VALUES (%s, 'location', %s, %s, %s, %s, %s, 'draft')
        RETURNING id
        """,
        (summary_id, location_id, summary_type, content, source_tables, model_version),
    )
    returned_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return returned_id


def list_summaries(conn, location_id: str = None):
    """List existing AI summaries."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if location_id:
            cur.execute(
                "SELECT id, summary_type, status, created_at, LEFT(content, 80) as preview FROM ai_summary WHERE subject_id = %s ORDER BY created_at DESC LIMIT 20",
                (location_id,),
            )
        else:
            cur.execute(
                "SELECT id, summary_type, status, created_at, NULL::text as preview "
                "FROM ai_summary ORDER BY created_at DESC LIMIT 20"
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()


def build_summary(conn, location_id: str, summary_type: str = "combined") -> dict[str, Any]:
    """Build a deterministic summary on a caller-owned location-scoped connection."""
    validate_task_capabilities("ai_summary_synthesis")
    errors = validate_task_inputs(
        "ai_summary_synthesis",
        {"location_id": location_id, "summary_type": summary_type, "store": False},
    )
    if errors:
        raise ValueError("; ".join(errors))
    assert_agent_action_allowed("read", "ai_summary", {"location_id": location_id})
    if summary_type not in GENERATORS:
        raise ValueError("Unsupported AI summary type")
    if not _check_registry_backed(conn, location_id):
        raise ValueError(f"Location {location_id} does not have a verified/published farm registry record")
    result = GENERATORS[summary_type](conn, location_id)
    summary = {
        "content": result["content"],
        "source_tables": result["source_tables"],
        "source_references": result.get("source_references", {}),
        "summary_type": result["summary_type"],
        "location_id": location_id,
    }
    errors = validate_output("ai_summary_synthesis", {"summary": summary})
    if errors:
        raise ValueError("; ".join(errors))
    return summary


def run_ai_summary(location_id: str, summary_type: str = "combined", store: bool = False) -> dict[str, Any]:
    """Generate and optionally store an AI summary with safety checks."""
    validate_task_capabilities("ai_summary_synthesis")
    errors = validate_task_inputs(
        "ai_summary_synthesis",
        {"location_id": location_id, "summary_type": summary_type, "store": store},
    )
    if errors:
        raise ValueError("; ".join(errors))
    assert_agent_action_allowed("read", "ai_summary", {"location_id": location_id})
    conn = get_pg()
    try:
        summary = build_summary(conn, location_id, summary_type)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_summary(
                conn,
                location_id,
                summary["summary_type"],
                summary["content"],
                summary["source_tables"],
            )
    finally:
        conn.close()
    return output


def _cli_uuid(parser: argparse.ArgumentParser, value: str, label: str) -> str:
    """Validate and normalize a UUID before a CLI branch opens the database."""
    try:
        return str(uuid.UUID(value))
    except (TypeError, ValueError, AttributeError):
        parser.error(f"{label} must be a UUID")


def main():
    parser = argparse.ArgumentParser(description="AI Summary Generator")
    parser.add_argument("--location-id", help="Location UUID")
    parser.add_argument("--summary-type", choices=list(GENERATORS.keys()), default="combined",
                        help="Type of summary to generate (default: combined)")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List summaries for --location-id, or explicitly across all locations",
    )
    parser.add_argument(
        "--all-locations",
        action="store_true",
        help="Allow an unfiltered summary inventory when used with --list (previews omitted)",
    )
    parser.add_argument(
        "--verify",
        help=(
            "Inspect a summary and compute its content digest; this does not "
            "compare a stored digest or change lifecycle status"
        ),
    )
    args = parser.parse_args()

    if args.all_locations and not args.list:
        parser.error("--all-locations requires --list")

    if args.list:
        if args.verify or args.store:
            parser.error("--list cannot be combined with --verify or --store")
        if args.all_locations and args.location_id:
            parser.error("--all-locations cannot be combined with --location-id")
        if not args.location_id and not args.all_locations:
            parser.error("--list requires --location-id or explicit --all-locations")
        if args.location_id:
            args.location_id = _cli_uuid(parser, args.location_id, "location-id")
        conn = get_pg()
        try:
            summaries = list_summaries(conn, args.location_id)
        finally:
            conn.close()
        if not summaries:
            print("No summaries found.")
        else:
            preview_heading = "Preview" if args.location_id else "Preview omitted (all locations)"
            print(f"{'ID':<38} {'Type':<15} {'Status':<12} {'Created':<20} {preview_heading}")
            print("-" * 120)
            for s in summaries:
                print(f"{str(s['id']):<38} {s['summary_type']:<15} {s['status']:<12} {str(s['created_at']):<20} {(s['preview'] or '')[:60]}")
        return

    if args.verify:
        args.verify = _cli_uuid(parser, args.verify, "summary-id")
        conn = get_pg()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                cur.execute("SELECT * FROM ai_summary WHERE id = %s", (args.verify,))
                row = cur.fetchone()
            finally:
                cur.close()
        finally:
            conn.close()
        if not row:
            print(f"Summary not found: {args.verify}")
        else:
            content_hash = hashlib.sha256(row["content"].encode()).hexdigest()
            print(f"ID: {row['id']}")
            print(f"Type: {row['summary_type']}")
            print(f"Status: {row['status']}")
            print("Lifecycle verification: not performed (read-only inspection)")
            print(f"Model: {row['model_version']}")
            print(f"Content SHA-256 (computed only; not compared): {content_hash}")
            print(f"Content length: {len(row['content'])} chars")
        return

    if not args.location_id:
        parser.error("--location-id is required (or use --list)")

    args.location_id = _cli_uuid(parser, args.location_id, "location-id")

    print(f"Generating {args.summary_type} summary for location {args.location_id}...")
    result = run_ai_summary(args.location_id, args.summary_type, store=args.store)

    print(f"Type: {result['summary']['summary_type']}")
    print(f"Sources: {', '.join(result['summary']['source_tables'])}")
    if "ai_summary_id" in result:
        print(f"Summary stored: {result['ai_summary_id']}")
    else:
        print("Summary not stored (use --store to save as draft)")
    print(f"\n--- Preview ---\n{result['summary']['content'][:500]}")


if __name__ == "__main__":
    main()
