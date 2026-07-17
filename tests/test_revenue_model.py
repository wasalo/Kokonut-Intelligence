"""Tests for the Revenue Model + Cost Structure service."""

import json

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import revenue_model


def _db():
    try:
        return get_db()
    except psycopg2.OperationalError as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def _location(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    return str(row[0]) if row else None


def test_module_shape():
    assert hasattr(revenue_model, "create_revenue_stream")
    assert hasattr(revenue_model, "list_revenue_streams")
    assert hasattr(revenue_model, "create_pricing_model")
    assert hasattr(revenue_model, "list_pricing_models")
    assert hasattr(revenue_model, "create_cost_structure")
    assert hasattr(revenue_model, "list_cost_structures")
    assert hasattr(revenue_model, "create_break_even")
    assert hasattr(revenue_model, "list_break_even_analyses")
    assert hasattr(revenue_model, "compute_sensitivity")
    assert hasattr(revenue_model, "revenue_forecast")


def test_create_and_list_revenue_stream():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = revenue_model.create_revenue_stream(
            conn, loc, "Maize Sales", "one_time",
            product_service="Maize", estimated_annual_usd=5000,
        )
        assert created["stream_name"] == "Maize Sales"
        assert created["stream_type"] == "one_time"
        assert created["is_active"] is True
        streams = revenue_model.list_revenue_streams(conn, loc)
        assert any(str(r["id"]) == str(created["id"]) for r in streams)
    finally:
        conn.close()


def test_create_and_list_pricing():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = revenue_model.create_pricing_model(
            conn, loc, "Maize per kg", "per_kg", 0.50,
            unit="kg", volume_discount_pct=10,
        )
        assert created["product_name"] == "Maize per kg"
        assert created["base_price"] == 0.50
        models = revenue_model.list_pricing_models(conn, loc)
        assert any(str(r["id"]) == str(created["id"]) for r in models)
    finally:
        conn.close()


def test_create_and_list_cost_structure():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = revenue_model.create_cost_structure(
            conn, loc, "Labor", "fixed", 1200,
            description="Monthly farm worker wages",
        )
        assert created["cost_category"] == "Labor"
        assert created["cost_type"] == "fixed"
        costs = revenue_model.list_cost_structures(conn, loc)
        assert any(str(r["id"]) == str(created["id"]) for r in costs)
    finally:
        conn.close()


def test_create_cost_driver():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = revenue_model.create_cost_driver(
            conn, loc, "Fuel Price", "input_price", sensitivity_pct=15,
            description="Diesel price affects transport costs",
        )
        assert created["driver_name"] == "Fuel Price"
        assert created["sensitivity_pct"] == 15
    finally:
        conn.close()


def test_break_even_analysis():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        result = revenue_model.create_break_even(
            conn, loc, total_fixed_costs=10000,
            variable_cost_per_unit=2.0, price_per_unit=5.0,
            analysis_name="Maize Break-Even",
        )
        assert float(result["break_even_units"]) == 3333.33
        assert float(result["break_even_revenue"]) == 16666.67
        assert float(result["contribution_margin"]) == 60.0
    finally:
        conn.close()


def test_break_even_invalid_price():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        with pytest.raises(ValueError, match="price_per_unit must be > 0"):
            revenue_model.create_break_even(conn, loc, 10000, 2.0, 0)
    finally:
        conn.close()


def test_break_even_negative_margin():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        with pytest.raises(ValueError, match="positive contribution margin"):
            revenue_model.create_break_even(conn, loc, 10000, 5.0, 3.0)
    finally:
        conn.close()


def test_sensitivity_analysis():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        be = revenue_model.create_break_even(conn, loc, 10000, 2.0, 5.0)
        result = revenue_model.compute_sensitivity(conn, str(be["id"]))
        assert "scenarios" in result
        assert result["count"] == 25  # 5 price × 5 cost
        # Verify scenario structure
        s = result["scenarios"][0]
        assert "price_change_pct" in s
        assert "break_even_units" in s
    finally:
        conn.close()


def test_revenue_forecast():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        revenue_model.create_revenue_stream(
            conn, loc, "Crop Sales", "one_time", estimated_annual_usd=12000,
        )
        forecast = revenue_model.revenue_forecast(conn, loc, periods=6)
        assert forecast["periods"] == 6
        assert len(forecast["monthly_projections"]) == 6
        assert forecast["total_forecast"] > 0
    finally:
        conn.close()
