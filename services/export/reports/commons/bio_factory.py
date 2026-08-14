"""Report generators: bio factory."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from services.common.database import query

from ..common import _serialize_rows


def generate_bio_factory_batch(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe bio-organic fertilizer batch report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_bio_factory_batch_summary
        WHERE (location_id = %s OR location_id IS NULL)
          AND (%s::date IS NULL OR production_start_date >= %s::date)
          AND (%s::date IS NULL OR production_end_date IS NULL OR production_end_date <= %s::date)
        ORDER BY production_start_date DESC, batch_name
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    batches = [dict(r) for r in cur.fetchall()]
    cur.close()
    total_kg = sum(float(row.get("output_kg_total") or 0) for row in batches)
    total_liters = sum(float(row.get("output_liters_total") or 0) for row in batches)
    return {
        "report_type": "bio_factory_batch",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "batches": _serialize_rows(batches),
        "total_kg_produced": round(total_kg, 2),
        "total_liters_produced": round(total_liters, 2),
        "limitations": [
            "Bio-factory batch yields are smallholder pilot evidence, not commercial production guarantees.",
            "Yield varies with feedstock moisture, microbial activity, and process conditions.",
            "Public recipes and batch records are not commercial endorsements.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_bio_input_provenance(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe bio-input provenance report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_bio_input_provenance_summary
        WHERE (location_id = %s OR location_id IS NULL)
        ORDER BY input_category, input_name
        """,
        (location_id,),
    )
    inputs = [dict(r) for r in cur.fetchall()]
    cur.close()
    lac_inputs = [
        row
        for row in inputs
        if row.get("origin_region")
        and any(
            keyword in (row.get("origin_region") or "").lower()
            for keyword in [
                "caribbean",
                "central america",
                "south america",
                "monte plata",
                "dominican",
                "mexico",
                "latin america",
                "sabana grande",
                "greater antilles",
            ]
        )
    ]
    return {
        "report_type": "bio_input_provenance",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "inputs": _serialize_rows(inputs),
        "lac_input_count": len(lac_inputs),
        "lac_input_share_pct": round(len(lac_inputs) / len(inputs) * 100, 1) if inputs else None,
        "limitations": [
            "Input provenance reflects documented supplier relationships, not full supply chain audits.",
            "Private supplier terms and pricing are excluded.",
            "LAC regional sourcing is documented per-batch; aggregate percentages are advisory.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_bio_recipe_library(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate a public-safe bio-organic fertilizer recipe library report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_bio_recipe_library_summary
            WHERE (location_id = %s OR location_id IS NULL)
            ORDER BY recipe_type, recipe_name
            """,
            (location_id,),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_bio_recipe_library_summary
            ORDER BY recipe_type, recipe_name
            """
        )
    recipes = [dict(r) for r in cur.fetchall()]
    cur.close()
    recipe_types: dict[str, int] = {}
    for row in recipes:
        rt = row.get("recipe_type")
        if rt:
            recipe_types[rt] = recipe_types.get(rt, 0) + 1
    return {
        "report_type": "bio_recipe_library",
        "location_id": location_id,
        "recipes": _serialize_rows(recipes),
        "recipe_type_breakdown": recipe_types,
        "limitations": [
            "Recipes are public knowledge for adaptation, not commercial endorsements.",
            "Recipe reusability is a planning signal, not a guarantee of results at scale.",
            "Quality warnings (e.g. sargassum arsenic, manure pathogens) must be followed.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_bio_quality_test(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe bio-factory quality test report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_bio_factory_quality_test_summary
        WHERE (location_id = %s OR location_id IS NULL)
          AND (%s::date IS NULL OR test_date >= %s::date)
          AND (%s::date IS NULL OR test_date <= %s::date)
        ORDER BY test_date DESC, parameter_name
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    tests = [dict(r) for r in cur.fetchall()]
    cur.close()
    test_count = len(tests)
    pass_count = sum(1 for row in tests if row.get("pass_fail") == "pass")
    return {
        "report_type": "bio_quality_test",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "tests": _serialize_rows(tests),
        "test_count": test_count,
        "pass_count": pass_count,
        "pass_rate_pct": round(pass_count / test_count * 100, 1) if test_count else None,
        "limitations": [
            "Quality test results are advisory, not certification or regulatory compliance.",
            "On-site lab results are not externally accredited unless lab_accredited = TRUE.",
            "Pass/fail thresholds are advisory and should be calibrated to specific use cases.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_bio_regional_input(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate a public-safe LAC regional input availability report."""
    regional = query(conn,
        """
        SELECT *
        FROM v_public_bio_regional_input_summary
        ORDER BY region_scope, input_name
        """
    )
    region_counts: dict[str, int] = {}
    for row in regional:
        rs = row.get("region_scope")
        if rs:
            region_counts[rs] = region_counts.get(rs, 0) + 1
    return {
        "report_type": "bio_regional_input",
        "location_id": location_id,
        "regional_inputs": _serialize_rows(regional),
        "region_breakdown": region_counts,
        "limitations": [
            "LAC regional input availability reflects documented sourcing notes, not exhaustive surveys.",
            "Cautions (e.g. sargassum arsenic, pesticide residues) must be followed before use.",
            "Sourcing notes are advisory; suppliers should be verified per-batch.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


