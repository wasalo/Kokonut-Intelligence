"""Report generators: ecological."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from ..common import _serialize_rows


def generate_ecological_modeling(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe ecological modeling report with interactions, model runs, and population dynamics."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_public_ecological_interaction_summary
        WHERE location_id = %s ORDER BY interaction_strength DESC
        """,
        (location_id,),
    )
    interactions = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_ecological_model_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR run_date >= %s::date)
          AND (%s::date IS NULL OR run_date <= %s::date)
        ORDER BY run_date DESC
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    models = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_population_dynamics_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR record_date >= %s::date)
          AND (%s::date IS NULL OR record_date <= %s::date)
        ORDER BY species_name, record_date
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    populations = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_energy_flow_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR measurement_date >= %s::date)
          AND (%s::date IS NULL OR measurement_date <= %s::date)
        ORDER BY measurement_date DESC
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    energy_flows = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM v_public_soil_input_retention
        WHERE location_id = %s
          AND (%s::date IS NULL OR application_date >= %s::date)
          AND (%s::date IS NULL OR application_date <= %s::date)
        ORDER BY application_date DESC
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    soil_inputs = [dict(r) for r in cur.fetchall()]
    cur.close()
    mutualism_count = sum(1 for i in interactions if i.get("interaction_type") == "mutualism")
    predation_count = sum(1 for i in interactions if i.get("interaction_type") == "predation")
    trophic_balance = mutualism_count / max(mutualism_count + predation_count, 1)
    avg_residual = sum(s.get("residual_pct", 0) or 0 for s in soil_inputs) / max(len(soil_inputs), 1)
    return {
        "report_type": "ecological_modeling",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "interactions": _serialize_rows(interactions),
        "model_runs": _serialize_rows(models),
        "population_records": _serialize_rows(populations),
        "energy_flows": _serialize_rows(energy_flows),
        "soil_inputs": _serialize_rows(soil_inputs),
        "interaction_count": len(interactions),
        "mutualism_count": mutualism_count,
        "predation_count": predation_count,
        "trophic_balance_index": round(trophic_balance, 3),
        "soil_input_count": len(soil_inputs),
        "avg_residual_pct": round(avg_residual, 2),
        "limitations": [
            "Ecological model outputs are simulation estimates, not guaranteed outcomes.",
            "Interaction strength values are observational estimates requiring ground-truth verification.",
            "Population dynamics records depend on survey method accuracy and observer skill.",
            "Energy flow measurements use estimation methods; direct measurement preferred.",
            "Soil input retention rates vary with soil type, climate, and microbial activity.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }




def generate_trophic_pyramid(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe trophic pyramid report showing energy flow across trophic levels."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT * FROM v_energy_flow_efficiency
        WHERE location_id = %s ORDER BY from_trophic_level, to_trophic_level
        """,
        (location_id,),
    )
    energy_flows = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT species_a_trophic AS trophic_level, COUNT(*) AS interaction_count,
               AVG(interaction_strength) AS avg_strength
        FROM ecological_interaction
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY species_a_trophic
        """,
        (location_id,),
    )
    trophic_counts = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT trophic_level, COUNT(DISTINCT species_name) AS species_count
        FROM population_dynamics_record
        WHERE location_id = %s AND status IN ('verified', 'published')
          AND (%s::date IS NULL OR record_date >= %s::date)
          AND (%s::date IS NULL OR record_date <= %s::date)
        GROUP BY trophic_level
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    species_by_trophic = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "trophic_pyramid",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "energy_flows": _serialize_rows(energy_flows),
        "trophic_interaction_counts": _serialize_rows(trophic_counts),
        "species_by_trophic_level": _serialize_rows(species_by_trophic),
        "total_energy_transfers": len(energy_flows),
        "limitations": [
            "Trophic pyramid metrics are aggregated from observational data with inherent measurement uncertainty.",
            "Energy flow efficiency percentages use estimation methods; direct biomass measurement preferred.",
            "Species classifications by trophic level may vary with life stage and diet.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Pest Management Report
# ---------------------------------------------------------------------------

