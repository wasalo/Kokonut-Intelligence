"""Tests for cross-entity process interfaces.

Covers handoff registration, handoff logging with elapsed time,
SLA compliance calculation, cross-entity trace reconstruction,
and cross-entity process mining (variant discovery, conformance).
"""

import uuid

import pytest

from services.analytics.process_interfaces import (
    register_handoff,
    record_handoff,
    handoff_lead_times,
    handoff_sla_compliance,
    build_process_trace,
    add_trace_step,
    cross_entity_cycle_times,
)


def _db():
    try:
        from services.ingestion.base import get_db
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'process_handoff'"
            )
            if cur.fetchone():
                return conn
        conn.close()
    except Exception:
        pass
    return None


def _purge(conn, source_type, source_id):
    """Cleanup test data."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM process_handoff_log WHERE source_entity_id = %s::uuid",
            (str(source_id),),
        )
        cur.execute(
            "DELETE FROM process_trace WHERE entity_id = %s::uuid",
            (str(source_id),),
        )
    conn.commit()


# --- Handoff Registration Tests ---

class TestHandoffRegistration:
    def test_register_handoff(self):
        conn = _db()
        if not conn:
            pytest.skip("process_handoff table not available")
        try:
            result = register_handoff(
                conn, "test_source_a", "test_target_b", "sequential",
                correlation_key="location_id", sla_hours=24.0,
                description="Test handoff",
            )
            assert result["source_entity_type"] == "test_source_a"
            assert result["target_entity_type"] == "test_target_b"
            assert result["handoff_type"] == "sequential"
            assert result["sla_hours"] == 24.0
        finally:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM process_handoff "
                    "WHERE source_entity_type = 'test_source_a'"
                )
            conn.commit()
            conn.close()

    def test_register_handoff_idempotent(self):
        conn = _db()
        if not conn:
            pytest.skip("process_handoff table not available")
        try:
            r1 = register_handoff(
                conn, "test_src_c", "test_tgt_d", "event_driven",
                sla_hours=48.0, description="First",
            )
            r2 = register_handoff(
                conn, "test_src_c", "test_tgt_d", "sequential",
                sla_hours=12.0, description="Updated",
            )
            assert r2["handoff_type"] == "sequential"
            assert r2["sla_hours"] == 12.0
        finally:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM process_handoff "
                    "WHERE source_entity_type = 'test_src_c'"
                )
            conn.commit()
            conn.close()


# --- Handoff Logging Tests ---

class TestHandoffLogging:
    def test_record_handoff(self):
        conn = _db()
        if not conn:
            pytest.skip("process_handoff table not available")
        source_id = uuid.uuid4()
        try:
            result = record_handoff(
                conn, "farm_activity", source_id,
                "harvest_event", None,
            )
            assert result["source_entity_type"] == "farm_activity"
            assert str(result["source_entity_id"]) == str(source_id)
            assert result["status"] == "delivered"
        finally:
            _purge(conn, "farm_activity", source_id)
            conn.close()


# --- SLA Compliance Tests ---

class TestSLACompliance:
    def test_handoff_lead_times_returns_list(self):
        conn = _db()
        if not conn:
            pytest.skip("process_handoff table not available")
        try:
            result = handoff_lead_times(conn)
            assert isinstance(result, list)
        finally:
            conn.close()

    def test_handoff_sla_compliance_structure(self):
        conn = _db()
        if not conn:
            pytest.skip("process_handoff table not available")
        try:
            result = handoff_sla_compliance(conn)
            assert "pairs" in result
            assert "overall" in result
            assert isinstance(result["pairs"], list)
            overall = result["overall"]
            assert "total" in overall
            assert "met" in overall
            assert "compliance_pct" in overall
        finally:
            conn.close()


# --- Cross-Entity Trace Tests ---

class TestCrossEntityTraces:
    def test_build_and_add_trace_step(self):
        conn = _db()
        if not conn:
            pytest.skip("process_trace table not available")
        trace_key = f"test_trace_{uuid.uuid4().hex[:8]}"
        try:
            from datetime import datetime, timezone
            t1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
            t2 = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)

            step1 = add_trace_step(
                conn, trace_key, "farm_activity",
                uuid.uuid4(), 1, entered_at=t1, exited_at=t2,
            )
            assert step1["step_order"] == 1
            assert step1["duration_hours"] == 24.0

            step2 = add_trace_step(
                conn, trace_key, "harvest_event",
                uuid.uuid4(), 2, entered_at=t2, exited_at=t2,
            )
            assert step2["step_order"] == 2

            trace = build_process_trace(conn, trace_key)
            assert len(trace) == 2
            assert trace[0]["step_order"] < trace[1]["step_order"]
        finally:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM process_trace WHERE trace_key = %s",
                    (trace_key,),
                )
            conn.commit()
            conn.close()


# --- Cross-Entity Cycle Times Tests ---

class TestCrossEntityCycleTimes:
    def test_cross_entity_cycle_times_structure(self):
        conn = _db()
        if not conn:
            pytest.skip("process_trace table not available")
        try:
            result = cross_entity_cycle_times(conn)
            assert "traces" in result
            assert "count" in result
            assert isinstance(result["traces"], list)
        finally:
            conn.close()


# --- Process Mining Cross-Entity Tests ---

class TestCrossEntityMining:
    def test_cross_entity_traces_returns_list(self):
        conn = _db()
        if not conn:
            pytest.skip("process_handoff_log table not available")
        try:
            from services.analytics.process_mining import cross_entity_traces
            result = cross_entity_traces(conn)
            assert isinstance(result, list)
        finally:
            conn.close()

    def test_cross_entity_variants_returns_list(self):
        conn = _db()
        if not conn:
            pytest.skip("process_handoff_log table not available")
        try:
            from services.analytics.process_mining import cross_entity_variants
            result = cross_entity_variants(conn)
            assert isinstance(result, list)
            for v in result:
                assert "variant_signature" in v
                assert "instance_count" in v
        finally:
            conn.close()

    def test_cross_entity_conformance_returns_list(self):
        conn = _db()
        if not conn:
            pytest.skip("process_handoff_log table not available")
        try:
            from services.analytics.process_mining import cross_entity_conformance
            result = cross_entity_conformance(conn)
            assert isinstance(result, list)
        finally:
            conn.close()


# --- Pure Logic Tests (no DB required) ---

class TestProcessInterfaceImports:
    def test_process_interfaces_module_imports(self):
        import services.analytics.process_interfaces as pi
        assert callable(pi.register_handoff)
        assert callable(pi.record_handoff)
        assert callable(pi.handoff_lead_times)
        assert callable(pi.handoff_sla_compliance)
        assert callable(pi.build_process_trace)
        assert callable(pi.cross_entity_cycle_times)

    def test_process_mining_cross_entity_imports(self):
        from services.analytics.process_mining import (
            cross_entity_traces,
            cross_entity_variants,
            cross_entity_conformance,
        )
        assert callable(cross_entity_traces)
        assert callable(cross_entity_variants)
        assert callable(cross_entity_conformance)
