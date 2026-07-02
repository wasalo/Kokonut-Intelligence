"""Bio-organic fertilizer operations synthesis agent for Latin America and the Caribbean."""

from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

import psycopg2
import psycopg2.extras

from services.agents.safety import assert_agent_action_allowed
from services.agents.tasks import validate_output
from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def _location_filter(column: str, location_id: str | None) -> tuple[str, tuple[Any, ...]]:
    if location_id:
        return f"WHERE {column} = %s", (location_id,)
    return "", ()


def _synthesize_batches(cur, location_id: str | None) -> list[dict[str, Any]]:
    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT batch_name, location_id, batch_type, production_method,
               production_start_date, production_end_date,
               input_kg_total, output_kg_total, output_liters_total, batch_yield_pct,
               moisture_pct, temperature_c, ph_level, microbial_strain,
               public_summary, limitations, evidence_maturity, evidence_maturity_label
        FROM v_public_bio_factory_batch_summary
        {where}
        ORDER BY production_start_date DESC, batch_name
        """,
        params,
    )
    return [dict(r) for r in cur.fetchall()]


def _synthesize_provenance(cur, location_id: str | None) -> list[dict[str, Any]]:
    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT input_name, input_category, location_id, batch_id,
               supplier_name, supplier_verified, organic_certified,
               origin_country, origin_region, input_kg,
               nutrient_n_pct, nutrient_p_pct, nutrient_k_pct,
               quality_warnings, public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_bio_input_provenance_summary
        {where}
        ORDER BY input_category, input_name
        """,
        params,
    )
    return [dict(r) for r in cur.fetchall()]


def _synthesize_recipes(cur, location_id: str | None) -> list[dict[str, Any]]:
    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT recipe_name, location_id, recipe_type, recipe_category,
               description, fermentation_days, target_c_n_ratio, target_moisture_pct,
               target_temperature_c, target_ph, dilution_ratio, application_method,
               quality_warnings, source_reference,
               public_summary, limitations, evidence_maturity, evidence_maturity_label
        FROM v_public_bio_recipe_library_summary
        {where}
        ORDER BY recipe_type, recipe_name
        """,
        params,
    )
    return [dict(r) for r in cur.fetchall()]


def _synthesize_quality(cur, location_id: str | None) -> list[dict[str, Any]]:
    where, params = _location_filter("location_id", location_id)
    cur.execute(
        f"""
        SELECT test_date, location_id, batch_id, test_type, parameter_name,
               measured_value, unit, target_min, target_max, pass_fail,
               lab_name, lab_accredited,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_bio_factory_quality_test_summary
        {where}
        ORDER BY test_date DESC, parameter_name
        """,
        params,
    )
    return [dict(r) for r in cur.fetchall()]


def _synthesize_regional(cur) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT region_scope, input_name, input_category, country, subregion,
               seasonality, cautions, quality_considerations, typical_suppliers,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_bio_regional_input_summary
        ORDER BY region_scope, input_name
        """
    )
    return [dict(r) for r in cur.fetchall()]


def synthesize_bio_factory(conn, location_id: str | None = None) -> dict[str, Any]:
    """Summarize public-safe bio-factory batches, provenance, recipes, quality, and LAC regional inputs."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    batch_rows = _synthesize_batches(cur, location_id)
    provenance_rows = _synthesize_provenance(cur, location_id)
    recipe_rows = _synthesize_recipes(cur, location_id)
    quality_rows = _synthesize_quality(cur, location_id)
    regional_rows = _synthesize_regional(cur)
    cur.close()

    total_kg_produced = sum(
        float(row.get("output_kg_total") or 0) for row in batch_rows
    )
    total_liters_produced = sum(
        float(row.get("output_liters_total") or 0) for row in batch_rows
    )

    lac_inputs = [
        row for row in provenance_rows
        if row.get("origin_region")
        and any(
            keyword in (row.get("origin_region") or "").lower()
            for keyword in [
                "caribbean", "central america", "south america",
                "monte plata", "dominican", "mexico", "latin america",
                "sabana grande", "greater antilles",
            ]
        )
    ]
    lac_input_count = len(lac_inputs)

    ingredient_categories: set[str] = set()
    for row in provenance_rows:
        if row.get("input_category"):
            ingredient_categories.add(row["input_category"])

    recipe_types: dict[str, int] = {}
    for row in recipe_rows:
        rt = row.get("recipe_type")
        if rt:
            recipe_types[rt] = recipe_types.get(rt, 0) + 1

    quality_tests = [row for row in quality_rows if row.get("pass_fail")]
    quality_pass = sum(1 for row in quality_tests if row["pass_fail"] == "pass")
    quality_pass_rate = (
        round(quality_pass / len(quality_tests) * 100, 1) if quality_tests else None
    )

    ingredients_with_warnings = sum(
        1 for row in provenance_rows if row.get("quality_warnings")
    )
    recipes_with_warnings = sum(
        1 for row in recipe_rows if row.get("quality_warnings")
    )

    synthesis_lines = []
    if batch_rows:
        synthesis_lines.append(
            f"{len(batch_rows)} bio-organic fertilizer batch(es) produced "
            f"{total_kg_produced:,.0f} kg and {total_liters_produced:,.0f} L of solid and liquid amendments."
        )
    else:
        synthesis_lines.append("No public bio-factory batches are available.")
    if provenance_rows:
        synthesis_lines.append(
            f"{len(provenance_rows)} ingredient(s) traced with "
            f"{lac_input_count} from Latin America/Caribbean sources."
        )
    if recipe_rows:
        synthesis_lines.append(
            f"{len(recipe_rows)} reusable recipe(s) cover "
            f"{', '.join(sorted(recipe_types.keys()))} categories."
        )
    if quality_rows:
        if quality_pass_rate is not None:
            synthesis_lines.append(
                f"{len(quality_rows)} quality test(s) show a {quality_pass_rate}% pass rate."
            )
    if regional_rows:
        synthesis_lines.append(
            f"{len(regional_rows)} LAC regional input(s) documented with sourcing notes and cautions."
        )
    if ingredients_with_warnings or recipes_with_warnings:
        synthesis_lines.append(
            f"{ingredients_with_warnings} ingredient(s) and {recipes_with_warnings} recipe(s) include explicit quality warnings."
        )

    return {
        "location_id": location_id,
        "batch_count": len(batch_rows),
        "provenance_count": len(provenance_rows),
        "recipe_count": len(recipe_rows),
        "quality_test_count": len(quality_rows),
        "regional_input_count": len(regional_rows),
        "total_kg_produced": round(total_kg_produced, 2),
        "total_liters_produced": round(total_liters_produced, 2),
        "lac_input_count": lac_input_count,
        "lac_input_share_pct": round(lac_input_count / len(provenance_rows) * 100, 1) if provenance_rows else None,
        "unique_input_categories": sorted(ingredient_categories),
        "recipe_type_breakdown": recipe_types,
        "quality_pass_rate_pct": quality_pass_rate,
        "ingredients_with_warnings": ingredients_with_warnings,
        "recipes_with_warnings": recipes_with_warnings,
        "batches": batch_rows,
        "provenance": provenance_rows,
        "recipes": recipe_rows,
        "quality_tests": quality_rows,
        "regional_inputs": regional_rows,
        "synthesis": " ".join(synthesis_lines),
        "safety_note": (
            "Public-safe bio-factory evidence only; private supplier terms, draft lab results, "
            "household-level feedstock data, and proprietary microbial strain details are excluded. "
            "Recipes are public knowledge for adaptation, not commercial endorsements. "
            "Quality test results are advisory, not certification."
        ),
    }


def store_bio_factory_summary(conn, summary: dict[str, Any], model_version: str = "bio-factory-agent-v1") -> str:
    """Store a draft AI summary for human review."""
    assert_agent_action_allowed("create", "ai_summary", {"status": "draft"})
    summary_id = str(uuid.uuid4())
    subject_id = summary.get("location_id") or "00000000-0000-0000-0000-000000000000"
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ai_summary
            (id, subject_type, subject_id, summary_type, content,
             source_tables, model_version, status)
        VALUES (%s, 'location', %s, 'bio_factory', %s, %s, %s, 'draft')
        RETURNING id
        """,
        (
            summary_id,
            subject_id,
            summary["synthesis"],
            [
                "bio_factory_batch",
                "bio_input_provenance",
                "bio_recipe_library",
                "bio_factory_quality_test",
                "bio_ingredient_composition_reference",
                "bio_regional_input_availability",
            ],
            model_version,
        ),
    )
    stored_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return stored_id


def run_bio_factory_synthesis(location_id: str | None = None, store: bool = False) -> dict[str, Any]:
    assert_agent_action_allowed("read", "bio_factory_batch", {"location_id": location_id})
    conn = get_connection()
    try:
        summary = synthesize_bio_factory(conn, location_id)
        output: dict[str, Any] = {"summary": summary}
        if store:
            output["ai_summary_id"] = store_bio_factory_summary(conn, summary)
    finally:
        conn.close()

    errors = validate_output("bio_factory_synthesis", output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kokonut bio-factory synthesis agent")
    parser.add_argument("--location-id", help="Optional location UUID")
    parser.add_argument("--store", action="store_true", help="Store draft ai_summary output for human review")
    args = parser.parse_args()

    print(json.dumps(run_bio_factory_synthesis(args.location_id, store=args.store), indent=2, default=str))


if __name__ == "__main__":
    main()
