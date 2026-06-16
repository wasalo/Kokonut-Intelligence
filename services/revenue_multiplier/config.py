"""
Revenue Multiplier Configuration

Loads configurable constants from the database, falling back to defaults.
"""

from typing import Dict, Any, Optional

_DEFAULTS = {
    "processing_uplift": {
        "Maize": {"flour": 1.8, "porridge_mix": 2.2, "animal_feed": 1.3},
        "Cassava": {"flour": 2.0, "chips": 1.5, "starch": 2.5},
        "Beans": {"packaged": 1.4, "flour": 1.6, "sprouted": 2.0},
        "Sweet Potato": {"dried_chips": 1.6, "flour": 1.8, "puree": 2.0},
    },
    "replication_cost_usd": 15000,
    "loop_multiplier": 2.5,
    "carbon_credit_price_usd": 25.0,
    "biodiversity_credit_price_usd": 35.0,
    "impact_certificate_price_usd": 10.0,
    "shared_savings_per_ha_usd": 50,
    "new_partners_potential": 3,
    "loss_reduction_target_pct": 50,
    "buyer_uplift_pct": 30,
    "bioinput_savings_pct": 70,
    "bioinput_switching_benefit_pct": 50,
    "default_processing_uplift": 1.3,
    # Scoring formulas — crop_mix
    "crop_mix_gap_normalizer": 10,
    "crop_mix_confidence_threshold": 4,
    # Scoring formulas — loss_reduction
    "loss_rate_score_multiplier": 5,
    "loss_rate_confidence_threshold": 3,
    # Scoring formulas — buyer_channel
    "buyer_payment_weight": 0.4,
    "buyer_returns_weight": 0.3,
    "buyer_netsale_weight": 0.3,
    "buyer_netsale_normalizer": 100,
    "buyer_count_multiplier": 25,
    "buyer_confidence_threshold": 2,
    # Scoring formulas — value_added
    "value_added_uplift_multiplier": 30,
    "value_added_infra_bonus": 1.3,
    "value_added_cost_assumption": 0.5,
    # Scoring formulas — web3_replication
    "web3_funding_sources_multiplier": 20,
    "web3_funding_bonus": 20,
    # Scoring formulas — bioinput
    "bioinput_share_multiplier": 1.5,
    "bioinput_biofactory_bonus": 50,
    "bioinput_default_capacity": 500,
    "bioinput_switching_fallback": 0.3,
    # Scoring formulas — public_goods
    "public_goods_allocation_multiplier": 10,
    "public_goods_target_pct": 0.05,
    # Scoring formulas — ecological_verification
    "ecological_carbon_weight": 25,
    "ecological_species_weight": 25,
    "ecological_claims_weight": 30,
    "ecological_forecast_weight": 20,
    # Scoring formulas — partner_sponsorship
    "partner_count_multiplier": 15,
    "partner_revenue_bonus": 20,
    # Scoring formulas — regional_clusters
    "regional_nearby_multiplier": 20,
    "regional_farm_multiplier": 10,
    "regional_ha_per_nearby": 10,
    # Analyzer dimension weights
    "weight_crop_mix": 1.5,
    "weight_loss_reduction": 1.2,
    "weight_buyer_channel": 1.0,
    "weight_value_added": 1.0,
    "weight_web3_replication": 0.8,
    "weight_bioinput": 0.8,
    "weight_public_goods": 0.7,
    "weight_ecological_verification": 1.0,
    "weight_partner_sponsorship": 0.8,
    "weight_regional_clusters": 0.6,
}

_cache: Optional[Dict[str, Any]] = None


def get_config(conn=None, key: str = None) -> Any:
    """Get configuration value(s). Uses cache after first load."""
    global _cache
    if _cache is None:
        _load_config(conn)
    if key:
        return _cache.get(key, _DEFAULTS.get(key))
    return dict(_cache) if _cache else dict(_DEFAULTS)


def _load_config(conn=None) -> None:
    """Load config from database into cache."""
    global _cache
    _cache = dict(_DEFAULTS)
    if conn is None:
        try:
            from ..ingestion.base import get_db
            conn = get_db()
        except Exception:
            return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT config_key, config_value FROM revenue_multiplier_config")
            for row in cur.fetchall():
                _cache[row[0]] = row[1]
        conn.close()
    except Exception:
        pass


def invalidate_cache():
    """Force reload on next access."""
    global _cache
    _cache = None
