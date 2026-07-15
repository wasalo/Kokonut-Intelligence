"""Tests for process costing and benchmarking.

Covers cost recording, cost-of-quality computation, benchmark
creation and comparison, process ROI, and improvement initiative lifecycle.
"""

import uuid

import pytest

from services.analytics.process_costing import (
    record_process_cost,
    process_cost_per_instance,
    total_process_cost,
    process_cost_of_quality,
    benchmark_processes,
    compare_benchmarks,
    process_roi,
    create_improvement,
    list_improvements,
    complete_improvement,
)


def _db():
    try:
        from services.ingestion.base import get_db
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'process_cost_observation'"
            )
            if cur.fetchone():
                return conn
        conn.close()
    except Exception:
        pass
    return None


# --- Import Tests (no DB required) ---

class TestImports:
    def test_all_functions_callable(self):
        assert callable(record_process_cost)
        assert callable(process_cost_per_instance)
        assert callable(total_process_cost)
        assert callable(process_cost_of_quality)
        assert callable(benchmark_processes)
        assert callable(compare_benchmarks)
        assert callable(process_roi)
        assert callable(create_improvement)
        assert callable(list_improvements)
        assert callable(complete_improvement)


# --- DB-Dependent Tests ---

class TestCostRecording:
    def test_record_and_aggregate_cost(self):
        conn = _db()
        if not conn:
            pytest.skip("process_cost_observation table not available")
        try:
            eid = uuid.uuid4()
            r1 = record_process_cost(
                conn, "farm_activity", eid, "farm_operations",
                "labor", 2.50, "USD",
            )
            assert r1["cost_amount"] == 2.50
            assert r1["cost_type"] == "labor"

            r2 = record_process_cost(
                conn, "farm_activity", eid, "farm_operations",
                "compute", 0.01, "USD",
            )
            assert r2["cost_amount"] == 0.01

            agg = process_cost_per_instance(conn, "farm_operations")
            assert agg["total_instances"] >= 2
            assert agg["avg_cost_per_instance"] > 0
            assert agg["total_cost"] > 0
        finally:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM process_cost_observation WHERE entity_id = %s::uuid",
                    (str(eid),),
                )
            conn.commit()
            conn.close()

    def test_total_process_cost(self):
        conn = _db()
        if not conn:
            pytest.skip("process_cost_observation table not available")
        try:
            result = total_process_cost(conn, "farm_operations")
            assert "process_key" in result
            assert "by_currency" in result
            assert isinstance(result["by_currency"], list)
        finally:
            conn.close()


class TestCostOfQuality:
    def test_cost_of_quality_structure(self):
        conn = _db()
        if not conn:
            pytest.skip("process_cost_observation table not available")
        try:
            result = process_cost_of_quality(conn)
            assert "cost_of_conformance" in result
            assert "cost_of_non_conformance" in result
            assert "total_cost_of_quality" in result
        finally:
            conn.close()


class TestBenchmarks:
    def test_benchmark_processes_returns_list(self):
        conn = _db()
        if not conn:
            pytest.skip("process_cost_observation table not available")
        try:
            result = benchmark_processes(conn, str(uuid.uuid4()))
            assert isinstance(result, list)
        finally:
            conn.close()

    def test_compare_benchmarks_structure(self):
        conn = _db()
        if not conn:
            pytest.skip("process_cost_observation table not available")
        try:
            lid1 = str(uuid.uuid4())
            lid2 = str(uuid.uuid4())
            result = compare_benchmarks(conn, [lid1, lid2])
            assert "locations" in result
            assert "summary" in result
        finally:
            conn.close()


class TestProcessROI:
    def test_process_roi_structure(self):
        conn = _db()
        if not conn:
            pytest.skip("process_cost_observation table not available")
        try:
            result = process_roi(conn, "farm_operations")
            assert "process_key" in result
            assert "published_instances" in result
            assert "total_process_cost" in result
            assert "roi_pct" in result
            assert result["process_key"] == "farm_operations"
        finally:
            conn.close()


class TestImprovementLifecycle:
    def test_create_list_complete_improvement(self):
        conn = _db()
        if not conn:
            pytest.skip("process_improvement table not available")
        try:
            created = create_improvement(
                conn, "farm_operations", "Reduce data entry time",
                description="Automate field data capture via mobile",
                improvement_type="automation",
            )
            assert created["initiative_name"] == "Reduce data entry time"
            assert created["status"] == "proposed"
            assert created["improvement_type"] == "automation"

            improvements = list_improvements(conn, process_key="farm_operations")
            assert len(improvements) >= 1
            assert any(i["initiative_name"] == "Reduce data entry time" for i in improvements)

            completed = complete_improvement(
                conn, created["id"], "Reduced entry time by 40%",
            )
            assert completed["status"] == "completed"
            assert completed["actual_benefit"] == "Reduced entry time by 40%"
        finally:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM process_improvement WHERE initiative_name = %s",
                    ("Reduce data entry time",),
                )
            conn.commit()
            conn.close()

    def test_list_improvements_with_status_filter(self):
        conn = _db()
        if not conn:
            pytest.skip("process_improvement table not available")
        try:
            result = list_improvements(conn, status="proposed")
            assert isinstance(result, list)
        finally:
            conn.close()


class TestSeededCosts:
    def test_process_cost_seeded(self):
        conn = _db()
        if not conn:
            pytest.skip("process_cost table not available")
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM process_cost")
            count = cur.fetchone()[0]
            assert count >= 20
        finally:
            conn.close()
