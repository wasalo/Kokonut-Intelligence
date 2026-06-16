"""
Revenue Multiplier Analyzer

Orchestrates all 10 dimension analyzers to produce a comprehensive
opportunity map for a given location.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from ..ingestion.base import get_db
from ..revenue_multiplier.config import get_config
from .models import OpportunityDimension, RevenueMultiplierMap


def analyze_location(location_id: str) -> RevenueMultiplierMap:
    """Run all 10 dimension analyzers for a location."""
    from .dimensions import crop_mix, loss_reduction, buyer_channel, value_added
    from .dimensions import web3_replication, bioinput, public_goods
    from .dimensions import ecological_verification, partner_sponsorship, regional_clusters

    conn = get_db()
    location_name = _get_location_name(conn, location_id)

    analyzers = [
        ("crop_mix_optimization", "Crop Mix Optimization", crop_mix.analyze),
        ("loss_rate_reduction", "Loss-Rate Reduction", loss_reduction.analyze),
        ("buyer_channel_selection", "Buyer/Channel Selection", buyer_channel.analyze),
        ("value_added_processing", "Value-Added Processing", value_added.analyze),
        ("web3_funded_replication", "Web3-Funded Replication", web3_replication.analyze),
        ("bioinput_production", "Bioinput Production", bioinput.analyze),
        ("public_goods_funding", "Public-Goods Funding Loops", public_goods.analyze),
        ("ecological_verification", "Ecological Verification Monetization", ecological_verification.analyze),
        ("partner_sponsorship", "Partner Sponsorship", partner_sponsorship.analyze),
        ("regional_farm_clusters", "Regional Farm Clusters", regional_clusters.analyze),
    ]

    dimensions = []
    for dim_id, dim_name, analyzer in analyzers:
        try:
            dim = analyzer(conn, location_id)
            dimensions.append(dim)
        except Exception as e:
            dimensions.append(OpportunityDimension(
                dimension_id=dim_id,
                dimension_name=dim_name,
                score=0,
                impact_usd=0,
                confidence="low",
                current_state=f"Error: {e}",
                recommendation="Fix analyzer error",
                data_points=0,
            ))

    # Read config-driven weights before closing connection
    weight_keys = {
        "crop_mix_optimization": "weight_crop_mix",
        "loss_rate_reduction": "weight_loss_reduction",
        "buyer_channel_selection": "weight_buyer_channel",
        "value_added_processing": "weight_value_added",
        "web3_funded_replication": "weight_web3_replication",
        "bioinput_production": "weight_bioinput",
        "public_goods_funding": "weight_public_goods",
        "ecological_verification": "weight_ecological_verification",
        "partner_sponsorship": "weight_partner_sponsorship",
        "regional_farm_clusters": "weight_regional_clusters",
    }
    weights = {}
    for dim in dimensions:
        key = weight_keys.get(dim.dimension_id)
        if key:
            weights[dim.dimension_id] = float(get_config(conn, key))
        else:
            weights[dim.dimension_id] = 1.0

    conn.close()

    # Calculate overall metrics
    total_impact = sum(d.impact_usd for d in dimensions)
    total_weight = sum(weights.values())
    overall_score = sum(d.score * weights.get(d.dimension_id, 1.0) for d in dimensions) / total_weight

    return RevenueMultiplierMap(
        location_id=location_id,
        location_name=location_name,
        dimensions=dimensions,
        total_opportunity_usd=round(total_impact, 2),
        overall_score=round(overall_score, 1),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _get_location_name(conn, location_id: str) -> str:
    cur = conn.cursor()
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    row = cur.fetchone()
    cur.close()
    return row[0] if row else "Unknown"
