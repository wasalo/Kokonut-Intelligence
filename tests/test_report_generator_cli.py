"""CLI scope contract for the complete report generator catalog."""

import pytest

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
