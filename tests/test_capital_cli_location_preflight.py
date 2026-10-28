"""Location UUIDs are rejected before the capital CLI opens PostgreSQL."""

from services.capital import cli

LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
HANDLERS = (
    ("capacity", ()),
    ("diversion", ("2026-01-01", "2026-01-31")),
    ("capture", ()),
    ("credit_propose", ("cooperative_surplus", 1.5)),
    ("credit_list", ()),
    ("credit_capacity", ()),
    ("report", ("2026-01-01", "2026-01-31")),
)
SERVICES = {
    "capacity": (cli.capacity, "assess_capacity"),
    "diversion": (cli.diversion, "compute_diversion_index"),
    "capture": (cli.capture, "capture_risk"),
    "credit_propose": (cli.credit, "propose_credit"),
    "credit_list": (cli.credit, "list_draft_credits"),
    "credit_capacity": (cli.credit, "credit_capacity"),
    "report": (cli.accounting_report, "build_capital_accounting"),
}


def _invoke(name, location_id):
    handler = getattr(cli, f"cmd_{name}")
    return handler(location_id, *dict(HANDLERS)[name])


def test_every_capital_command_rejects_bad_location_before_database_access(monkeypatch):
    def unexpected_database_access():
        raise AssertionError("invalid location must fail before PostgreSQL opens")

    monkeypatch.setattr(cli, "get_db", unexpected_database_access)
    for bad_location in ("", "not-a-uuid", None):
        for name, _args in HANDLERS:
            try:
                _invoke(name, bad_location)
            except ValueError as exc:
                assert str(exc) == "location_id must be a valid UUID"
            else:
                raise AssertionError(f"{name} accepted invalid location {bad_location!r}")


def test_every_capital_command_passes_canonical_location_and_closes_connection(monkeypatch):
    class Connection:
        closed = False
        committed = False

        def close(self):
            self.closed = True

        def commit(self):
            self.committed = True

    connection = Connection()
    database_calls = []
    service_calls = []
    printed = []
    monkeypatch.setattr(cli, "get_db", lambda: database_calls.append(True) or connection)
    monkeypatch.setattr(cli, "print_json", printed.append)

    for name, _args in HANDLERS:
        target, function_name = SERVICES[name]

        def service(conn, location_id, *args, _name=name, **kwargs):
            service_calls.append((_name, conn, location_id, args, kwargs))
            return {"command": _name}

        monkeypatch.setattr(target, function_name, service)
        _invoke(name, LOCATION_ID.upper())

    assert len(database_calls) == len(HANDLERS)
    assert [call[0] for call in service_calls] == [name for name, _args in HANDLERS]
    assert all(call[1] is connection for call in service_calls)
    assert all(call[2] == LOCATION_ID for call in service_calls)
    assert printed == [{"command": name} for name, _args in HANDLERS]
    assert connection.closed
    assert connection.committed


def test_all_capital_subcommands_require_location_scope():
    parser = cli.build_parser()

    for argv in (
        ["capacity"],
        ["diversion"],
        ["capture"],
        ["credit", "propose", "--source-type", "cooperative_surplus", "--amount", "1"],
        ["credit", "list"],
        ["credit", "capacity"],
        ["report"],
    ):
        try:
            parser.parse_args(argv)
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError(f"parser accepted missing location: {argv}")
