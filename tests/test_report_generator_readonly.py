"""Report calculations cannot write before the governed snapshot transaction."""

import inspect
import sys

import pytest

from services.export import report_generator
from services.export.reports import REPORT_GENERATORS as REGISTERED_REPORT_GENERATORS
from services.export.reports import business_plan as business_plan_reports


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params=None):
        statement = query.strip().split(maxsplit=1)[0].upper()
        if self.connection.read_only and statement in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"}:
            raise RuntimeError("write attempted during read-only report calculation")


class _Connection:
    def __init__(self):
        self.read_only = False
        self.autocommit = False
        self.session_modes = []
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rollbacks += 1

    def set_session(self, *, readonly):
        self.session_modes.append(readonly)
        self.read_only = readonly

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def _run_cli(monkeypatch, *, auto=False):
    connection = _Connection()
    observed = []

    def generate(conn, location_id, period_start, period_end):
        observed.append((conn.read_only, location_id, period_start, period_end))
        with conn.cursor() as cur:
            cur.execute("SELECT report source")
        return {"report_type": "farm_summary", "rows": [{"count": 1}]}

    def store(conn, report_data, location_id, period_start, period_end):
        assert not conn.read_only
        conn.commit()
        return "synthetic-snapshot-id"

    monkeypatch.setattr(report_generator, "get_pg", lambda: connection)
    monkeypatch.setattr(report_generator, "REPORT_GENERATORS", {"farm_summary": generate})
    monkeypatch.setattr(report_generator, "store_snapshot", store)
    monkeypatch.setattr(report_generator, "compute_hash", lambda _data: "synthetic-hash")
    monkeypatch.setattr(
        sys,
        "argv",
        ["report_generator", "--auto", "--location-id", "11111111-1111-4111-8111-111111111111"]
        if auto
        else [
            "report_generator",
            "--type",
            "farm_summary",
            "--location-id",
            "11111111-1111-4111-8111-111111111111",
        ],
    )

    report_generator.main()
    return connection, observed


@pytest.mark.parametrize("auto", [False, True], ids=["single", "batch"])
def test_report_cli_runs_calculation_read_only_then_persists_draft(monkeypatch, auto):
    connection, observed = _run_cli(monkeypatch, auto=auto)

    assert observed == [(True, "11111111-1111-4111-8111-111111111111", None, None)]
    assert connection.rollbacks == 1
    assert connection.session_modes == [True, False]
    assert connection.commits >= 1
    assert connection.closed


def test_failed_read_only_generation_rolls_back_before_recording_failure(monkeypatch):
    connection = _Connection()

    def generate(conn, *_args):
        assert conn.read_only
        raise RuntimeError("synthetic generator failure")

    monkeypatch.setattr(report_generator, "get_pg", lambda: connection)
    monkeypatch.setattr(report_generator, "REPORT_GENERATORS", {"farm_summary": generate})
    monkeypatch.setattr(sys, "argv", ["report_generator", "--auto", "--all"])

    with pytest.raises(SystemExit) as exc_info:
        report_generator.main()

    assert exc_info.value.code == 1
    assert connection.rollbacks == 2
    assert connection.session_modes == [True, False]
    assert not connection.read_only
    assert connection.closed


def test_report_generator_cannot_lower_read_only_session_mode():
    connection = _Connection()

    def generator(read_only_conn, *_args):
        read_only_conn.set_session(readonly=False)

    with pytest.raises(RuntimeError, match="cannot lower the read-only database mode"):
        report_generator.generate_report_data_read_only(
            connection, generator, "location-id", None, None
        )

    assert connection.rollbacks == 1
    assert connection.session_modes == [True, False]
    assert not connection.read_only


def test_report_generator_cannot_enable_autocommit_and_restores_connection():
    connection = _Connection()
    connection.autocommit = False

    def generator(read_only_conn, *_args):
        assert read_only_conn.read_only
        read_only_conn.rollback()
        read_only_conn.autocommit = True

    with pytest.raises(RuntimeError, match="cannot enable autocommit"):
        report_generator.generate_report_data_read_only(
            connection, generator, "location-id", None, None
        )
    assert connection.session_modes == [True, False]
    assert not connection.read_only
    assert connection.autocommit is False


def test_report_cursor_does_not_expose_raw_connection_escape():
    connection = _Connection()

    def generator(read_only_conn, *_args):
        with read_only_conn.cursor() as cur:
            cur.connection.autocommit = True

    with pytest.raises(RuntimeError, match="cannot enable autocommit"):
        report_generator.generate_report_data_read_only(
            connection, generator, "location-id", None, None
        )
    assert connection.autocommit is False
    assert connection.session_modes == [True, False]


def test_report_generator_write_is_rejected_and_session_mode_is_restored():
    connection = _Connection()

    def generator(read_only_conn, *_args):
        with read_only_conn.cursor() as cur:
            cur.execute("INSERT INTO farm_activity DEFAULT VALUES")

    with pytest.raises(RuntimeError, match="write attempted during read-only"):
        report_generator.generate_report_data_read_only(
            connection, generator, "location-id", None, None
        )

    assert connection.rollbacks == 1
    assert connection.session_modes == [True, False]
    assert not connection.read_only


def test_every_registered_report_accepts_the_cli_generator_signature():
    incompatible = {
        name: str(inspect.signature(generator))
        for name, generator in REGISTERED_REPORT_GENERATORS.items()
        if not _accepts_cli_signature(generator)
    }

    assert len(REGISTERED_REPORT_GENERATORS) == 94
    assert incompatible == {}


def _accepts_cli_signature(generator):
    try:
        inspect.signature(generator).bind(None, "location-id", None, None)
    except TypeError:
        return False
    return True


def test_business_plan_adapter_preserves_single_and_all_location_scopes(monkeypatch):
    generated = []

    def fake_generate(_conn, *, location_id):
        generated.append(location_id)
        return {"meta": {"location_id": location_id}}

    monkeypatch.setattr(business_plan_reports, "generate_business_plan", fake_generate)

    class Cursor:
        def __init__(self, connection):
            self.connection = connection

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query):
            self.connection.queries.append(query)

        def fetchall(self):
            return [("location-a",), ("location-b",)]

    class Connection:
        def __init__(self):
            self.queries = []

        def cursor(self):
            return Cursor(self)

    connection = Connection()
    single = business_plan_reports.generate_business_plan_report(
        connection, "location-a", None, None
    )
    all_locations = business_plan_reports.generate_business_plan_report(
        connection, "all", None, None
    )

    assert single == {
        "report_type": "business_plan",
        "meta": {"location_id": "location-a"},
    }
    assert all_locations == {
        "report_type": "business_plan",
        "scope": "all_locations",
        "location_count": 2,
        "plans": [
            {"meta": {"location_id": "location-a"}},
            {"meta": {"location_id": "location-b"}},
        ],
    }
    assert generated == ["location-a", "location-a", "location-b"]
    assert connection.queries == ["SELECT id FROM location ORDER BY id"]


def test_revenue_multiplier_requires_location_before_analyzer(monkeypatch):
    from services.export.reports import core
    from services.revenue_multiplier import analyzer

    def fail_if_analyzer_runs(_location_id):
        raise AssertionError("revenue analysis must not start without a location")

    monkeypatch.setattr(analyzer, "analyze_location", fail_if_analyzer_runs)

    for location_id in (None, ""):
        with pytest.raises(
            ValueError,
            match="revenue_multiplier requires an explicit location_id",
        ):
            core.generate_revenue_multiplier(None, location_id)
