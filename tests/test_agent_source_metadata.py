"""Keep synthesis draft source labels aligned with inputs the agents query."""

import inspect

from services.agents.bio_factory_agent import BioFactorySynthesisAgent
from services.agents.feedback_agent import FeedbackSynthesisAgent
from services.agents.wellbeing_agent import (
    WellbeingSynthesisAgent,
    synthesize_wellbeing,
)


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


def test_wellbeing_agent_declares_its_direct_feedback_aggregation_source():
    source = inspect.getsource(synthesize_wellbeing).lower()

    assert "from stakeholder_feedback" in source
    assert "stakeholder_feedback" in WellbeingSynthesisAgent.source_tables
