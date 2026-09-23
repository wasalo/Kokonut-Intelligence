"""Tests for process simulation and what-if analysis.

Covers simulation creation, execution, bottleneck relief,
automation impact, and CLI functionality.
"""

import uuid

import pytest

from services.analytics.process_simulation import (
    create_simulation,
    get_simulation_results,
    list_simulations,
    run_simulation,
    simulate_automation_impact,
    simulate_bottleneck_relief,
)


def _db():
    try:
        from services.ingestion.base import get_db
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'process_simulation'"
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
        assert callable(create_simulation)
        assert callable(run_simulation)
        assert callable(list_simulations)
        assert callable(get_simulation_results)
        assert callable(simulate_bottleneck_relief)
        assert callable(simulate_automation_impact)


# --- Regression Tests (no DB required) ---

class _InsertCursor:
    def __init__(self):
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, _sql, params):
        self.params = params

    def fetchone(self):
        return {"name": self.params[0], "created_by": self.params[4]}


class _InsertConn:
    def __init__(self):
        self.cursor_ = _InsertCursor()
        self.committed = False

    def cursor(self, **_kwargs):
        return self.cursor_

    def commit(self):
        self.committed = True


def test_create_simulation_accepts_valid_creator_uuid():
    creator_id = str(uuid.uuid4())
    conn = _InsertConn()

    result = create_simulation(
        conn,
        name="UUID creator regression",
        scenario_params={},
        created_by=creator_id,
    )

    assert result["created_by"] == creator_id
    assert conn.cursor_.params[4] == creator_id
    assert conn.committed


# --- DB-Dependent Tests ---

class TestSimulationLifecycle:
    def test_create_and_list_simulation(self):
        conn = _db()
        if not conn:
            pytest.skip("process_simulation table not available")
        try:
            sim = create_simulation(
                conn,
                name="Test Lead Time Reduction",
                scenario_params={"lead_time_reduction_pct": 20},
                description="Simulate 20% lead time reduction",
                process_key="farm_operations",
                created_by=None,
            )
            assert sim["name"] == "Test Lead Time Reduction"
            assert sim["status"] == "draft"
            assert sim["process_key"] == "farm_operations"

            sims = list_simulations(conn, process_key="farm_operations")
            assert len(sims) >= 1
            assert any(s["name"] == "Test Lead Time Reduction" for s in sims)
        finally:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM process_simulation WHERE name = %s",
                    ("Test Lead Time Reduction",),
                )
            conn.commit()
            conn.close()

    def test_run_simulation(self):
        conn = _db()
        if not conn:
            pytest.skip("process_simulation table not available")
        try:
            sim = create_simulation(
                conn,
                name="Run Test Simulation",
                scenario_params={
                    "lead_time_reduction_pct": 10,
                    "fty_improvement_pct": 5,
                },
                process_key="farm_operations",
            )
            result = run_simulation(conn, sim["id"])
            assert result["status"] == "completed"
            assert "results" in result
            assert "baseline" in result
            assert "simulated_maturity" in result
        finally:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM process_simulation WHERE name = %s",
                    ("Run Test Simulation",),
                )
            conn.commit()
            conn.close()

    def test_get_simulation_results(self):
        conn = _db()
        if not conn:
            pytest.skip("process_simulation table not available")
        try:
            sim = create_simulation(
                conn,
                name="Get Results Test",
                scenario_params={"lead_time_reduction_pct": 15},
                process_key="farm_operations",
            )
            run_simulation(conn, sim["id"])
            results = get_simulation_results(conn, sim["id"])
            assert "simulation" in results
            assert "metric_results" in results
        finally:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM process_simulation WHERE name = %s",
                    ("Get Results Test",),
                )
            conn.commit()
            conn.close()


class TestBottleneckRelief:
    def test_bottleneck_relief_structure(self):
        conn = _db()
        if not conn:
            pytest.skip("process_simulation table not available")
        try:
            result = simulate_bottleneck_relief(conn, "farm_activity", 30.0)
            assert "entity_type" in result
            # Either bottleneck found (has relief_pct) or no bottleneck (has error)
            assert "relief_pct" in result or "error" in result
        finally:
            conn.close()

    def test_bottleneck_relief_invalid_entity(self):
        conn = _db()
        if not conn:
            pytest.skip("process_simulation table not available")
        try:
            result = simulate_bottleneck_relief(conn, "nonexistent_entity", 50.0)
            assert "error" in result or "bottleneck_stage" in result
        finally:
            conn.close()


class TestAutomationImpact:
    def test_automation_impact_structure(self):
        conn = _db()
        if not conn:
            pytest.skip("process_simulation table not available")
        try:
            result = simulate_automation_impact(conn, "farm_operations", 20.0)
            assert "process_key" in result
            assert "automation_pct" in result
            assert result["automation_pct"] == 20.0
            assert "estimated_cost_savings" in result
            assert "estimated_speed_improvement_pct" in result
        finally:
            conn.close()

    def test_automation_impact_zero_pct(self):
        conn = _db()
        if not conn:
            pytest.skip("process_simulation table not available")
        try:
            result = simulate_automation_impact(conn, "farm_operations", 0.0)
            assert result["automation_pct"] == 0.0
            assert result["estimated_cost_savings"] == 0.0
            assert result["estimated_speed_improvement_pct"] == 0.0
        finally:
            conn.close()
