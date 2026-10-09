"""Commons report generators, split by theme."""

from .bio_factory import (
    generate_bio_factory_batch,
    generate_bio_input_provenance,
    generate_bio_quality_test,
    generate_bio_recipe_library,
    generate_bio_regional_input,
)
from .ecological import (
    generate_ecological_modeling,
    generate_trophic_pyramid,
)
from .kokonut import (
    generate_algorithmic_redistribution,
    generate_anti_capture_governance,
    generate_federation_mutual_aid,
    generate_participatory_signal,
    generate_redistribution_policy,
)
from .liberation import (
    generate_capital_alignment,
    generate_governance_inclusion,
    generate_land_stewardship,
    generate_time_liberation,
)
from .scaling import (
    generate_adoption_barriers,
    generate_open_source_impact,
    generate_perpetual_value_stress,
    generate_scaling_economics,
)
from .stewardship import (
    generate_adaptive_stewardship,
    generate_community_governance,
    generate_regenerative_outcomes,
    generate_replication_readiness,
)
from .wellbeing import (
    generate_cultural_preservation,
    generate_foundational_wellbeing,
    generate_gnh_alignment,
    generate_renewable_energy,
    generate_vulnerable_access,
)

__all__ = [
    generate_bio_factory_batch,
    generate_bio_input_provenance,
    generate_bio_recipe_library,
    generate_bio_quality_test,
    generate_bio_regional_input,
    generate_time_liberation,
    generate_capital_alignment,
    generate_governance_inclusion,
    generate_land_stewardship,
    generate_gnh_alignment,
    generate_cultural_preservation,
    generate_renewable_energy,
    generate_vulnerable_access,
    generate_foundational_wellbeing,
    generate_regenerative_outcomes,
    generate_community_governance,
    generate_replication_readiness,
    generate_adaptive_stewardship,
    generate_scaling_economics,
    generate_adoption_barriers,
    generate_perpetual_value_stress,
    generate_open_source_impact,
    generate_anti_capture_governance,
    generate_redistribution_policy,
    generate_federation_mutual_aid,
    generate_algorithmic_redistribution,
    generate_participatory_signal,
    generate_ecological_modeling,
    generate_trophic_pyramid,
]
