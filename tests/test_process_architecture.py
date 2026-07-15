"""Tests for process architecture service layer.

Covers process_map CRUD, process_ownership RACI assignments,
process_entity_mapping queries, and process hierarchy.
Integration DB tests skip when process_map table is not available.
"""

import uuid

import pytest

from services.analytics.process_architecture import (
    list_processes, get_process, create_process, update_process, delete_process,
    list_ownership, assign_ownership, remove_ownership,
    list_entity_mappings, get_entity_mapping, create_entity_mapping,
    delete_entity_mapping, get_process_hierarchy, get_process_with_children,
)


def _db_available():
    """Check if the database is reachable and has the process_map table."""
    try:
        from services.analytics.process_architecture import _conn
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'process_map'"
                )
                return cur.fetchone() is not None
    except Exception:
        return False


_db_skip = pytest.mark.skipif(not _db_available(), reason="process_map table not available")


# --- Process Map Tests ---

@_db_skip
class TestProcessMapCRUD:
    def test_list_processes_returns_seeded_data(self):
        procs = list_processes()
        assert len(procs) >= 27
        keys = {p["process_key"] for p in procs}
        assert "work_management" in keys
        assert "farm_operations" in keys
        assert "event_delivery" in keys
        assert "traceability" in keys
        assert "digital_finance" in keys
        assert "pest_management" in keys
        assert "emergency_response" in keys
        assert "cooperative_management" in keys
        assert "extension_training" in keys

    def test_list_processes_filter_by_type(self):
        mgmt = list_processes(process_type="management")
        assert all(p["process_type"] == "management" for p in mgmt)
        core = list_processes(process_type="core")
        assert all(p["process_type"] == "core" for p in core)
        support = list_processes(process_type="support")
        assert all(p["process_type"] == "support" for p in support)

    def test_get_process_existing(self):
        proc = get_process("farm_operations")
        assert proc is not None
        assert proc["name"] == "Farm Operations"
        assert proc["process_type"] == "core"

    def test_get_process_nonexistent(self):
        assert get_process("nonexistent_process_xyz") is None

    def test_create_and_delete_process(self):
        key = f"test_process_{uuid.uuid4().hex[:8]}"
        created = create_process(
            process_key=key, name="Test Process", process_type="support",
            description="Test description",
        )
        assert created["process_key"] == key
        assert created["name"] == "Test Process"

        fetched = get_process(key)
        assert fetched is not None
        assert fetched["description"] == "Test description"

        assert delete_process(key)
        assert get_process(key) is None

    def test_update_process(self):
        key = f"test_update_{uuid.uuid4().hex[:8]}"
        create_process(process_key=key, name="Original", process_type="core")
        updated = update_process(key, name="Updated Name", description="New desc")
        assert updated["name"] == "Updated Name"
        assert updated["description"] == "New desc"
        delete_process(key)


# --- Process Ownership Tests ---

@_db_skip
class TestProcessOwnership:
    def test_assign_and_list_ownership(self):
        party_id = str(uuid.uuid4())
        assign_ownership(
            process_key="farm_operations", party_type="staff",
            party_id=party_id, raci_role="responsible",
        )
        ownership = list_ownership(process_key="farm_operations")
        matching = [o for o in ownership if o["party_id"] == party_id]
        assert len(matching) >= 1
        assert matching[0]["raci_role"] == "responsible"

        remove_ownership("farm_operations", "staff", party_id, "responsible")
        ownership_after = list_ownership(process_key="farm_operations")
        assert not any(o["party_id"] == party_id for o in ownership_after)

    def test_list_all_ownership(self):
        all_own = list_ownership()
        assert isinstance(all_own, list)


# --- Entity Mapping Tests ---

@_db_skip
class TestEntityMapping:
    def test_list_entity_mappings_returns_seeded_data(self):
        mappings = list_entity_mappings()
        assert len(mappings) >= 22
        entity_types = {m["entity_type"] for m in mappings}
        assert "farm_activity" in entity_types
        assert "harvest_event" in entity_types
        assert "data_stream_post" in entity_types
        assert "metric_value" in entity_types
        assert "traceability_batch" in entity_types
        assert "insurance_claim" in entity_types
        assert "pest_intervention" in entity_types
        assert "emergency_incident" in entity_types
        assert "cooperative_order" in entity_types
        assert "extension_enrollment" in entity_types

    def test_get_entity_mapping(self):
        m = get_entity_mapping("farm_activity")
        assert m is not None
        assert m["process_key"] == "farm_operations"
        assert m["workflow_spec_id"] == "farm_activity"

    def test_get_entity_mapping_nonexistent(self):
        assert get_entity_mapping("nonexistent_entity_xyz") is None

    def test_create_and_delete_entity_mapping(self):
        et = f"test_entity_{uuid.uuid4().hex[:8]}"
        created = create_entity_mapping(
            process_key="marketplace", entity_type=et,
            workflow_spec_id="work_item", lifecycle_model="custom",
            description="Test mapping",
        )
        assert created["entity_type"] == et

        fetched = get_entity_mapping(et)
        assert fetched is not None
        assert fetched["process_key"] == "marketplace"

        assert delete_entity_mapping(et)
        assert get_entity_mapping(et) is None


# --- Process Hierarchy Tests ---

@_db_skip
class TestProcessHierarchy:
    def test_get_process_with_children(self):
        proc = get_process_with_children("farm_operations")
        assert proc is not None
        assert "children" in proc
        assert isinstance(proc["children"], list)


# --- Workflow Spec Validation ---

class TestNewWorkflowSpecs:
    """Validate that the 8 new workflow specs are well-formed."""

    def test_all_21_specs_present(self):
        from services.workflow_specs.registry import list_specs
        specs = {s.id for s in list_specs()}
        expected = {
            "carbon_retirement", "event_bus_delivery", "work_item",
            "budget", "objective", "project",
            "data_stream_post", "ai_summary", "impact_claim",
            "report_snapshot", "stakeholder_feedback", "farm_activity",
            "harvest_event", "metric_value",
            "traceability_batch", "insurance_claim", "pest_intervention",
            "emergency_incident", "cooperative_order", "extension_enrollment",
            "market_order",
        }
        assert specs == expected

    def test_new_specs_have_invariants_and_source_refs(self):
        from services.workflow_specs.registry import list_specs
        for spec in list_specs():
            assert spec.invariants, f"{spec.id} missing invariants"
            assert spec.source_refs, f"{spec.id} missing source_refs"

    def test_5_state_specs_cover_standard_states(self):
        from services.workflow_specs.registry import list_specs
        standard_ids = {
            "data_stream_post", "ai_summary", "impact_claim",
            "report_snapshot", "stakeholder_feedback", "farm_activity",
            "harvest_event", "traceability_batch", "insurance_claim",
            "pest_intervention", "emergency_incident", "cooperative_order",
            "extension_enrollment", "market_order",
        }
        for spec in list_specs():
            if spec.id in standard_ids:
                assert spec.states == frozenset({
                    "draft", "submitted", "verified", "published", "rejected"
                }), f"{spec.id} has non-standard states"

    def test_metric_value_is_2_state(self):
        from services.workflow_specs.registry import get_spec
        spec = get_spec("metric_value")
        assert spec.states == frozenset({"draft", "verified"})

    def test_rejection_is_terminal_in_5_state_specs(self):
        from services.workflow_specs.registry import list_specs
        standard_ids = {
            "data_stream_post", "ai_summary", "impact_claim",
            "report_snapshot", "stakeholder_feedback", "farm_activity",
            "harvest_event", "traceability_batch", "insurance_claim",
            "pest_intervention", "emergency_incident", "cooperative_order",
            "extension_enrollment", "market_order",
        }
        for spec in list_specs():
            if spec.id in standard_ids:
                reject_steps = [
                    s for s in spec.steps if "reject" in s.id and s.terminal
                ]
                assert reject_steps, f"{spec.id} missing terminal reject step"
