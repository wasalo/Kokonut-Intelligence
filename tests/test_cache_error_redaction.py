"""Cache database failures do not log exception messages or cache keys."""

from __future__ import annotations

import logging

import pytest

from services.cache.cache import ComputationCache

SECRET_ERROR = "postgresql://operator:secret@db.internal/kokonut"
_RAISE = object()


class _DatabaseFailure(Exception):
    pass


class _FailingCursor:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        raise _DatabaseFailure(SECRET_ERROR)


class _FailingConnection:
    def __init__(self):
        self.rollbacks = 0

    def cursor(self):
        return _FailingCursor()

    def rollback(self):
        self.rollbacks += 1


@pytest.mark.parametrize(
    ("method", "args", "kwargs", "expected", "rolls_back"),
    [
        ("get", ("yield",), {"location_id": "location-secret"}, None, True),
        ("set", ("yield", {"value": 1}), {"location_id": "location-secret"}, _RAISE, True),
        ("invalidate", (), {"location_id": "location-secret"}, 0, True),
        ("cleanup_expired", (), {}, 0, True),
        ("stats", (), {}, {}, False),
    ],
)
def test_cache_database_errors_are_redacted(method, args, kwargs, expected, rolls_back, caplog):
    conn = _FailingConnection()
    cache = ComputationCache(conn=conn)

    with caplog.at_level(logging.WARNING, logger="kokonut.cache"):
        if expected is _RAISE:
            with pytest.raises(_DatabaseFailure, match="operator:secret"):
                getattr(cache, method)(*args, **kwargs)
        else:
            assert getattr(cache, method)(*args, **kwargs) == expected

    assert SECRET_ERROR not in caplog.text
    assert "location-secret" not in caplog.text
    assert "_DatabaseFailure" in caplog.text
    assert "Traceback" not in caplog.text
    assert conn.rollbacks == int(rolls_back)
