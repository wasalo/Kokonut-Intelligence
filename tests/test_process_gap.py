"""Tests for process gap analysis and maturity assessment.

Covers target CRUD, gap computation, maturity auto-assessment,
maturity trend tracking, improvement initiatives, and Cp/Cpk computation.
"""

import uuid

import pytest

from services.analytics.process_gap import (
    assess_process,
    assess_all_processes,
    get_maturity_level,
    assess_maturity,
    process_improvement_initiatives,
    process_maturity_trend,
)
from services.systems.process_control import compute_cp_cpk, ctq_capability


def _db():
    try:
        from services.ingestion.base import get_db
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'process_target'"
            )
            if cur.fetchone():
                return conn
        conn.close()
    except Exception:
        pass
    return None


# --- Cp/Cpk Pure Logic Tests (no DB required) ---

class TestCpCpk:
    def test_compute_cp_cpk_perfect(self):
        values = [10.0, 10.0, 10.0, 10.0, 10.0]
        result = compute_cp_cpk(values, usl=12.0, lsl=8.0)
        assert result["cp"] == float("inf")
        assert result["cpk"] == float("inf")
        assert result["rating"] == "perfect"
        assert result["capable"] is True

    def test_compute_cp_cpk_capable(self):
        values = [10.0, 10.1, 9.9, 10.2, 9.8, 10.0, 10.1, 9.9]
        result = compute_cp_cpk(values, usl=12.0, lsl=8.0)
        assert result["cp"] is not None
        assert result["cpk"] is not None
        assert result["cpk"] >= 1.33
        assert result["capable"] is True
        assert result["rating"] in ("capable", "highly_capable")

    def test_compute_cp_cpk_not_capable(self):
        values = [10.0, 10.5, 9.5, 11.0, 9.0, 10.5, 9.5, 11.5, 8.5]
        result = compute_cp_cpk(values, usl=11.0, lsl=9.0)
        assert result["cpk"] < 1.0
        assert result["capable"] is False
        assert result["rating"] == "not_capable"

    def test_compute_cp_cpk_marginal(self):
        values = [10.0, 10.6, 9.4, 10.3, 9.7, 10.0, 10.5, 9.5, 10.8, 9.2]
        result = compute_cp_cpk(values, usl=12.0, lsl=8.0)
        assert 1.0 <= result["cpk"] < 1.33
        assert result["rating"] == "marginal"

    def test_compute_cp_cpk_insufficient_data(self):
        result = compute_cp_cpk([], usl=12.0, lsl=8.0)
        assert result["rating"] == "insufficient_data"
        assert result["cpk"] is None

    def test_compute_cp_cpk_invalid_spec_limits(self):
        result = compute_cp_cpk([10.0, 10.1], usl=8.0, lsl=12.0)
        assert result["rating"] == "insufficient_data"

    def test_compute_cp_cpk_symmetric(self):
        values = [5.0, 5.1, 4.9, 5.0, 5.2, 4.8]
        result = compute_cp_cpk(values, usl=6.0, lsl=4.0)
        assert result["cp"] is not None
        # For symmetric distribution centered on target, cp == cpk
        assert abs(result["cp"] - result["cpk"]) < 0.1


# --- DB-Dependent Tests ---

class TestTargetCRUD:
    def test_targets_seeded(self):
        conn = _db()
        if not conn:
            pytest.skip("process_target table not available")
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM process_target")
            count = cur.fetchone()[0]
            assert count >= 20
        finally:
            conn.close()

    def test_assess_process_returns_structure(self):
        conn = _db()
        if not conn:
            pytest.skip("process_target table not available")
        try:
            result = assess_process(conn, "farm_operations")
            assert "process_key" in result
            assert "targets" in result
            assert "gaps" in result
            assert "maturity" in result
            assert "capabilities" in result
            assert result["process_key"] == "farm_operations"
        finally:
            conn.close()


class TestMaturityAssessment:
    def test_assess_maturity_returns_level(self):
        conn = _db()
        if not conn:
            pytest.skip("process_target table not available")
        try:
            result = assess_maturity(conn, "farm_operations")
            assert "level" in result
            assert "level_name" in result
            assert 1 <= result["level"] <= 5
            assert result["level_name"] in (
                "Initial", "Managed", "Defined",
                "Quantitatively Managed", "Optimizing",
            )
        finally:
            conn.close()

    def test_get_maturity_level(self):
        conn = _db()
        if not conn:
            pytest.skip("process_maturity table not available")
        try:
            assess_maturity(conn, "farm_operations")
            mat = get_maturity_level(conn, "farm_operations")
            assert mat is not None
            assert mat["process_key"] == "farm_operations"
            assert 1 <= mat["maturity_level"] <= 5
        finally:
            conn.close()

    def test_maturity_trend_returns_list(self):
        conn = _db()
        if not conn:
            pytest.skip("process_maturity table not available")
        try:
            trend = process_maturity_trend(conn, "farm_operations")
            assert isinstance(trend, list)
        finally:
            conn.close()


class TestImprovementInitiatives:
    def test_improvement_initiatives_returns_list(self):
        conn = _db()
        if not conn:
            pytest.skip("process_target table not available")
        try:
            initiatives = process_improvement_initiatives(conn, "farm_operations")
            assert isinstance(initiatives, list)
            for init in initiatives:
                assert "priority" in init
                assert "action" in init
                assert "description" in init
                assert "target_level" in init
        finally:
            conn.close()

    def test_initiatives_sorted_by_priority(self):
        conn = _db()
        if not conn:
            pytest.skip("process_target table not available")
        try:
            initiatives = process_improvement_initiatives(conn, "farm_operations")
            priorities = [i["priority"] for i in initiatives]
            priority_order = {"high": 0, "medium": 1, "low": 2}
            sorted_priorities = sorted(priorities, key=lambda p: priority_order.get(p, 3))
            assert priorities == sorted_priorities
        finally:
            conn.close()


class TestAssessAllProcesses:
    def test_assess_all_returns_list(self):
        conn = _db()
        if not conn:
            pytest.skip("process_target table not available")
        try:
            results = assess_all_processes(conn)
            assert isinstance(results, list)
            assert len(results) >= 5
            for r in results:
                assert "process_key" in r
                assert "maturity" in r
        finally:
            conn.close()


class TestProcessControlImports:
    def test_compute_cp_cpk_callable(self):
        assert callable(compute_cp_cpk)

    def test_ctq_capability_callable(self):
        assert callable(ctq_capability)

    def test_process_gap_imports(self):
        from services.analytics.process_gap import (
            assess_process, assess_all_processes, get_maturity_level,
            assess_maturity, process_improvement_initiatives,
            process_maturity_trend,
        )
        assert callable(assess_process)
        assert callable(assess_all_processes)
        assert callable(get_maturity_level)
        assert callable(assess_maturity)
        assert callable(process_improvement_initiatives)
        assert callable(process_maturity_trend)
