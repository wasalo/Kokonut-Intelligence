"""Tests for the SWOT Enhanced service — TOWS, factors, competitors, temporal."""

import json

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import swot
from services.analytics import swot_enhanced


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")


def _location(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    return str(row[0]) if row else None


def _swot_id(conn, loc):
    """Create a SWOT and return its ID."""
    created = swot.create(conn, location_id=loc)
    return str(created["id"])


def test_module_shape():
    assert hasattr(swot_enhanced, "create_factor")
    assert hasattr(swot_enhanced, "list_factors")
    assert hasattr(swot_enhanced, "generate_tows")
    assert hasattr(swot_enhanced, "get_tows")
    assert hasattr(swot_enhanced, "approve_tows")
    assert hasattr(swot_enhanced, "compute_strategic_fit")
    assert hasattr(swot_enhanced, "create_competitor")
    assert hasattr(swot_enhanced, "list_competitors")
    assert hasattr(swot_enhanced, "snapshot_temporal")
    assert hasattr(swot_enhanced, "list_temporal")
    assert hasattr(swot_enhanced, "link_action")
    assert hasattr(swot_enhanced, "list_actions")


def test_create_and_list_factors():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        swot_id = _swot_id(conn, loc)
        f1 = swot_enhanced.create_factor(
            conn, swot_id, "strength", "financial",
            "Strong revenue diversification", priority=8, confidence=0.9,
        )
        assert f1["factor_type"] == "strength"
        assert f1["classification"] == "internal"
        f2 = swot_enhanced.create_factor(
            conn, swot_id, "opportunity", "future_trends",
            "Growing carbon credit market", priority=7,
        )
        assert f2["classification"] == "external"
        factors = swot_enhanced.list_factors(conn, swot_id)
        assert len(factors) == 2
    except psycopg2.ProgrammingError:
        pytest.skip("swot_factor table not present")
    finally:
        conn.close()


def test_factor_validation():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        swot_id = _swot_id(conn, loc)
        with pytest.raises(ValueError, match="internal category"):
            swot_enhanced.create_factor(conn, swot_id, "strength", "economy", "Bad")
        with pytest.raises(ValueError, match="external category"):
            swot_enhanced.create_factor(conn, swot_id, "opportunity", "financial", "Bad")
    except psycopg2.ProgrammingError:
        pytest.skip("swot_factor table not present")
    finally:
        conn.close()


def test_generate_tows():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        swot_id = _swot_id(conn, loc)
        swot_enhanced.create_factor(conn, swot_id, "strength", "financial", "Strong cash flow")
        swot_enhanced.create_factor(conn, swot_id, "strength", "human_resources", "Expert team")
        swot_enhanced.create_factor(conn, swot_id, "opportunity", "economy", "Market expansion")
        swot_enhanced.create_factor(conn, swot_id, "threat", "legislation", "New regulations")
        result = swot_enhanced.generate_tows(conn, swot_id)
        assert result["factor_counts"]["strengths"] == 2
        assert result["factor_counts"]["opportunities"] == 1
        strategies = swot_enhanced.get_tows(conn, swot_id)
        assert len(strategies) == 4
        types = {s["strategy_type"] for s in strategies}
        assert types == {"SO", "ST", "WO", "WT"}
    except psycopg2.ProgrammingError:
        pytest.skip("swot_factor table not present")
    finally:
        conn.close()


def test_approve_tows():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        swot_id = _swot_id(conn, loc)
        swot_enhanced.create_factor(conn, swot_id, "strength", "financial", "Cash")
        swot_enhanced.create_factor(conn, swot_id, "opportunity", "economy", "Growth")
        swot_enhanced.generate_tows(conn, swot_id)
        tows = swot_enhanced.get_tows(conn, swot_id)
        so = [s for s in tows if s["strategy_type"] == "SO"][0]
        result = swot_enhanced.approve_tows(conn, so["id"], "00000000-0000-0000-0000-000000000001")
        assert result["status"] == "approved"
    except psycopg2.ProgrammingError:
        pytest.skip("swot_factor table not present")
    finally:
        conn.close()


def test_strategic_fit():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        swot_id = _swot_id(conn, loc)
        swot_enhanced.create_factor(conn, swot_id, "strength", "financial", "Revenue")
        swot_enhanced.create_factor(conn, swot_id, "strength", "human_resources", "Team")
        swot_enhanced.create_factor(conn, swot_id, "opportunity", "economy", "Market")
        swot_enhanced.create_factor(conn, swot_id, "opportunity", "funding_sources", "Investment")
        fit = swot_enhanced.compute_strategic_fit(conn, swot_id)
        assert 0 <= fit["strategic_fit_score"] <= 100
        assert fit["strength_count"] == 2
        assert fit["opportunity_count"] == 2
    except psycopg2.ProgrammingError:
        pytest.skip("swot_factor table not present")
    finally:
        conn.close()


def test_competitor_swot():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        created = swot_enhanced.create_competitor(
            conn, loc, "BigAg Corp", competitor_type="industrial",
            strengths=["Scale", "Distribution"], weaknesses=["No organic focus"],
            competitive_threat_level="high",
        )
        assert created["competitor_name"] == "BigAg Corp"
        competitors = swot_enhanced.list_competitors(conn, loc)
        assert len(competitors) >= 1
    except psycopg2.ProgrammingError:
        pytest.skip("competitor_swot table not present")
    finally:
        conn.close()


def test_temporal_snapshot():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        swot_id = _swot_id(conn, loc)
        swot_enhanced.create_factor(conn, swot_id, "strength", "financial", "Initial strength")
        snap1 = swot_enhanced.snapshot_temporal(conn, swot_id, change_summary="Initial")
        assert snap1["version"] == 1
        swot_enhanced.create_factor(conn, swot_id, "strength", "financial", "New strength")
        snap2 = swot_enhanced.snapshot_temporal(conn, swot_id, change_summary="Added strength")
        assert snap2["version"] == 2
        history = swot_enhanced.list_temporal(conn, swot_id)
        assert len(history) == 2
    except psycopg2.ProgrammingError:
        pytest.skip("swot_temporal table not present")
    finally:
        conn.close()


def test_action_linkage():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        swot_id = _swot_id(conn, loc)
        f = swot_enhanced.create_factor(conn, swot_id, "weakness", "financial", "Low cash")
        action = swot_enhanced.link_action(
            conn, swot_id, "Secure bridge financing",
            target_type="recommendation", factor_id=f["id"],
        )
        assert action["status"] == "proposed"
        actions = swot_enhanced.list_actions(conn, swot_id)
        assert len(actions) >= 1
    except psycopg2.ProgrammingError:
        pytest.skip("swot_action_link table not present")
    finally:
        conn.close()


def test_delete_factor():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        swot_id = _swot_id(conn, loc)
        f = swot_enhanced.create_factor(conn, swot_id, "strength", "financial", "Temp")
        deleted = swot_enhanced.delete_factor(conn, f["id"])
        assert deleted is True
        factors = swot_enhanced.list_factors(conn, swot_id)
        assert len(factors) == 0
    except psycopg2.ProgrammingError:
        pytest.skip("swot_factor table not present")
    finally:
        conn.close()


def test_list_factors_filtered():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location")
    try:
        swot_id = _swot_id(conn, loc)
        swot_enhanced.create_factor(conn, swot_id, "strength", "financial", "S1")
        swot_enhanced.create_factor(conn, swot_id, "weakness", "financial", "W1")
        swot_enhanced.create_factor(conn, swot_id, "opportunity", "economy", "O1")
        strengths = swot_enhanced.list_factors(conn, swot_id, factor_type="strength")
        assert len(strengths) == 1
        assert strengths[0]["factor_type"] == "strength"
        internals = swot_enhanced.list_factors(conn, swot_id, classification="internal")
        assert len(internals) == 2
    except psycopg2.ProgrammingError:
        pytest.skip("swot_factor table not present")
    finally:
        conn.close()
