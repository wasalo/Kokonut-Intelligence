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
    generate_stakeholder_ecosystem,
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
