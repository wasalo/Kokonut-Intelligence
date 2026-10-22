"""CLI scope contract for the complete report generator catalog."""

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
