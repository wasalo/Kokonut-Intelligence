"""CLI scope contract for the complete report generator catalog."""

import pytest

from services.export import report_generator
from services.export.report_generator import build_parser, validate_args


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
        ("--auto", "--location-id", "location-a"),
        ("--auto", "--all"),
        ("--type", "farm_summary", "--location-id", "location-a"),
        ("--type", "state_of_kokonut"),
        ("--verify", "snapshot-hash"),
        ("--list", "--location-id", "location-a"),
    ],
)
def test_explicitly_scoped_generation_and_standalone_reads_are_valid(arguments) -> None:
    validate(*arguments)


@pytest.mark.parametrize(
    "arguments",
    [
        ("--type", "farm_summary", "--all"),
        ("--type", "farm_summary", "--location-id", "location-a", "--location-id", "location-b"),
        ("--auto", "--location-id", "location-a", "--location-id", "location-b"),
        ("--list", "--location-id", "location-a", "--location-id", "location-b"),
        ("--type", "business_plan", "--location-id", "location-a", "--location-id", "location-a"),
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
        ("--type", "state_of_kokonut", "--location-id", "location-a", "--location-id", "location-b"),
        ("--type", "business_plan", "--location-id", "location-a", "--location-id", "location-b"),
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
            "location-a",
            "--location-id",
            "location-b",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        report_generator.main()

    assert exc_info.value.code == 2
    assert "multiple --location-id values are not supported" in capsys.readouterr().err
