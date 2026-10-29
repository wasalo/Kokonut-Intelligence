"""CLI scope contract for the complete report generator catalog."""

import re
from unittest.mock import MagicMock, Mock

import pytest

from services.analytics.process_health import generate_process_health
from services.export import report_generator
from services.export.report_generator import build_parser, validate_args
from services.export.reports.commons.bio_factory import generate_bio_regional_input
from services.export.reports.commons.kokonut import (
    generate_federation_mutual_aid,
    generate_participatory_signal,
)
from services.export.reports.commons.scaling import generate_open_source_impact
from services.export.reports.strategy import (
    generate_capability_assessment,
    generate_capability_dashboard,
    generate_coordination_cockpit,
    generate_governance_coordination_health,
    generate_stakeholder_cockpit,
    generate_stakeholder_decision_lineage,
    generate_stakeholder_ecosystem,
    generate_stakeholder_engagement,
    generate_stakeholder_grievance,
    generate_stakeholder_landscape,
    generate_stakeholder_representation,
    generate_stakeholder_trust,
    generate_stakeholder_value_streams,
    generate_strategy_execution,
    generate_technology_roadmap,
    generate_value_stream_formal,
)
from services.export.reports.wellbeing import (
    generate_dao_proposal_history,
    generate_green_paper_publication_status,
)

NETWORK_ONLY_GENERATORS = (
    ("bio_regional_input", generate_bio_regional_input),
    ("capability_assessment", generate_capability_assessment),
    ("capability_dashboard", generate_capability_dashboard),
    ("coordination_cockpit", generate_coordination_cockpit),
    ("dao_proposal_history", generate_dao_proposal_history),
    ("federation_mutual_aid", generate_federation_mutual_aid),
    ("governance_coordination_health", generate_governance_coordination_health),
    ("green_paper_publication_status", generate_green_paper_publication_status),
    ("open_source_impact", generate_open_source_impact),
    ("participatory_signal", generate_participatory_signal),
    ("process_health", generate_process_health),
    ("stakeholder_cockpit", generate_stakeholder_cockpit),
    ("stakeholder_ecosystem", generate_stakeholder_ecosystem),
    ("stakeholder_representation", generate_stakeholder_representation),
    ("stakeholder_trust", generate_stakeholder_trust),
    ("stakeholder_value_streams", generate_stakeholder_value_streams),
    ("strategy_execution", generate_strategy_execution),
    ("technology_roadmap", generate_technology_roadmap),
    ("value_stream_formal", generate_value_stream_formal),
)

LOCATION_A = "11111111-1111-4111-8111-111111111111"
LOCATION_B = "22222222-2222-4222-8222-222222222222"


def validate(*argv: str) -> None:
    parser = build_parser()
    validate_args(parser, parser.parse_args(list(argv)))


@pytest.mark.parametrize(
    "arguments",
    [
        ("--auto",),
        ("--type", "farm_summary"),
        ("--type", "farm_summary", "--all", "--location-id", "location-a"),
        ("--type", "farm_summary", "--verify", "snapshot-hash"),
        ("--list", "--verify", "snapshot-hash"),
    ],
)
def test_ambiguous_or_unscoped_report_commands_fail_before_database_access(arguments) -> None:
    with pytest.raises(SystemExit) as exc_info:
        validate(*arguments)

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "report_type",
    [
        "stakeholder_landscape",
        "stakeholder_engagement",
        "stakeholder_grievance",
        "stakeholder_decision_lineage",
    ],
)
def test_location_lineaged_stakeholder_reports_require_one_explicit_location(report_type) -> None:
    with pytest.raises(SystemExit) as exc_info:
        validate("--type", report_type)
    assert exc_info.value.code == 2

    validate("--type", report_type, "--location-id", LOCATION_A)

    with pytest.raises(SystemExit) as exc_info:
        validate("--type", report_type, "--all")
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "arguments",
    [
        ("--auto", "--location-id", LOCATION_A),
        ("--auto", "--all"),
        ("--type", "farm_summary", "--location-id", LOCATION_A),
        ("--type", "state_of_kokonut"),
        ("--verify", "snapshot-hash"),
        ("--list", "--location-id", LOCATION_A),
    ],
)
def test_explicitly_scoped_generation_and_standalone_reads_are_valid(arguments) -> None:
    validate(*arguments)


@pytest.mark.parametrize(
    "arguments",
    [
        ("--type", "farm_summary", "--all"),
        ("--type", "farm_summary", "--location-id", LOCATION_A, "--location-id", LOCATION_B),
        ("--auto", "--location-id", LOCATION_A, "--location-id", LOCATION_B),
        ("--list", "--location-id", LOCATION_A, "--location-id", LOCATION_B),
        ("--type", "business_plan", "--location-id", LOCATION_A, "--location-id", LOCATION_A),
    ],
)
def test_unsupported_or_ambiguous_location_scopes_fail_before_database_access(arguments) -> None:
    with pytest.raises(SystemExit) as exc_info:
        validate(*arguments)

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "arguments",
    [
        ("--type", "business_plan", "--all"),
        ("--type", "scaling_economics"),
        ("--type", "scaling_economics", "--all"),
        ("--type", "comprehensive_status", "--all"),
        ("--type", "state_of_kokonut", "--location-id", LOCATION_A, "--location-id", LOCATION_B),
        ("--type", "business_plan", "--location-id", LOCATION_A, "--location-id", LOCATION_B),
        ("--type", "comprehensive_status"),
    ],
)
def test_explicit_aggregate_report_scopes_remain_available(arguments) -> None:
    validate(*arguments)


@pytest.mark.parametrize("report_type", sorted(report_generator.NETWORK_SCOPE_ONLY_REPORTS))
def test_network_only_reports_reject_farm_scope_and_allow_network_scope(report_type, capsys) -> None:
    validate("--type", report_type)
    validate("--type", report_type, "--all")

    with pytest.raises(SystemExit) as exc_info:
        validate("--type", report_type, "--location-id", LOCATION_A)

    assert exc_info.value.code == 2
    assert "is network-scoped" in capsys.readouterr().err


@pytest.mark.parametrize("report_type", sorted(report_generator.NETWORK_SCOPE_ONLY_REPORTS))
def test_network_scope_only_report_location_argument_is_unassigned(report_type) -> None:
    assert report_generator._generator_location_arg(report_type, LOCATION_A) is None
    assert report_generator._generator_location_arg(report_type, "all") is None
    assert report_generator._generator_location_arg("farm_summary", LOCATION_A) == LOCATION_A


def test_network_only_report_registry_matches_direct_scope_guards() -> None:
    guarded_types = {report_type for report_type, _generator in NETWORK_ONLY_GENERATORS}
    assert report_generator.NETWORK_SCOPE_ONLY_REPORTS == guarded_types


@pytest.mark.parametrize(("report_type", "generator"), NETWORK_ONLY_GENERATORS)
def test_network_only_generators_reject_direct_farm_scope_before_database_access(report_type, generator) -> None:
    connection = Mock()

    with pytest.raises(ValueError, match=f"{report_type} uses network-wide sources"):
        generator(connection, LOCATION_A)

    connection.cursor.assert_not_called()


def test_stakeholder_representation_uses_exact_public_projection_and_preserves_payload() -> None:
    columns = [
        "activity_type",
        "activity_id",
        "invited_count",
        "participated_count",
        "participation_rate_pct",
        "contribution_rate_pct",
        "minority_view_count",
        "minority_view_preserved_count",
    ]
    representation_rows = [
        {
            "activity_type": "decision",
            "activity_id": "00000000-0000-4000-8000-000000000001",
            "invited_count": 8,
            "participated_count": 6,
            "participation_rate_pct": 75.0,
            "contribution_rate_pct": 50.0,
            "minority_view_count": 2,
            "minority_view_preserved_count": 2,
        }
    ]
    distributions = [
        {
            "scope_type": "network",
            "scope_id": "00000000-0000-4000-8000-000000000010",
            "distribution_type": "benefit",
            "metric_name": "training_hours",
            "unit": "hours",
            "record_count": 3,
            "beneficiary_count": 3,
            "total_amount": 12.0,
            "earliest_period": "2026-01-01",
            "latest_period": "2026-09-30",
        }
    ]

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, query, params=None):
            self.current_query = " ".join(query.split())
            self.calls.append((self.current_query, params))

        def fetchall(self):
            if "v_public_stakeholder_representation" in self.current_query:
                return representation_rows
            return distributions

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class Connection:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    connection = Connection()
    report = generate_stakeholder_representation(connection)

    projection_query, projection_params = connection.cursor_value.calls[0]
    projection = re.search(
        r"SELECT (.*?) FROM v_public_stakeholder_representation",
        projection_query,
    )
    assert projection is not None
    assert [column.strip() for column in projection.group(1).split(",")] == columns
    assert projection_params is None
    assert "WHERE" not in projection_query
    assert "ORDER BY activity_type, activity_id" in projection_query
    assert connection.cursor_value.calls[1] == (
        "SELECT scope_type, scope_id, distribution_type, metric_name, unit, record_count, "
        "beneficiary_count, total_amount, earliest_period, latest_period "
        "FROM v_stakeholder_equity_distribution ORDER BY distribution_type, metric_name",
        None,
    )
    assert report["location_id"] is None
    assert report["representation"] == representation_rows
    assert report["representation_count"] == 1
    assert report["distributions"] == distributions
    assert report["distribution_count"] == 1

    _, distribution_params = connection.cursor_value.calls[1]
    assert distribution_params is None


def test_stakeholder_and_coordination_cockpits_use_exact_public_projections() -> None:
    stakeholder_columns = [
        "public_party_count",
        "representation_summary_count",
        "verified_outcome_count",
        "verified_impact_claim_count",
        "verified_distribution_count",
        "ecological_stewardship_count",
        "published_feedback_count",
        "privacy_limitation",
        "uncertainty_limitation",
        "generated_at",
        "published_alliance_count",
        "verified_alliance_benefit_count",
        "published_alliance_knowledge_count",
    ]
    coordination_columns = [
        "alliance_id",
        "name",
        "coordination_type",
        "market_cycle",
        "public_summary",
        "public_evidence",
        "public_limitations",
        "review_due_at",
        "verified_benefit_count",
        "published_knowledge_count",
        "verified_outcome_change_count",
        "privacy_limitation",
        "uncertainty_limitation",
    ]
    stakeholder_internal = {"active_party_count": 4, "open_grievance_count": 1}
    stakeholder_public = {
        "public_party_count": 3,
        "representation_summary_count": 2,
        "verified_outcome_count": 5,
        "verified_impact_claim_count": 4,
        "verified_distribution_count": 2,
        "ecological_stewardship_count": 1,
        "published_feedback_count": 3,
        "privacy_limitation": "Private and small-group records are excluded.",
        "uncertainty_limitation": "Counts do not prove satisfaction.",
        "generated_at": "2026-10-29T12:00:00Z",
        "published_alliance_count": 2,
        "verified_alliance_benefit_count": 1,
        "published_alliance_knowledge_count": 1,
    }
    coordination_internal = [{"name": "Internal alliance", "status": "active"}]
    coordination_public = [
        {
            "alliance_id": "00000000-0000-4000-8000-000000000001",
            "name": "Watershed learning alliance",
            "coordination_type": "learning",
            "market_cycle": "slow",
            "public_summary": "A published collaboration summary.",
            "public_evidence": {"review": "synthetic"},
            "public_limitations": ["Planning signal only."],
            "review_due_at": "2026-12-01T00:00:00Z",
            "verified_benefit_count": 2,
            "published_knowledge_count": 3,
            "verified_outcome_change_count": 1,
            "privacy_limitation": "Private evidence is excluded.",
            "uncertainty_limitation": "Published evidence does not prove success.",
        }
    ]

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, query, params=None):
            self.current_query = " ".join(query.split())
            self.calls.append((self.current_query, params))

        def fetchone(self):
            if "v_stakeholder_cockpit_internal" in self.current_query:
                return stakeholder_internal
            if "v_public_stakeholder_cockpit" in self.current_query:
                return stakeholder_public
            return None

        def fetchall(self):
            if "v_coordination_cockpit_internal" in self.current_query:
                return coordination_internal
            if "v_public_coordination_alliance" in self.current_query:
                return coordination_public
            return []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class Connection:
        def __init__(self):
            self.cursors = []

        def cursor(self, cursor_factory=None):
            cursor = Cursor()
            self.cursors.append(cursor)
            return cursor

    connection = Connection()
    stakeholder_report = generate_stakeholder_cockpit(connection)
    stakeholder_cursor = connection.cursors[-1]
    stakeholder_query, stakeholder_params = stakeholder_cursor.calls[1]
    stakeholder_projection = re.search(
        r"SELECT (.*?) FROM v_public_stakeholder_cockpit", stakeholder_query
    )
    assert stakeholder_projection is not None
    assert [column.strip() for column in stakeholder_projection.group(1).split(",")] == stakeholder_columns
    assert stakeholder_params is None
    assert "WHERE" not in stakeholder_query
    assert stakeholder_report["internal"] == stakeholder_internal
    assert stakeholder_report["public_safe"] == stakeholder_public

    coordination_report = generate_coordination_cockpit(connection)
    coordination_cursor = connection.cursors[-1]
    coordination_query, coordination_params = coordination_cursor.calls[1]
    coordination_projection = re.search(
        r"SELECT (.*?) FROM v_public_coordination_alliance", coordination_query
    )
    assert coordination_projection is not None
    assert [column.strip() for column in coordination_projection.group(1).split(",")] == coordination_columns
    assert coordination_params is None
    assert "WHERE" not in coordination_query
    assert "ORDER BY name" in coordination_query
    assert coordination_report["internal"] == coordination_internal
    assert coordination_report["public_safe"] == coordination_public


def test_internal_cockpit_views_use_exact_projections_at_every_report_callsite() -> None:
    stakeholder_columns = [
        "active_party_count",
        "active_relationship_count",
        "open_interest_count",
        "active_engagement_plan_count",
        "overdue_commitment_count",
        "open_grievance_count",
        "active_decision_count",
        "unresolved_harm_count",
        "open_relationship_risk_count",
        "pending_buyer_verification_count",
        "contested_trust_evidence_count",
        "stewardship_action_count",
        "unverified_value_stream_outcome_count",
        "generated_at",
        "active_alliance_count",
        "slow_cycle_alliance_count",
        "fast_cycle_alliance_count",
        "open_coordination_conflict_count",
        "open_coordination_remedy_count",
        "overdue_alliance_review_count",
    ]
    coordination_columns = [
        "alliance_id",
        "name",
        "coordination_type",
        "market_cycle",
        "status",
        "review_due_at",
        "ends_at",
        "work_item_id",
        "proxy_authority_id",
        "active_participant_count",
        "shared_objective_count",
        "contribution_count",
        "verified_benefit_count",
        "open_harm_count",
        "open_knowledge_exchange_count",
        "open_conflict_count",
        "trust_risk_count",
        "open_coordination_risk_count",
        "open_remedy_count",
        "preserved_minority_view_count",
        "verified_outcome_change_count",
        "ecological_obligation_count",
    ]
    stakeholder_row = {column: index for index, column in enumerate(stakeholder_columns)}
    stakeholder_row["generated_at"] = "2026-10-29T12:00:00Z"
    coordination_row = {
        column: index for index, column in enumerate(coordination_columns)
    }
    coordination_row.update(
        {
            "alliance_id": "00000000-0000-4000-8000-000000000001",
            "name": "Synthetic coordination alliance",
            "coordination_type": "learning",
            "market_cycle": "slow",
            "status": "active",
        }
    )

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, query, params=None):
            self.current_query = " ".join(query.split())
            self.calls.append((self.current_query, params))

        def fetchone(self):
            if "v_stakeholder_cockpit_internal" in self.current_query:
                return stakeholder_row
            return {}

        def fetchall(self):
            if "v_coordination_cockpit_internal" in self.current_query:
                return [coordination_row]
            if "v_stakeholder_landscape" in self.current_query:
                return [{"display_name": "Synthetic participant"}]
            if "relationship_risk_indicator" in self.current_query:
                return [{"status": "monitoring"}]
            if "v_party_relationship_recommendations" in self.current_query:
                return [{"recommendation": "review"}]
            return []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class Connection:
        def __init__(self):
            self.cursors = []

        def cursor(self, cursor_factory=None):
            cursor = Cursor()
            self.cursors.append(cursor)
            return cursor

    def assert_projection(query, view, columns):
        projection = re.search(rf"SELECT (.*?) FROM {view}", query)
        assert projection is not None
        assert [column.strip() for column in projection.group(1).split(",")] == columns

    connection = Connection()
    stakeholder_report = generate_stakeholder_cockpit(connection)
    cockpit_cursor = connection.cursors[-1]
    assert_projection(
        cockpit_cursor.calls[0][0], "v_stakeholder_cockpit_internal", stakeholder_columns
    )
    assert cockpit_cursor.calls[0][1] is None
    assert stakeholder_report["internal"] == stakeholder_row

    ecosystem_report = generate_stakeholder_ecosystem(connection)
    ecosystem_cursor = connection.cursors[-1]
    assert_projection(
        ecosystem_cursor.calls[0][0], "v_stakeholder_cockpit_internal", stakeholder_columns
    )
    assert ecosystem_cursor.calls[0][1] is None
    assert ecosystem_report["cockpit"] == stakeholder_row
    assert ecosystem_report["landscape"] == [{"display_name": "Synthetic participant"}]
    assert ecosystem_report["relationship_risks"] == [{"status": "monitoring"}]
    assert ecosystem_report["relationship_recommendations"] == [{"recommendation": "review"}]

    coordination_report = generate_coordination_cockpit(connection)
    coordination_cursor = connection.cursors[-1]
    assert_projection(
        coordination_cursor.calls[0][0],
        "v_coordination_cockpit_internal",
        coordination_columns,
    )
    assert coordination_cursor.calls[0][1] is None
    assert "ORDER BY name" in coordination_cursor.calls[0][0]
    assert coordination_report["internal"] == [coordination_row]


def test_roadmap_and_stakeholder_engagement_use_exact_view_projections() -> None:
    roadmap_columns = [
        "roadmap_id",
        "name",
        "entity_type",
        "entity_id",
        "planning_horizon_start",
        "planning_horizon_end",
        "detail_level",
        "sponsor",
        "owner",
        "status",
        "next_review_at",
        "requirement_count",
        "technology_area_count",
        "driver_count",
        "alternative_count",
        "selected_alternative_count",
        "last_reviewed_at",
    ]
    engagement_columns = [
        "plan_id",
        "name",
        "status",
        "engagement_mode",
        "stakeholder_party_id",
        "stakeholder_name",
        "objective_count",
        "touchpoint_count",
        "commitment_count",
        "open_commitment_count",
        "fulfilled_commitment_count",
        "overdue_commitment_count",
        "outcome_count",
        "last_outcome_at",
        "scope_type",
        "scope_id",
    ]
    commitment_columns = [
        "commitment_id",
        "plan_id",
        "plan_name",
        "stakeholder_name",
        "owner_name",
        "title",
        "status",
        "due_at",
        "work_item_id",
        "work_item_status",
        "responsibility_id",
        "is_overdue",
        "outcome_count",
        "last_outcome_at",
    ]
    roadmap_row = {"roadmap_id": "roadmap-1", "name": "Kernel roadmap", "status": "active"}
    plan_row = {
        "plan_id": "plan-1",
        "name": "Seasonal consultations",
        "scope_type": "location",
        "scope_id": LOCATION_A,
        "overdue_commitment_count": 1,
    }
    commitment_row = {"commitment_id": "commitment-1", "plan_id": "plan-1", "is_overdue": True}

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, query, params=None):
            self.current_query = " ".join(query.split())
            self.calls.append((self.current_query, params))

        def fetchall(self):
            if "v_technology_roadmap_overview" in self.current_query:
                return [roadmap_row]
            if "v_stakeholder_engagement_summary" in self.current_query:
                return [plan_row]
            if "v_stakeholder_commitment_health" in self.current_query:
                return [commitment_row]
            return []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class Connection:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    def assert_projection(query, view, columns):
        projection = re.search(rf"SELECT (.*?) FROM {view}", query)
        assert projection is not None
        assert [column.strip() for column in projection.group(1).split(",")] == columns

    connection = Connection()
    roadmap = generate_technology_roadmap(connection)
    roadmap_query, roadmap_params = connection.cursor_value.calls[0]
    assert_projection(roadmap_query, "v_technology_roadmap_overview", roadmap_columns)
    assert roadmap_params is None
    assert "ORDER BY name" in roadmap_query
    assert roadmap["roadmaps"] == [{**roadmap_row, "requirements": [], "alternatives": []}]

    engagement = generate_stakeholder_engagement(connection, location_id=LOCATION_A)
    summary_query, summary_params = connection.cursor_value.calls[-2]
    assert_projection(summary_query, "v_stakeholder_engagement_summary", engagement_columns)
    assert summary_params == [LOCATION_A]
    assert "WHERE scope_type = 'location' AND scope_id = %s::uuid" in summary_query
    assert "ORDER BY overdue_commitment_count DESC, name" in summary_query
    commitment_query, commitment_params = connection.cursor_value.calls[-1]
    assert_projection(commitment_query, "v_stakeholder_commitment_health", commitment_columns)
    assert commitment_params == ("plan-1",)
    assert "WHERE plan_id = %s AND is_overdue = TRUE" in commitment_query
    assert "ORDER BY due_at NULLS LAST" in commitment_query
    assert engagement["plans"] == [plan_row]
    assert engagement["overdue_commitments"] == [commitment_row]


def test_additional_strategy_projections_preserve_scope_order_and_report_payloads() -> None:
    projections = {
        "v_stakeholder_landscape_by_location": "location_id, party_id, party_type, display_name, party_status, privacy_level, identifier_count, active_relationship_count, open_interest_count, advisory_score, salience_review_status, last_updated_at",
        "v_stakeholder_landscape": "party_id, party_type, display_name, party_status, privacy_level, identifier_count, active_relationship_count, open_interest_count, advisory_score, salience_review_status, last_updated_at",
        "v_stakeholder_cockpit_internal": "active_party_count, active_relationship_count, open_interest_count, active_engagement_plan_count, overdue_commitment_count, open_grievance_count, active_decision_count, unresolved_harm_count, open_relationship_risk_count, pending_buyer_verification_count, contested_trust_evidence_count, stewardship_action_count, unverified_value_stream_outcome_count, generated_at, active_alliance_count, slow_cycle_alliance_count, fast_cycle_alliance_count, open_coordination_conflict_count, open_coordination_remedy_count, overdue_alliance_review_count",
        "v_stakeholder_grievance_health": "case_id, case_number, category, severity, confidentiality, status, summary, location_id, complainant_name, affected_party_name, owner_name, received_at, due_at, work_item_id, investigation_count, evidence_count, remedy_count, open_remedy_count, appeal_count, satisfaction_score, is_overdue",
        "v_stakeholder_decision_lineage": "decision_id, decision_key, title, decision_type, scope_type, scope_id, status, approval_status, approval_actor_type, approval_role, material_harm_review_status, minority_review_status, created_by_name, approved_by_name, approved_at, decision_log_id, work_item_id, participant_count, participating_count, minority_participant_count, tradeoff_count, unresolved_harm_count, evidence_count, verified_evidence_count, outcome_count, last_outcome_at",
        "relationship_risk_indicator": "id, subject_party_id, relationship_party_id, risk_key, severity, rationale, evidence_ids, uncertainty, status, reviewed_by_party_id, created_at",
        "v_party_relationship_recommendations": "party_id, display_name, recommendation, evidence_count, maximum_uncertainty, human_review_required, limitation",
        "v_party_trust_profile": "party_id, display_name, party_type, evidence_count, supporting_evidence_count, contradicting_evidence_count, contested_evidence_count, open_risk_count, latest_evidence_at, earliest_evidence_at, latest_snapshot_at, latest_uncertainty, interpretation",
        "v_market_dispute_performance": "dispute_count, resolved_count, open_count, average_resolution_days, open_appeal_count, correction_request_count",
        "v_party_financing_eligibility_inputs": "party_id, display_name, identity_evidence_count, payment_support_count, contradicting_evidence_count, open_risk_count, maximum_uncertainty, human_review_required, limitation",
        "v_stakeholder_capability_value_stream": "entity_type, entity_id, entity_name, party_id, party_name, relationship_type, desired_outcome, demand_level, criticality, harm_exposure, dependency_risk, stakeholder_promise, service_quality_target, satisfaction_target, status",
        "v_value_stream_performance": "stream_id, stream_name, stakeholder_type, trigger_event, end_state, stream_status, stage_id, stage_name, sequence_order, process_key, target_lead_time_hours, target_fty_pct, observation_count, avg_lead_time_hours, avg_fty_pct, last_observed_at",
        "stakeholder_bottleneck_priority": "id, stage_id, party_id, outcome_id, process_key, priority, harm_if_unresolved, value_at_risk, value_unit, evidence, reviewed_by_party_id, reviewed_at, status",
        "technology_alternative_stakeholder_outcome": "id, alternative_id, party_id, outcome_id, expected_benefit, expected_harm_reduction, access_effects, equity_effects, estimated_value, estimated_value_unit, uncertainty, evidence, reviewed_by_party_id, reviewed_at, status",
        "v_governance_cockpit_internal": "active_circle_count, active_role_count, unassigned_role_count, overdue_assignment_review_count, unresolved_tension_count, high_severity_tension_count, proposals_awaiting_review_count, open_objection_count, material_objection_count, links_expiring_soon_count, overdue_tactical_item_count, open_tactical_item_count, generated_at",
        "v_governance_cockpit_public": "active_circle_count, active_role_count, resolved_tension_count, implemented_proposal_count, privacy_limitation, generated_at",
        "v_governance_tension_health": "tension_id, tension_key, title, description, tension_type, severity, urgency, circle_id, circle_key, circle_name, scope_type, scope_id, status, reported_by_party_id, reported_by_name, affected_party_id, affected_party_name, owner_role_id, owner_role_key, owner_party_id, owner_party_name, work_item_id, decision_id, grievance_id, review_due_at, deferred_until, link_count, is_overdue",
        "v_governance_proposal_lineage": "proposal_id, proposal_key, circle_id, circle_key, proposal_type, title, status, tension_id, proposed_by_party_id, proposer_name, proposed_by_role_id, proposer_role_key, harm_review_status, minority_review_status, approved_by_party_id, approver_name, approved_at, implementation_work_item_id, review_due_at, objection_count, open_objection_count, open_material_objection_count, review_count",
        "v_governance_circle_links": "link_id, source_circle_id, source_circle_key, target_circle_id, target_circle_key, link_type, role_id, role_key, party_id, party_name, mandate, scope_type, scope_id, term_start, term_end, status, recusal_status, approved_by_party_id, approved_by_name",
    }

    def columns(relation):
        return [column.strip() for column in projections[relation].split(",")]

    def assert_projection(query, relation):
        match = re.search(rf"SELECT (.*?) FROM {relation}(?:\s|$)", query)
        assert match is not None, query
        assert [column.strip() for column in match.group(1).split(",")] == columns(relation)

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_relation = ""

        def execute(self, query, params=None):
            normalized = " ".join(query.split())
            relation_match = re.search(r"\bFROM ([a-z_]+)", normalized)
            assert relation_match is not None, normalized
            self.current_relation = relation_match.group(1)
            self.calls.append((normalized, params))

        def fetchall(self):
            return [{"payload": self.current_relation, "is_overdue": True}]

        def fetchone(self):
            return {"payload": self.current_relation}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class Connection:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    location_cases = [
        (
            generate_stakeholder_landscape,
            ["v_stakeholder_landscape_by_location"],
            "parties",
            "WHERE location_id = %s::uuid ORDER BY advisory_score DESC NULLS LAST, display_name",
        ),
        (
            generate_stakeholder_grievance,
            ["v_stakeholder_grievance_health"],
            "cases",
            "WHERE location_id = %s::uuid ORDER BY is_overdue DESC, severity DESC, received_at",
        ),
        (
            generate_stakeholder_decision_lineage,
            ["v_stakeholder_decision_lineage"],
            "decisions",
            "WHERE scope_type = 'location' AND scope_id = %s::uuid ORDER BY approved_at DESC NULLS LAST, decision_id",
        ),
    ]
    for generator, relations, payload_key, expected_suffix in location_cases:
        connection = Connection()
        report = generator(connection, location_id=LOCATION_A)
        assert len(connection.cursor_value.calls) == len(relations)
        query, params = connection.cursor_value.calls[0]
        assert_projection(query, relations[0])
        assert params == [LOCATION_A]
        assert query.endswith(expected_suffix)
        assert report[payload_key] == [{"payload": relations[0], "is_overdue": True}]
        if generator is generate_stakeholder_grievance:
            assert report["overdue_count"] == 1

    network_cases = [
        (
            generate_stakeholder_ecosystem,
            [
                "v_stakeholder_cockpit_internal",
                "v_stakeholder_landscape",
                "relationship_risk_indicator",
                "v_party_relationship_recommendations",
            ],
            [
                "",
                "ORDER BY advisory_score DESC NULLS LAST, display_name",
                "ORDER BY created_at DESC",
                "ORDER BY recommendation, display_name",
            ],
            {
                "landscape": "v_stakeholder_landscape",
                "relationship_risks": "relationship_risk_indicator",
                "relationship_recommendations": "v_party_relationship_recommendations",
            },
        ),
        (
            generate_stakeholder_trust,
            [
                "v_party_trust_profile",
                "v_market_dispute_performance",
                "relationship_risk_indicator",
                "v_party_financing_eligibility_inputs",
            ],
            [
                "ORDER BY open_risk_count DESC, display_name",
                "",
                "WHERE status IN ('open', 'monitoring') ORDER BY created_at DESC",
                "ORDER BY open_risk_count DESC, display_name",
            ],
            {
                "profiles": "v_party_trust_profile",
                "relationship_risks": "relationship_risk_indicator",
                "financing_and_insurance_inputs": "v_party_financing_eligibility_inputs",
            },
        ),
        (
            generate_stakeholder_value_streams,
            [
                "v_stakeholder_capability_value_stream",
                "v_value_stream_performance",
                "stakeholder_bottleneck_priority",
                "technology_alternative_stakeholder_outcome",
            ],
            [
                "ORDER BY entity_type, entity_name, party_name",
                "",
                "WHERE status IN ('reviewed', 'active') ORDER BY priority, reviewed_at DESC NULLS LAST",
                "WHERE status IN ('reviewed', 'approved') ORDER BY reviewed_at DESC NULLS LAST",
            ],
            {
                "stakeholder_links": "v_stakeholder_capability_value_stream",
                "performance": "v_value_stream_performance",
                "stakeholder_bottleneck_priorities": "stakeholder_bottleneck_priority",
                "technology_alternative_outcomes": "technology_alternative_stakeholder_outcome",
            },
        ),
        (
            generate_governance_coordination_health,
            [
                "v_governance_cockpit_internal",
                "v_governance_cockpit_public",
                "v_governance_tension_health",
                "v_governance_proposal_lineage",
                "v_governance_circle_links",
            ],
            [
                "",
                "",
                "ORDER BY severity DESC, urgency DESC",
                "ORDER BY approved_at DESC NULLS LAST, proposal_id",
                "ORDER BY term_end NULLS LAST",
            ],
            {
                "tensions": "v_governance_tension_health",
                "proposals": "v_governance_proposal_lineage",
                "circle_links": "v_governance_circle_links",
            },
        ),
    ]
    for generator, relations, clauses, payload_rows in network_cases:
        connection = Connection()
        report = generator(connection)
        assert len(connection.cursor_value.calls) == len(relations)
        for (query, params), relation, clause in zip(
            connection.cursor_value.calls, relations, clauses, strict=True
        ):
            assert_projection(query, relation)
            assert params is None
            if clause:
                assert query.endswith(clause)
        for key, relation in payload_rows.items():
            assert report[key] == [{"payload": relation, "is_overdue": True}]
        if generator is generate_stakeholder_ecosystem:
            assert report["relationship_recommendations"] == [
                {"payload": "v_party_relationship_recommendations", "is_overdue": True}
            ]
        elif generator is generate_stakeholder_trust:
            assert report["dispute_performance"] == {"payload": "v_market_dispute_performance"}
        elif generator is generate_governance_coordination_health:
            assert report["internal"] == {"payload": "v_governance_cockpit_internal"}
            assert report["public_safe"] == {"payload": "v_governance_cockpit_public"}



def test_check_report_empty_reports_empty_primary_sections(capsys) -> None:
    is_empty = report_generator._check_report_empty({"farms": []}, "farm_summary")

    assert is_empty is True
    assert "no rows in 'farms'" in capsys.readouterr().out


def test_check_report_empty_returns_false_when_primary_rows_exist(capsys) -> None:
    is_empty = report_generator._check_report_empty({"farms": [{"id": "farm-1"}]}, "farm_summary")

    assert is_empty is False
    assert capsys.readouterr().out == ""


def test_auto_generation_counts_stored_reports_with_empty_primary_rows(monkeypatch, capsys) -> None:
    connection = MagicMock()
    monkeypatch.setattr(report_generator, "REPORT_GENERATORS", {"farm_summary": object()})
    monkeypatch.setattr(
        report_generator,
        "generate_report_data_read_only",
        lambda *_args: {"report_type": "farm_summary", "farms": []},
    )
    monkeypatch.setattr(report_generator, "store_snapshot", lambda *_args: "snapshot-1")
    monkeypatch.setattr(report_generator, "compute_hash", lambda _data: "synthetic-hash")

    report_generator._run_auto_generation(
        connection,
        location_arg=LOCATION_A,
        location_label=LOCATION_A,
        period_start=None,
        period_end=None,
    )

    output = capsys.readouterr().out
    assert "no rows in 'farms'" in output
    assert "Done: 1 succeeded, 0 failed, 1 empty" in output


@pytest.mark.parametrize("report_type", sorted(report_generator.NETWORK_SCOPE_ONLY_REPORTS))
def test_auto_generation_stores_network_only_reports_without_farm_scope(monkeypatch, report_type) -> None:
    connection = MagicMock()
    observed = {"generation_location": None, "snapshot_location": LOCATION_A}

    monkeypatch.setattr(report_generator, "REPORT_GENERATORS", {report_type: object()})
    monkeypatch.setattr(
        report_generator,
        "generate_report_data_read_only",
        lambda _conn, _generator, location_id, _start, _end: observed.update(
            generation_location=location_id
        ) or {"report_type": report_type},
    )
    monkeypatch.setattr(report_generator, "_check_report_empty", lambda _data, _report_type: None)
    monkeypatch.setattr(report_generator, "store_snapshot", lambda _conn, _data, location_id, *_: (
        observed.update(snapshot_location=location_id) or "snapshot-id"
    ))
    monkeypatch.setattr(report_generator, "compute_hash", lambda _data: "hash")

    report_generator._run_auto_generation(
        connection,
        location_arg=LOCATION_A,
        location_label=LOCATION_A,
        period_start=None,
        period_end=None,
    )

    assert observed == {"generation_location": None, "snapshot_location": None}


def test_invalid_scope_exits_before_opening_postgres(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        report_generator,
        "get_pg",
        lambda: (_ for _ in ()).throw(AssertionError("database must not open")),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "report_generator",
            "--type",
            "farm_summary",
            "--location-id",
            LOCATION_A,
            "--location-id",
            LOCATION_B,
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        report_generator.main()

    assert exc_info.value.code == 2
    assert "multiple --location-id values are not supported" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments",
    [
        ("--type", "farm_summary", "--location-id", "not-a-uuid"),
        ("--list", "--location-id", "not-a-uuid"),
    ],
)
def test_malformed_location_uuid_fails_before_database_access(arguments) -> None:
    with pytest.raises(SystemExit) as exc_info:
        validate(*arguments)

    assert exc_info.value.code == 2


def test_duplicate_uuid_spellings_are_canonicalized_before_scope_check(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        validate(
            "--type",
            "business_plan",
            "--location-id",
            LOCATION_A,
            "--location-id",
            LOCATION_A.upper(),
        )

    assert exc_info.value.code == 2
    assert "--location-id values must be unique" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments",
    [
        ("--type", "farm_summary", "--location-id", LOCATION_A, "--period-start", "2026-2-01"),
        ("--type", "farm_summary", "--location-id", LOCATION_A, "--period-end", "not-a-date"),
        (
            "--type",
            "farm_summary",
            "--location-id",
            LOCATION_A,
            "--period-start",
            "2026-02-02",
            "--period-end",
            "2026-02-01",
        ),
    ],
)
def test_invalid_or_reversed_periods_fail_before_database_access(arguments) -> None:
    with pytest.raises(SystemExit) as exc_info:
        validate(*arguments)

    assert exc_info.value.code == 2


def test_ordered_iso_period_is_valid() -> None:
    validate(
        "--type",
        "farm_summary",
        "--location-id",
        LOCATION_A,
        "--period-start",
        "2026-02-01",
        "--period-end",
        "2026-02-02",
    )
