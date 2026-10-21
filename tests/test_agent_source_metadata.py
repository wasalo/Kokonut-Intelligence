"""Keep synthesis draft source labels aligned with inputs the agents query."""

from services.agents.bio_factory_agent import BioFactorySynthesisAgent
from services.agents.feedback_agent import FeedbackSynthesisAgent


def test_bio_factory_agent_does_not_claim_unused_composition_reference_input():
    assert BioFactorySynthesisAgent.source_tables == [
        "bio_factory_batch",
        "bio_input_provenance",
        "bio_recipe_library",
        "bio_factory_quality_test",
        "bio_regional_input_availability",
    ]


def test_feedback_agent_does_not_claim_unqueried_review_rows_as_source():
    assert FeedbackSynthesisAgent.source_tables == ["stakeholder_feedback"]
