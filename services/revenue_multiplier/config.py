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
