"""Tests for reference-class forecasting (optimism-bias dampening)."""

from unittest.mock import MagicMock, patch

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.forecast import reference_class as rc


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def _location(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    return str(row[0]) if row else None


def test_module_shape():
    assert hasattr(rc, "apply_reference_class")


def test_apply_reference_class_keys():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        out = rc.apply_reference_class(conn, loc, "crop_noi", 0.5)
        assert set(out) >= {
            "metric", "alpha", "projected", "reference_median",
            "comparable_locations", "damped_estimate", "note",
        }
        assert out["alpha"] == 0.5
        # When both projection and reference exist, damped is a blend.
        if out["projected"] is not None and out["reference_median"] is not None:
            expected = round(0.5 * out["projected"] + 0.5 * out["reference_median"], 4)
            assert out["damped_estimate"] == expected
    except psycopg2.ProgrammingError:
        pytest.skip("forecast/noi tables not present (migration not applied)")
    finally:
        conn.close()


def test_alpha_out_of_range_rejected():
    with pytest.raises(ValueError, match="alpha must be between"):
        rc.apply_reference_class(MagicMock(), "loc-id", alpha=-0.1)
    with pytest.raises(ValueError, match="alpha must be between"):
        rc.apply_reference_class(MagicMock(), "loc-id", alpha=1.1)


def test_module_has_apply_reference_class():
    assert callable(rc.apply_reference_class)
