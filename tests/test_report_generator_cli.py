"""CLI scope contract for the complete report generator catalog."""

from unittest.mock import MagicMock, Mock

import pytest

from services.export import report_generator
from services.export.report_generator import build_parser, validate_args
from services.export.reports.strategy import generate_stakeholder_cockpit

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
        ("--type", "comprehensive_status", "--all"),
        ("--type", "state_of_kokonut", "--location-id", LOCATION_A, "--location-id", LOCATION_B),
        ("--type", "business_plan", "--location-id", LOCATION_A, "--location-id", LOCATION_B),
        ("--type", "comprehensive_status"),
    ],
)
def test_explicit_aggregate_report_scopes_remain_available(arguments) -> None:
    validate(*arguments)


def test_stakeholder_cockpit_is_network_scoped_and_rejects_farm_scope(capsys) -> None:
    validate("--type", "stakeholder_cockpit")
    validate("--type", "stakeholder_cockpit", "--all")

    with pytest.raises(SystemExit) as exc_info:
        validate("--type", "stakeholder_cockpit", "--location-id", LOCATION_A)

    assert exc_info.value.code == 2
    assert "is network-scoped" in capsys.readouterr().err


def test_network_scope_only_report_location_argument_is_unassigned() -> None:
    assert report_generator._generator_location_arg("stakeholder_cockpit", LOCATION_A) is None
    assert report_generator._generator_location_arg("stakeholder_cockpit", "all") is None
    assert report_generator._generator_location_arg("farm_summary", LOCATION_A) == LOCATION_A


def test_stakeholder_cockpit_rejects_direct_farm_scope_before_database_access() -> None:
    connection = Mock()

    with pytest.raises(ValueError, match="cannot be farm-scoped"):
        generate_stakeholder_cockpit(connection, LOCATION_A)

    connection.cursor.assert_not_called()


def test_auto_generation_stores_network_cockpit_without_farm_scope(monkeypatch) -> None:
    connection = MagicMock()
    observed = {"generation_location": None, "snapshot_location": LOCATION_A}

    monkeypatch.setattr(report_generator, "REPORT_GENERATORS", {"stakeholder_cockpit": object()})
    monkeypatch.setattr(
        report_generator,
        "generate_report_data_read_only",
        lambda _conn, _generator, location_id, _start, _end: observed.update(
            generation_location=location_id
        ) or {"report_type": "stakeholder_cockpit"},
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
