"""
Metric Calculators

Each calculator takes (conn, location_id, period_start, period_end) and returns
{value, computation_method, source_record_ids, metadata}.
"""

from .value_flowed import compute_value_flowed
from .wallet_retention import compute_wallet_retention
from .digital_lego import compute_digital_lego_usage
from .attestation_coverage import compute_attestation_coverage
from .soil_carbon_delta import compute_soil_carbon_delta
from .biodiversity_delta import compute_biodiversity_delta
from .operating_margin import compute_operating_margin

CALCULATORS = {
    "value_flowed": compute_value_flowed,
    "wallet_retention": compute_wallet_retention,
    "digital_lego_usage": compute_digital_lego_usage,
    "attestation_coverage": compute_attestation_coverage,
    "soil_carbon_delta": compute_soil_carbon_delta,
    "biodiversity_delta": compute_biodiversity_delta,
    "operating_margin_pct": compute_operating_margin,
}
