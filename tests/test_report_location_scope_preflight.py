"""Direct report scope validation must happen before database access."""

from unittest.mock import patch

import pytest

from services.export import business_plan as business_plan_service
from services.export.reports import business_plan as business_plan_reports
from services.export.reports import state
from services.strategic_reserve import health as reserve_health

LOCATION_A = "a0000000-0000-0000-0000-000000000001"
LOCATION_B = "b0000000-0000-0000-0000-000000000002"


class _Cursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows

    def close(self):
        return None


class _Connection:
    def __init__(self, rows=None):
        self.cursor_obj = _Cursor(rows)
        self.cursor_calls = 0
        self.rollback_calls = 0
        self._autocommit = False

    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, value):
        self._autocommit = value

    def cursor(self, *_args, **_kwargs):
        self.cursor_calls += 1
        return self.cursor_obj

    def rollback(self):
        self.rollback_calls += 1


@pytest.mark.parametrize("location_id", ["not-a-uuid", f"{LOCATION_A},bad", f"{LOCATION_A},"])
def test_business_plan_report_rejects_invalid_scope_before_cursor_or_generator(location_id):
    conn = _Connection()
    with patch.object(business_plan_reports, "generate_business_plan") as generate:
        with pytest.raises(ValueError, match="valid UUIDs"):
            business_plan_reports.generate_business_plan_report(conn, location_id)

    assert conn.cursor_calls == 0
    generate.assert_not_called()


def test_business_plan_report_preserves_all_and_valid_selected_locations():
    conn = _Connection(rows=[(LOCATION_A,), (LOCATION_B,)])
    with patch.object(
        business_plan_reports,
        "generate_business_plan",
        side_effect=lambda _conn, *, location_id: {"meta": {"location_id": location_id}},
    ) as generate:
        result = business_plan_reports.generate_business_plan_report(conn, "ALL")

    assert result["scope"] == "all_locations"
    assert result["location_count"] == 2
    assert [call.kwargs["location_id"] for call in generate.call_args_list] == [LOCATION_A, LOCATION_B]
    assert conn.cursor_calls == 1


def test_business_plan_report_valid_single_uuid_dispatches_canonically():
    conn = _Connection()
    with patch.object(
        business_plan_reports,
        "generate_business_plan",
        return_value={"meta": {"grain": "location"}},
    ) as generate:
        result = business_plan_reports.generate_business_plan_report(conn, LOCATION_A.upper())

    assert result["meta"]["grain"] == "location"
    generate.assert_called_once_with(conn, location_id=LOCATION_A)
    assert conn.cursor_calls == 0


def test_business_plan_report_valid_uuid_list_dispatches_each_location():
    conn = _Connection()
    with patch.object(
        business_plan_reports,
        "generate_business_plan",
        side_effect=lambda _conn, *, location_id: {"meta": {"location_id": location_id}},
    ) as generate:
        result = business_plan_reports.generate_business_plan_report(conn, f"{LOCATION_A},{LOCATION_B.upper()}")

    assert result["scope"] == "selected_locations"
    assert [call.kwargs["location_id"] for call in generate.call_args_list] == [LOCATION_A, LOCATION_B]
    assert conn.cursor_calls == 0


@pytest.mark.parametrize("location_id", ["bad", "", f" {LOCATION_A} , bad "])
def test_direct_business_plan_rejects_supplied_invalid_location_before_connection_changes(location_id):
    conn = _Connection()
    with patch.object(business_plan_service, "_section") as section:
        with pytest.raises(ValueError, match="location_id must be a valid UUID"):
            business_plan_service.generate_business_plan(conn, location_id=location_id, org_id=LOCATION_B)

    assert conn.cursor_calls == 0
    assert conn.rollback_calls == 0
    assert conn.autocommit is False
    section.assert_not_called()


@pytest.mark.parametrize("location_id", [LOCATION_A, LOCATION_A.upper()])
def test_direct_business_plan_preserves_valid_location_dispatch(location_id):
    conn = _Connection()
    with patch.object(business_plan_service, "_section", return_value={}) as section:
        result = business_plan_service.generate_business_plan(conn, location_id=location_id)

    assert result["meta"]["grain"] == "location"
    assert result["meta"]["location_id"] == LOCATION_A
    assert section.call_count == 6
    assert conn.rollback_calls == 1
    assert conn.autocommit is False


def test_direct_business_plan_preserves_org_only_mode():
    conn = _Connection()
    with patch.object(business_plan_service, "_section", return_value={}) as section:
        result = business_plan_service.generate_business_plan(conn, org_id=LOCATION_B)

    assert result["meta"]["grain"] == "organization"
    assert result["meta"]["location_id"] is None
    assert result["meta"]["org_id"] == LOCATION_B
    assert section.call_count == 6


@pytest.mark.parametrize("scope", [None, "all"])
def test_state_report_network_scope_is_preserved(scope):
    conn = _Connection()
    with patch.object(state, "_state_of_kokonut_locations", return_value=([], [])) as locations, patch.object(
        state, "_state_of_kokonut_actors", return_value={}
    ):
        report = state.generate_state_of_kokonut(conn, scope)

    assert report["scope"] == "all_locations"
    locations.assert_called_once_with(conn, None, None, None)


@pytest.mark.parametrize("location_id", ["bad", f"{LOCATION_A},bad", "", " , "])
def test_state_of_kokonut_rejects_invalid_selection_before_helper(location_id):
    conn = _Connection()
    with patch.object(state, "_state_of_kokonut_locations") as locations, patch.object(
        state, "_state_of_kokonut_actors"
    ) as actors:
        with pytest.raises(ValueError, match="valid UUIDs"):
            state.generate_state_of_kokonut(conn, location_id)

    assert conn.cursor_calls == 0
    locations.assert_not_called()
    actors.assert_not_called()


def test_state_of_kokonut_normalizes_valid_selected_locations():
    conn = _Connection()
    with patch.object(state, "_state_of_kokonut_locations", return_value=([], [])) as locations, patch.object(
        state, "_state_of_kokonut_actors", return_value={}
    ):
        report = state.generate_state_of_kokonut(conn, f" {LOCATION_A.upper()} , {LOCATION_B} ")

    assert report["scope"] == "selected_locations"
    assert report["selected_location_ids"] == [LOCATION_A, LOCATION_B]
    locations.assert_called_once_with(conn, [LOCATION_A, LOCATION_B], None, None)


@pytest.mark.parametrize("location_id", ["bad", f"{LOCATION_A},bad", "", "   "])
def test_comprehensive_status_rejects_invalid_selection_before_helper(location_id):
    conn = _Connection()
    with patch.object(state, "_state_of_kokonut_locations") as locations:
        with pytest.raises(ValueError, match="valid UUIDs"):
            state.generate_comprehensive_status(conn, location_id)

    assert conn.cursor_calls == 0
    locations.assert_not_called()


@pytest.mark.parametrize("scope", [None, "all"])
def test_comprehensive_status_preserves_network_scope(scope):
    conn = _Connection()
    with patch.object(state, "_state_of_kokonut_locations", return_value=([], [])) as locations:
        report = state.generate_comprehensive_status(conn, scope)

    assert report["scope"] == "all_locations"
    locations.assert_called_once_with(conn, None, None, None)


@pytest.mark.parametrize("location_id", ["bad", f"{LOCATION_A},bad", "", "  "])
def test_state_graphs_reject_invalid_scope_before_builder(location_id):
    conn = _Connection()
    with patch.object(state, "build_all") as build:
        with pytest.raises(ValueError, match="valid UUIDs"):
            state.generate_state_of_kokonut_graphs(conn, location_id)

    assert conn.cursor_calls == 0
    build.assert_not_called()


@pytest.mark.parametrize("scope, expected", [(None, None), ("all", "all")])
def test_state_graphs_preserve_network_modes(scope, expected):
    conn = _Connection()
    with patch.object(state, "build_all", return_value=[]) as build:
        report = state.generate_state_of_kokonut_graphs(conn, scope)

    assert report["scope"] == "all_locations"
    assert report["selected_location_ids"] is None
    assert build.call_args.kwargs["location_id"] == expected


def test_state_graphs_pass_normalized_selected_locations_to_builder():
    conn = _Connection()
    with patch.object(state, "build_all", return_value=[]) as build:
        report = state.generate_state_of_kokonut_graphs(conn, f"{LOCATION_A.upper()}, {LOCATION_B}")

    normalized = f"{LOCATION_A},{LOCATION_B}"
    assert report["scope"] == "selected_locations"
    assert report["selected_location_ids"] == normalized
    assert build.call_args.kwargs["location_id"] == normalized


@pytest.mark.parametrize("location_id", ["bad", f"{LOCATION_A},bad", "", "  "])
def test_strategic_reserve_rejects_invalid_scope_before_cursor_or_health(location_id):
    conn = _Connection()
    with patch.object(reserve_health, "reserve_health") as health:
        with pytest.raises(ValueError, match="valid UUIDs"):
            state.generate_strategic_reserve(conn, location_id)

    assert conn.cursor_calls == 0
    health.assert_not_called()


@pytest.mark.parametrize("scope", [None, "all"])
def test_strategic_reserve_preserves_network_modes(scope):
    conn = _Connection()
    with patch.object(
        reserve_health,
        "reserve_health",
        return_value={"reserves": [], "reserve_count": 0, "generated_at": "now"},
    ) as health:
        report = state.generate_strategic_reserve(conn, scope)

    assert report["scope"] == "all_locations"
    health.assert_called_once_with(conn)
    assert conn.cursor_calls == 1


def test_strategic_reserve_normalizes_valid_selected_locations():
    conn = _Connection(rows=[{"id": LOCATION_A, "name": "Adelphi"}])
    with patch.object(reserve_health, "reserve_health") as health, patch.object(
        reserve_health, "seed_vault_health", return_value={}
    ):
        report = state.generate_strategic_reserve(conn, LOCATION_A.upper())

    assert report["scope"] == "selected_locations"
    assert report["selected_location_ids"] == [LOCATION_A]
    health.assert_not_called()
    assert conn.cursor_calls == 1
