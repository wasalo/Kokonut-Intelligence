"""Failure-path cursor cleanup for state and portfolio report queries."""

from __future__ import annotations

import pytest

from services.export.reports import core, operations, state


class _FailingCursor:
    def __init__(self, fail_on, fetchone_results=None):
        self.fail_on = fail_on
        self.calls = {"execute": 0, "fetchall": 0, "fetchone": 0}
        self.closed = False
        self.fetchone_results = iter(fetchone_results or [{"name": "Synthetic farm"}])

    def _maybe_fail(self, operation):
        self.calls[operation] += 1
        if self.fail_on == (operation, self.calls[operation]):
            raise RuntimeError("synthetic report query failure")

    def execute(self, *_args):
        self._maybe_fail("execute")

    def fetchall(self):
        self._maybe_fail("fetchall")
        return []

    def fetchone(self):
        self._maybe_fail("fetchone")
        return next(self.fetchone_results, {})

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def cursor(self, **_kwargs):
        return self.cursor_instance


_CASES = [
    *((core.generate_farm_summary, ("location-1",), ("execute", index)) for index in range(1, 10)),
    *((core.generate_farm_summary, ("location-1",), ("fetchall", index)) for index in range(1, 6)),
    *((core.generate_farm_summary, ("location-1",), ("fetchone", index)) for index in range(1, 5)),
    (state._state_of_kokonut_locations, (None, None, None), ("execute", 1)),
    (state._state_of_kokonut_locations, (None, None, None), ("fetchall", 1)),
    *((state._state_of_kokonut_actors, (None, None), ("execute", index)) for index in range(1, 5)),
    *((state._state_of_kokonut_actors, (None, None), ("fetchall", index)) for index in range(1, 5)),
    (state.generate_strategic_reserve, ("location-1",), ("execute", 1)),
    (state.generate_strategic_reserve, ("location-1",), ("fetchall", 1)),
    (state.generate_capital_provider_utility, ("location-1",), ("execute", 1)),
    (state.generate_capital_provider_utility, ("location-1",), ("fetchone", 1)),
    (state.generate_capital_provider_utility, ("location-1",), ("execute", 2)),
    (state.generate_capital_provider_utility, ("location-1",), ("fetchall", 1)),
    *((operations.generate_resource_efficiency, ("location-1",), ("execute", index)) for index in range(1, 4)),
    (operations.generate_resource_efficiency, ("location-1",), ("fetchone", 1)),
    (operations.generate_resource_efficiency, ("location-1",), ("fetchone", 2)),
    (operations.generate_resource_efficiency, ("location-1",), ("fetchall", 1)),
    *((operations.generate_training_impact, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (operations.generate_training_impact, ("location-1",), ("fetchone", 1)),
    (operations.generate_training_impact, ("location-1",), ("fetchall", 1)),
    *((operations.generate_revenue_streams, ("location-1",), ("execute", index)) for index in range(1, 3)),
    (operations.generate_revenue_streams, ("location-1",), ("fetchone", 1)),
    (operations.generate_revenue_streams, ("location-1",), ("fetchall", 1)),
    *((operations.generate_model_validation, ("location-1",), ("execute", index)) for index in range(1, 4)),
    (operations.generate_model_validation, ("location-1",), ("fetchone", 1)),
    *((operations.generate_model_validation, ("location-1",), ("fetchall", index)) for index in range(1, 3)),
]


@pytest.mark.parametrize(("generator", "args", "fail_on"), _CASES)
def test_report_cursor_closes_when_query_or_fetch_fails(generator, args, fail_on):
    cursor = _FailingCursor(fail_on)
    conn = _Connection(cursor)

    with pytest.raises(RuntimeError, match="synthetic report query failure"):
        generator(conn, *args)

    assert cursor.closed


def test_farm_summary_closes_cursor_when_location_is_missing():
    cursor = _FailingCursor(None, fetchone_results=[None])
    conn = _Connection(cursor)

    with pytest.raises(ValueError, match="Location location-1 not found"):
        core.generate_farm_summary(conn, "location-1")

    assert cursor.closed
