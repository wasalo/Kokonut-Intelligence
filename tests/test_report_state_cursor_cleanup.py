"""Failure-path cursor cleanup for state and portfolio report queries."""

from __future__ import annotations

import pytest

from services.export.reports import core, operations, state, wellbeing
from services.export.reports.commons import bio_factory as commons_bio_factory
from services.export.reports.commons import ecological as commons_ecological
from services.export.reports.commons import kokonut as commons_kokonut
from services.export.reports.commons import liberation as commons_liberation
from services.export.reports.commons import scaling as commons_scaling
from services.export.reports.commons import stewardship as commons_stewardship
from services.export.reports.commons import wellbeing as commons_wellbeing


class _FailingCursor:
    def __init__(self, fail_on, fetchone_results=None, fetchall_results=None):
        self.fail_on = fail_on
        self.calls = {"execute": 0, "fetchall": 0, "fetchone": 0}
        self.closed = False
        self.fetchone_results = iter(fetchone_results or [{"name": "Synthetic farm", "scorecard_id": "synthetic"}])
        self.fetchall_results = iter(fetchall_results or [])

    def _maybe_fail(self, operation):
        self.calls[operation] += 1
        if self.fail_on == (operation, self.calls[operation]):
            raise RuntimeError("synthetic report query failure")

    def execute(self, *_args):
        self._maybe_fail("execute")

    def fetchall(self):
        self._maybe_fail("fetchall")
        return next(self.fetchall_results, [])

    def fetchone(self):
        self._maybe_fail("fetchone")
        return next(self.fetchone_results, {})

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def cursor(self, **_kwargs):
        return self.cursor_instance


_CASES = [
    *((commons_ecological.generate_ecological_modeling, ("location-1",), ("execute", index)) for index in range(1, 7)),
    (commons_ecological.generate_ecological_modeling, ("location-1",), ("fetchone", 1)),
    *((commons_ecological.generate_ecological_modeling, ("location-1",), ("fetchall", index)) for index in range(1, 6)),
    *((commons_ecological.generate_trophic_pyramid, ("location-1",), ("execute", index)) for index in range(1, 5)),
    (commons_ecological.generate_trophic_pyramid, ("location-1",), ("fetchone", 1)),
    *((commons_ecological.generate_trophic_pyramid, ("location-1",), ("fetchall", index)) for index in range(1, 4)),
    (commons_kokonut._fetch_public_view, ("synthetic_view", "location-1"), ("execute", 1)),
    (commons_kokonut._fetch_public_view, ("synthetic_view", "location-1"), ("fetchall", 1)),
    (commons_kokonut._fetch_public_view, ("synthetic_view", "location-1"), ("execute", 1)),
    (commons_kokonut._fetch_public_view, ("synthetic_view", "location-1"), ("fetchall", 1)),
    *((commons_bio_factory.generate_bio_factory_batch, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_bio_factory.generate_bio_factory_batch, ("location-1",), ("fetchone", 1)),
    (commons_bio_factory.generate_bio_factory_batch, ("location-1",), ("fetchall", 1)),
    *((commons_bio_factory.generate_bio_input_provenance, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_bio_factory.generate_bio_input_provenance, ("location-1",), ("fetchone", 1)),
    (commons_bio_factory.generate_bio_input_provenance, ("location-1",), ("fetchall", 1)),
    (commons_bio_factory.generate_bio_recipe_library, ("location-1",), ("execute", 1)),
    (commons_bio_factory.generate_bio_recipe_library, ("location-1",), ("fetchall", 1)),
    *((commons_bio_factory.generate_bio_quality_test, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_bio_factory.generate_bio_quality_test, ("location-1",), ("fetchone", 1)),
    (commons_bio_factory.generate_bio_quality_test, ("location-1",), ("fetchall", 1)),
    *((commons_liberation.generate_time_liberation, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_liberation.generate_time_liberation, ("location-1",), ("fetchone", 1)),
    (commons_liberation.generate_time_liberation, ("location-1",), ("fetchall", 1)),
    *((commons_liberation.generate_capital_alignment, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_liberation.generate_capital_alignment, ("location-1",), ("fetchone", 1)),
    (commons_liberation.generate_capital_alignment, ("location-1",), ("fetchall", 1)),
    (commons_liberation.generate_governance_inclusion, ("location-1",), ("execute", 1)),
    (commons_liberation.generate_governance_inclusion, ("location-1",), ("fetchall", 1)),
    *((commons_liberation.generate_land_stewardship, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_liberation.generate_land_stewardship, ("location-1",), ("fetchone", 1)),
    (commons_liberation.generate_land_stewardship, ("location-1",), ("fetchall", 1)),
    (commons_scaling.generate_scaling_economics, ("location-1",), ("execute", 1)),
    (commons_scaling.generate_scaling_economics, ("location-1",), ("fetchall", 1)),
    *((commons_scaling.generate_scaling_economics, ("all",), ("execute", index)) for index in range(1, 3)),
    *((commons_scaling.generate_scaling_economics, ("all",), ("fetchall", index)) for index in range(1, 3)),
    (commons_scaling.generate_adoption_barriers, ("location-1",), ("execute", 1)),
    (commons_scaling.generate_adoption_barriers, ("location-1",), ("fetchall", 1)),
    (commons_scaling.generate_perpetual_value_stress, ("location-1",), ("execute", 1)),
    (commons_scaling.generate_perpetual_value_stress, ("location-1",), ("fetchall", 1)),
    *((commons_wellbeing.generate_gnh_alignment, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_wellbeing.generate_gnh_alignment, ("location-1",), ("fetchone", 1)),
    (commons_wellbeing.generate_gnh_alignment, ("location-1",), ("fetchall", 1)),
    *((commons_wellbeing.generate_cultural_preservation, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_wellbeing.generate_cultural_preservation, ("location-1",), ("fetchone", 1)),
    (commons_wellbeing.generate_cultural_preservation, ("location-1",), ("fetchall", 1)),
    *((commons_wellbeing.generate_renewable_energy, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_wellbeing.generate_renewable_energy, ("location-1",), ("fetchone", 1)),
    (commons_wellbeing.generate_renewable_energy, ("location-1",), ("fetchall", 1)),
    *((commons_wellbeing.generate_vulnerable_access, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_wellbeing.generate_vulnerable_access, ("location-1",), ("fetchone", 1)),
    (commons_wellbeing.generate_vulnerable_access, ("location-1",), ("fetchall", 1)),
    *((commons_wellbeing.generate_foundational_wellbeing, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_wellbeing.generate_foundational_wellbeing, ("location-1",), ("fetchone", 1)),
    (commons_wellbeing.generate_foundational_wellbeing, ("location-1",), ("fetchall", 1)),
    *((commons_stewardship.generate_regenerative_outcomes, ("11111111-1111-4111-8111-111111111111",), ("execute", index)) for index in range(1, 3)),
    (commons_stewardship.generate_regenerative_outcomes, ("11111111-1111-4111-8111-111111111111",), ("fetchone", 1)),
    (commons_stewardship.generate_regenerative_outcomes, ("11111111-1111-4111-8111-111111111111",), ("fetchall", 1)),
    (commons_stewardship.generate_community_governance, ("location-1",), ("execute", 1)),
    (commons_stewardship.generate_community_governance, ("location-1",), ("fetchall", 1)),
    (commons_stewardship.generate_replication_readiness, ("location-1",), ("execute", 1)),
    (commons_stewardship.generate_replication_readiness, ("location-1",), ("fetchall", 1)),
    *((commons_stewardship.generate_adaptive_stewardship, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (commons_stewardship.generate_adaptive_stewardship, ("location-1",), ("fetchone", 1)),
    (commons_stewardship.generate_adaptive_stewardship, ("location-1",), ("fetchall", 1)),
    *((wellbeing.generate_risk_mitigation, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (wellbeing.generate_risk_mitigation, ("location-1",), ("fetchone", 1)),
    (wellbeing.generate_risk_mitigation, ("location-1",), ("fetchall", 1)),
    (wellbeing.generate_scaling_roadmap, ("location-1",), ("execute", 1)),
    (wellbeing.generate_scaling_roadmap, ("location-1",), ("fetchall", 1)),
    (wellbeing.generate_green_paper_publication_status, (), ("execute", 1)),
    (wellbeing.generate_green_paper_publication_status, (), ("fetchall", 1)),
    *((wellbeing.generate_capital_efficiency, ("location-1",), ("execute", index)) for index in range(1, 4)),
    (wellbeing.generate_capital_efficiency, ("location-1",), ("fetchone", 1)),
    *((wellbeing.generate_capital_efficiency, ("location-1",), ("fetchall", index)) for index in range(1, 3)),
    (wellbeing.generate_governance_throughput, ("location-1",), ("execute", 1)),
    (wellbeing.generate_governance_throughput, ("location-1",), ("fetchall", 1)),
    (wellbeing.generate_dao_proposal_history, (), ("execute", 1)),
    (wellbeing.generate_dao_proposal_history, (), ("fetchall", 1)),
    *((wellbeing.generate_ebf_scorecard, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (wellbeing.generate_ebf_scorecard, ("location-1",), ("fetchone", 1)),
    (wellbeing.generate_ebf_scorecard, ("location-1",), ("fetchall", 1)),
    *((wellbeing.generate_holistic_wellbeing, ("11111111-1111-4111-8111-111111111111",), ("execute", index)) for index in range(1, 5)),
    (wellbeing.generate_holistic_wellbeing, ("11111111-1111-4111-8111-111111111111",), ("fetchone", 1)),
    *((wellbeing.generate_holistic_wellbeing, ("11111111-1111-4111-8111-111111111111",), ("fetchall", index)) for index in range(1, 4)),
    *((wellbeing.generate_financial_sustainability, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (wellbeing.generate_financial_sustainability, ("location-1",), ("fetchone", 1)),
    (wellbeing.generate_financial_sustainability, ("location-1",), ("fetchall", 1)),
    (core.generate_crop_noi, ("11111111-1111-4111-8111-111111111111",), ("execute", 1)),
    (core.generate_crop_noi, ("11111111-1111-4111-8111-111111111111",), ("fetchall", 1)),
    *((core.generate_environmental, ("location-1",), ("execute", index)) for index in range(1, 5)),
    *((core.generate_environmental, ("location-1",), ("fetchall", index)) for index in range(1, 5)),
    *((core.generate_forecast_summary, ("11111111-1111-4111-8111-111111111111",), ("execute", index)) for index in range(1, 4)),
    (core.generate_forecast_summary, ("11111111-1111-4111-8111-111111111111",), ("fetchall", 1)),
    (core.generate_forecast_summary, ("11111111-1111-4111-8111-111111111111",), ("fetchone", 1)),
    *((core.generate_climate_impact, ("11111111-1111-4111-8111-111111111111",), ("execute", index)) for index in range(1, 5)),
    *((core.generate_climate_impact, ("11111111-1111-4111-8111-111111111111",), ("fetchone", index)) for index in range(1, 3)),
    *((core.generate_climate_impact, ("11111111-1111-4111-8111-111111111111",), ("fetchall", index)) for index in range(1, 3)),
    *((core.generate_farm_summary, ("11111111-1111-4111-8111-111111111111",), ("execute", index)) for index in range(1, 10)),
    *((core.generate_farm_summary, ("11111111-1111-4111-8111-111111111111",), ("fetchall", index)) for index in range(1, 6)),
    *((core.generate_farm_summary, ("11111111-1111-4111-8111-111111111111",), ("fetchone", index)) for index in range(1, 5)),
    (state._state_of_kokonut_locations, (None, None, None), ("execute", 1)),
    (state._state_of_kokonut_locations, (None, None, None), ("fetchall", 1)),
    *((state._state_of_kokonut_actors, (None, None), ("execute", index)) for index in range(1, 5)),
    *((state._state_of_kokonut_actors, (None, None), ("fetchall", index)) for index in range(1, 5)),
    (state.generate_strategic_reserve, ("location-1",), ("execute", 1)),
    (state.generate_strategic_reserve, ("location-1",), ("fetchall", 1)),
    (state.generate_capital_provider_utility, ("location-1",), ("execute", 1)),
    (state.generate_capital_provider_utility, ("location-1",), ("fetchone", 1)),
    (state.generate_capital_provider_utility, ("location-1",), ("execute", 2)),
    (state.generate_capital_provider_utility, ("location-1",), ("fetchall", 1)),
    *((operations.generate_resource_efficiency, ("11111111-1111-4111-8111-111111111111",), ("execute", index)) for index in range(1, 4)),
    (operations.generate_resource_efficiency, ("11111111-1111-4111-8111-111111111111",), ("fetchone", 1)),
    (operations.generate_resource_efficiency, ("11111111-1111-4111-8111-111111111111",), ("fetchone", 2)),
    (operations.generate_resource_efficiency, ("11111111-1111-4111-8111-111111111111",), ("fetchall", 1)),
    *((operations.generate_training_impact, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (operations.generate_training_impact, ("location-1",), ("fetchone", 1)),
    (operations.generate_training_impact, ("location-1",), ("fetchall", 1)),
    *((operations.generate_revenue_streams, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (operations.generate_revenue_streams, ("location-1",), ("fetchone", 1)),
    (operations.generate_revenue_streams, ("location-1",), ("fetchall", 1)),
    *((operations.generate_model_validation, ("location-1",), ("execute", index)) for index in range(1, 4)),
    (operations.generate_model_validation, ("location-1",), ("fetchone", 1)),
    *((operations.generate_model_validation, ("location-1",), ("fetchall", index)) for index in range(1, 3)),
    *((operations.generate_livestock_feed, ("location-1",), ("execute", index)) for index in range(1, 4)),
    (operations.generate_livestock_feed, ("location-1",), ("fetchone", 1)),
    *((operations.generate_livestock_feed, ("location-1",), ("fetchall", index)) for index in range(1, 3)),
    *((operations.generate_token_rewards, ("location-1",), ("execute", index)) for index in range(1, 4)),
    *((operations.generate_token_rewards, ("location-1",), ("fetchone", index)) for index in range(1, 3)),
    (operations.generate_token_rewards, ("location-1",), ("fetchall", 1)),
    *((operations.generate_reward_calibration, ("location-1",), ("execute", index)) for index in range(1, 4)),
    (operations.generate_reward_calibration, ("location-1",), ("fetchone", 1)),
    *((operations.generate_reward_calibration, ("location-1",), ("fetchall", index)) for index in range(1, 3)),
    *((operations.generate_organic_certification_readiness, ("location-1",), ("execute", index)) for index in range(1, 6)),
    *((operations.generate_organic_certification_readiness, ("location-1",), ("fetchone", index)) for index in range(1, 4)),
    *((operations.generate_organic_certification_readiness, ("location-1",), ("fetchall", index)) for index in range(1, 3)),
    *((operations.generate_organic_transition_progress, ("location-1",), ("execute", index)) for index in range(1, 4)),
    (operations.generate_organic_transition_progress, ("location-1",), ("fetchone", 1)),
    *((operations.generate_organic_transition_progress, ("location-1",), ("fetchall", index)) for index in range(1, 3)),
    *((operations.generate_organic_input_audit, ("location-1",), ("execute", index)) for index in range(1, 4)),
    (operations.generate_organic_input_audit, ("location-1",), ("fetchone", 1)),
    *((operations.generate_organic_input_audit, ("location-1",), ("fetchall", index)) for index in range(1, 3)),
    *((operations.generate_statement_of_work, ("location-1",), ("execute", index)) for index in range(1, 11)),
    *((operations.generate_statement_of_work, ("location-1",), ("fetchone", index)) for index in range(1, 4)),
    *((operations.generate_statement_of_work, ("location-1",), ("fetchall", index)) for index in range(1, 8)),
]


@pytest.mark.parametrize(("generator", "args", "fail_on"), _CASES)
def test_report_cursor_closes_when_query_or_fetch_fails(generator, args, fail_on):
    cursor = _FailingCursor(fail_on)
    conn = _Connection(cursor)

    with pytest.raises(RuntimeError, match="synthetic report query failure"):
        generator(conn, *args)

    assert cursor.closed


def test_farm_summary_closes_cursor_when_location_is_missing():
    cursor = _FailingCursor(None, fetchone_results=[None])
    conn = _Connection(cursor)

    with pytest.raises(ValueError, match="Location 11111111-1111-4111-8111-111111111111 not found"):
        core.generate_farm_summary(conn, "11111111-1111-4111-8111-111111111111")

    assert cursor.closed


@pytest.mark.parametrize("fail_on", [("execute", 2), ("fetchall", 2)])
def test_dao_history_closes_cursor_when_voter_query_fails(fail_on):
    cursor = _FailingCursor(fail_on, fetchall_results=[[{"proposal_id": "1"}]])
    conn = _Connection(cursor)

    with pytest.raises(RuntimeError, match="synthetic report query failure"):
        wellbeing.generate_dao_proposal_history(conn)

    assert cursor.closed


@pytest.mark.parametrize(
    "fail_on",
    [*(('execute', index) for index in range(11, 14)), *(('fetchall', index) for index in range(8, 11))],
)
def test_statement_of_work_closes_cursor_when_optional_sow_query_fails(fail_on):
    cursor = _FailingCursor(fail_on, fetchone_results=[{"name": "Synthetic farm"}, {"id": "sow-1"}])
    conn = _Connection(cursor)

    with pytest.raises(RuntimeError, match="synthetic report query failure"):
        operations.generate_statement_of_work(conn, "location-1")

    assert cursor.closed
