"""CLI scope contract for the complete report generator catalog."""

import pytest

from services.export import report_generator
from services.export.report_generator import build_parser, validate_args

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
