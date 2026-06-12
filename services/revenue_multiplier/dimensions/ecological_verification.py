"""
Ecological Verification Monetization — Dimension 8

Estimates dollar value of soil carbon, biodiversity, and vegetation verification
as carbon credits, biodiversity credits, and impact certificates.
"""

import psycopg2.extras
from ..models import OpportunityDimension


# Market prices for ecological credits (conservative estimates)
CARBON_CREDIT_PRICE = 25.0  # USD per tonne CO2e
BIODIVERSITY_CREDIT_PRICE = 35.0  # USD per unit of biodiversity gain
IMPACT_CERTIFICATE_PRICE = 10.0  # USD per verified claim


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get soil carbon changes
    cur.execute("""
        SELECT
            plot_id,
            MAX(CASE WHEN is_baseline THEN carbon_tonnes_per_ha END) as baseline,
            MAX(CASE WHEN NOT is_baseline THEN carbon_tonnes_per_ha END) as current
        FROM soil_carbon_measurement
        WHERE location_id = %s
        GROUP BY plot_id
    """, (location_id,))
    carbon_data = [dict(r) for r in cur.fetchall()]

    # Get species observations
    cur.execute("""
        SELECT
            plot_id,
            observation_date,
            COUNT(DISTINCT species_name) as species_count
        FROM species_observation
        WHERE location_id = %s
        GROUP BY plot_id, observation_date
        ORDER BY observation_date
    """, (location_id,))
    species_data = [dict(r) for r in cur.fetchall()]

    # Get MRV claims
    cur.execute("""
        SELECT claim_type, status, COUNT(*) as count
        FROM mrv_claim
        WHERE location_id = %s
        GROUP BY claim_type, status
    """, (location_id,))
    claims = [dict(r) for r in cur.fetchall()]

    # Get attestation records
    cur.execute("""
        SELECT status, COUNT(*) as count
        FROM attestation_record
        WHERE subject_type = 'location' AND subject_id = %s
        GROUP BY status
    """, (location_id,))
    attestations = {r["status"]: r["count"] for r in cur.fetchall()}

    cur.close()

    # Calculate carbon credit potential
    total_carbon_delta = 0
    for cd in carbon_data:
        baseline = float(cd["baseline"] or 0)
        current = float(cd["current"] or 0)
        total_carbon_delta += max(0, current - baseline)

    carbon_revenue = total_carbon_delta * CARBON_CREDIT_PRICE

    # Calculate biodiversity credit potential
    species_by_date = {}
    for sd in species_data:
        date = sd["observation_date"]
        if date not in species_by_date:
            species_by_date[date] = 0
        species_by_date[date] += sd["species_count"]

    dates = sorted(species_by_date.keys())
    if len(dates) >= 2:
        baseline_species = species_by_date[dates[0]]
        current_species = species_by_date[dates[-1]]
        species_delta = max(0, current_species - baseline_species)
    else:
        species_delta = 0

    biodiversity_revenue = species_delta * BIODIVERSITY_CREDIT_PRICE

    # Calculate attestation value
    total_claims = sum(c["count"] for c in claims)
    attested_claims = attestations.get("attested", 0)
    attestation_revenue = attested_claims * IMPACT_CERTIFICATE_PRICE

    total_revenue = carbon_revenue + biodiversity_revenue + attestation_revenue

    # Score based on data completeness and verification status
    has_carbon = len(carbon_data) > 0
    has_species = len(species_data) > 0
    has_claims = total_claims > 0
    score = (30 if has_carbon else 0) + (30 if has_species else 0) + (40 if has_claims else 0)

    details = {
        "carbon_delta_tonnes": round(total_carbon_delta, 2),
        "carbon_credit_revenue": round(carbon_revenue, 2),
        "species_delta": species_delta,
        "biodiversity_credit_revenue": round(biodiversity_revenue, 2),
        "attested_claims": attested_claims,
        "attestation_revenue": round(attestation_revenue, 2),
        "total_verification_revenue": round(total_revenue, 2),
        "claim_breakdown": {c["claim_type"]: c["count"] for c in claims},
    }

    return OpportunityDimension(
        dimension_id="ecological_verification",
        dimension_name="Ecological Verification Monetization",
        score=round(score, 1),
        impact_usd=round(total_revenue, 2),
        confidence="high" if has_carbon and has_species else "medium",
        current_state=f"Carbon: +{total_carbon_delta:.1f} t/ha, Species: +{species_delta}, Claims: {total_claims}",
        recommendation=f"Monetize {total_carbon_delta:.1f}t carbon + {species_delta} species gains = ${total_revenue:,.0f}",
        data_points=len(carbon_data) + len(species_data) + total_claims,
        details=details,
    )
