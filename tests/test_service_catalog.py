"""Tests for service catalog (SCRM) service layer.

Covers service_registry CRUD, lifecycle, health summary, and the
21 workflow specs including the 7 new ones.
Integration DB tests skip when service_registry table is not available.
"""

import uuid

import pytest

from services.analytics.service_catalog import (
    list_services, get_service, register_service, deprecate_service,
    service_health_summary,
)


def _db_available():
    """Check if the database is reachable and has the service_registry table."""
    try:
        from services.analytics.service_catalog import _conn
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'service_registry'"
                )
                return cur.fetchone() is not None
    except Exception:
        return False


_db_skip = pytest.mark.skipif(not _db_available(), reason="service_registry table not available")


# --- DB Integration Tests ---

@_db_skip
class TestServiceRegistry:
    def test_list_services_returns_seeded_data(self):
        services = list_services()
        assert len(services) >= 57

    def test_list_services_filter_by_category(self):
        core = list_services(category="core")
        assert len(core) >= 1
        assert all(s["category"] == "core" for s in core)

    def test_get_service_existing(self):
        svc = get_service("gateway")
        assert svc is not None
        assert svc["name"] == "gateway"

    def test_get_service_nonexistent(self):
        assert get_service("nonexistent_xyz") is None

    def test_register_and_deprecate_service(self):
        name = f"test_svc_{uuid.uuid4().hex[:8]}"
        created = register_service(
            name=name, category="support", description="Test service",
        )
        assert created["name"] == name
        assert created["status"] == "active"

        deprecated = deprecate_service(name)
        assert deprecated["status"] == "deprecated"

    def test_service_health_summary(self):
        summary = service_health_summary()
        assert isinstance(summary, dict)
        assert "total" in summary
        assert "active_count" in summary
        assert "deprecated_count" in summary
        assert "retired_count" in summary
        assert "avg_sla_ms" in summary
        assert "by_category" in summary


# --- Workflow Spec Tests (no DB required) ---

class TestWorkflowSpecs:
    """Validate that the 21 workflow specs are well-formed."""

    def test_all_21_specs_present(self):
        from services.workflow_specs.registry import load_builtin_specs, list_specs
        load_builtin_specs()
        specs = {s.id for s in list_specs()}
        assert len(specs) == 21
        new_specs = {
            "traceability_batch", "insurance_claim", "pest_intervention",
            "emergency_incident", "cooperative_order", "extension_enrollment",
            "market_order",
        }
        assert new_specs.issubset(specs)

    def test_new_specs_have_valid_states(self):
        from services.workflow_specs.registry import load_builtin_specs, list_specs
        load_builtin_specs()
        new_ids = {
            "traceability_batch", "insurance_claim", "pest_intervention",
            "emergency_incident", "cooperative_order", "extension_enrollment",
            "market_order",
        }
        for spec in list_specs():
            if spec.id in new_ids:
                for state in ("draft", "submitted", "verified", "published", "rejected"):
                    assert state in spec.states, f"{spec.id} missing state {state}"

    def test_new_specs_have_human_approval_on_verify(self):
        from services.workflow_specs.registry import load_builtin_specs, list_specs
        load_builtin_specs()
        new_ids = {
            "traceability_batch", "insurance_claim", "pest_intervention",
            "emergency_incident", "cooperative_order", "extension_enrollment",
            "market_order",
        }
        for spec in list_specs():
            if spec.id in new_ids:
                verify_steps = [s for s in spec.steps if "verify" in s.id.lower()]
                assert verify_steps, f"{spec.id} missing verify step"
                for step in verify_steps:
                    assert step.human_approval, (
                        f"{spec.id} step {step.id} must have human_approval=True"
                    )

    def test_new_specs_have_entry_steps(self):
        from services.workflow_specs.registry import load_builtin_specs, list_specs
        load_builtin_specs()
        new_ids = {
            "traceability_batch", "insurance_claim", "pest_intervention",
            "emergency_incident", "cooperative_order", "extension_enrollment",
            "market_order",
        }
        for spec in list_specs():
            if spec.id in new_ids:
                entry_steps = [s for s in spec.steps if s.entry]
                assert entry_steps, f"{spec.id} has no entry step"
