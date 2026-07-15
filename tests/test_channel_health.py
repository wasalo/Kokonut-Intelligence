"""Tests for the Channel Orchestration + Customer Health service."""

import json
import uuid

import pytest
import psycopg2

from services.ingestion.base import get_db
from services.analytics import channel_orchestration


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
    assert hasattr(channel_orchestration, "create_channel_config")
    assert hasattr(channel_orchestration, "list_channel_configs")
    assert hasattr(channel_orchestration, "set_channel_preference")
    assert hasattr(channel_orchestration, "get_delivery_plan")
    assert hasattr(channel_orchestration, "create_fallback_rule")
    assert hasattr(channel_orchestration, "log_interaction")
    assert hasattr(channel_orchestration, "list_interactions")
    assert hasattr(channel_orchestration, "compute_health_score")
    assert hasattr(channel_orchestration, "list_health_scores")


def test_create_channel_config():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = channel_orchestration.create_channel_config(
            conn, loc, "SMS Gateway", "sms",
            config={"provider": "africastalking", "api_key": "xxx"},
        )
        assert created["channel_name"] == "SMS Gateway"
        assert created["channel_type"] == "sms"
        configs = channel_orchestration.list_channel_configs(conn, loc)
        assert any(str(r["id"]) == str(created["id"]) for r in configs)
    except psycopg2.ProgrammingError:
        pytest.skip("channel_config table not present (migration not applied)")
    finally:
        conn.close()


def test_set_preference_and_delivery_plan():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        channel_orchestration.create_channel_config(conn, loc, "SMS", "sms")
        channel_orchestration.create_channel_config(conn, loc, "WhatsApp", "whatsapp")
        channel_orchestration.set_channel_preference(
            conn, loc, "farmer", "sms", priority=10, is_primary=True,
        )
        channel_orchestration.set_channel_preference(
            conn, loc, "farmer", "whatsapp", priority=5,
        )
        plan = channel_orchestration.get_delivery_plan(conn, loc, "farmer")
        assert len(plan) >= 2
        # SMS should be first (higher priority)
        assert plan[0]["channel"] == "sms"
        assert plan[0]["is_primary"] is True
    except psycopg2.ProgrammingError:
        pytest.skip("channel_config table not present (migration not applied)")
    finally:
        conn.close()


def test_create_fallback_rule():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = channel_orchestration.create_fallback_rule(
            conn, loc, "SMS to WhatsApp", "sms", ["whatsapp", "voice_call"],
            trigger_condition="delivery_failed", timeout_hours=12,
        )
        assert created["primary_channel"] == "sms"
        assert created["fallback_channels"] == ["whatsapp", "voice_call"]
    except psycopg2.ProgrammingError:
        pytest.skip("channel_fallback_rule table not present (migration not applied)")
    finally:
        conn.close()


def test_log_and_list_interactions():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        farmer_id = str(uuid.uuid4())
        created = channel_orchestration.log_interaction(
            conn, loc, "farmer", farmer_id, "message_sent",
            channel_type="sms", subject="Weather alert",
            sentiment="positive",
        )
        assert created["interaction_type"] == "message_sent"
        assert created["sentiment"] == "positive"
        interactions = channel_orchestration.list_interactions(
            conn, loc, customer_type="farmer",
        )
        assert len(interactions) >= 1
    except psycopg2.ProgrammingError:
        pytest.skip("customer_interaction table not present (migration not applied)")
    finally:
        conn.close()


def test_compute_health_score():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        farmer_id = str(uuid.uuid4())
        # Log some interactions
        for _ in range(5):
            channel_orchestration.log_interaction(
                conn, loc, "farmer", farmer_id, "message_sent",
                sentiment="positive",
            )
        health = channel_orchestration.compute_health_score(
            conn, loc, "farmer", farmer_id,
        )
        assert 0 <= health["health_score"] <= 100
        assert "engagement_score" in health
        assert "breakdown" in health
    except psycopg2.ProgrammingError:
        pytest.skip("customer_health_score table not present (migration not applied)")
    finally:
        conn.close()


def test_list_health_scores():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        farmer_id = str(uuid.uuid4())
        channel_orchestration.compute_health_score(conn, loc, "farmer", farmer_id)
        scores = channel_orchestration.list_health_scores(conn, loc)
        assert isinstance(scores, list)
    except psycopg2.ProgrammingError:
        pytest.skip("customer_health_score table not present (migration not applied)")
    finally:
        conn.close()


def test_delivery_plan_no_preferences():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        channel_orchestration.create_channel_config(conn, loc, "Email", "email")
        plan = channel_orchestration.get_delivery_plan(conn, loc, "all")
        # Should return all active channels as defaults
        assert len(plan) >= 1
    except psycopg2.ProgrammingError:
        pytest.skip("channel_config table not present (migration not applied)")
    finally:
        conn.close()
