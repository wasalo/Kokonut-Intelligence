"""Direct-call scope validation for operational reports."""

import pytest

from services.export.reports import operations


class NoDatabase:
    def cursor(self, **_kwargs):
        raise AssertionError("database access must not occur for invalid location scope")


@pytest.mark.parametrize(
    ("generator", "report_type"),
    [
        (operations.generate_pest_management, "pest_management"),
        (operations.generate_training_impact, "training_impact"),
        (operations.generate_revenue_streams, "revenue_streams"),
        (operations.generate_model_validation, "model_validation"),
        (operations.generate_livestock_feed, "livestock_feed"),
        (operations.generate_token_rewards, "token_rewards"),
        (operations.generate_reward_calibration, "reward_calibration"),
        (operations.generate_organic_certification_readiness, "organic_certification_readiness"),
        (operations.generate_organic_transition_progress, "organic_transition_progress"),
        (operations.generate_organic_input_audit, "organic_input_audit"),
        (operations.generate_statement_of_work, "statement_of_work"),
    ],
)
@pytest.mark.parametrize(
    "location_id",
    [
        None,
        "",
        "all",
        "not-a-uuid",
        "11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222",
    ],
)
def test_operational_report_rejects_invalid_location_before_database_access(
    generator, report_type, location_id
):
    with pytest.raises(ValueError, match=f"{report_type} requires an explicit location_id"):
        generator(NoDatabase(), location_id)
