"""Kokonut Commons governance, redistribution, federation, and participatory signal tests."""

from pathlib import Path

import pytest

from services.agents.kokonut_commons_agent import synthesize_kokonut_commons
from services.agents.tasks import get_task, list_tasks, validate_output
from services.export.report_generator import (
    ALL_LOCATION_REPORTS,
    NETWORK_LEVEL_REPORTS,
    REPORT_GENERATORS,
    generate_algorithmic_redistribution,
    generate_anti_capture_governance,
    generate_federation_mutual_aid,
    generate_participatory_signal,
    generate_redistribution_policy,
)

SCHEMA = Path("schemas/postgres/041_kokonut_commons_governance.sql")
SEED = Path("schemas/seeds/042_kokonut_commons_governance.sql")
PILOT_SEED = Path("schemas/seeds/042_pilot_kokonut_commons_governance.sql")


def test_kokonut_commons_schema_defines_records_and_public_views() -> None:
    text = SCHEMA.read_text()
    for table in [
        "anti_capture_governance_policy",
        "commons_redistribution_policy",
        "federation_protocol",
        "algorithmic_redistribution_mechanism",
        "participatory_signal_experiment",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for view in [
        "v_public_anti_capture_governance_policy",
        "v_public_commons_redistribution_policy",
        "v_public_federation_protocol",
        "v_public_algorithmic_redistribution_mechanism",
        "v_public_participatory_signal_experiment",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text
    assert "one_person_one_vote_enabled" in text
    assert "commons_allocation_pct" in text
    assert "permissionless_forking_enabled" in text
    assert "vibes_check" in text


def test_kokonut_commons_seed_and_dashboards_exist() -> None:
    text = SEED.read_text()
    for metric in [
        "anti_capture_policy_count",
        "community_veto_enabled",
        "commons_redistribution_pct",
        "operator_or_community_allocation_pct",
        "federation_protocol_count",
        "mutual_aid_support_count",
        "redistribution_mechanism_count",
        "participatory_signal_experiment_count",
    ]:
        assert metric in text
    for sql in [
        "52_anti_capture_governance.sql",
        "53_redistribution_policy.sql",
        "54_federation_mutual_aid.sql",
        "55_algorithmic_redistribution.sql",
        "56_participatory_signal.sql",
    ]:
        assert Path("dashboards/metabase/sql").joinpath(sql).exists()
    assert "refresh_cron" in text


def test_pilot_seed_has_flexible_policy_and_excludes_unsupported_claims() -> None:
    text = PILOT_SEED.read_text()
    assert "adelphi-anti-capture-policy-2026" in text
    assert "current policy scenario" in text
    assert "scenario only, adaptable case by case" in text
    assert "51% committed allocation" in text
    assert "unsupported_claims_excluded" in text
    assert "Kokonut Venus Farm" not in text
    assert "Hypercert" not in text
    assert "Ecocertain" not in text
    assert "AMUSA allocation" in text


def test_kokonut_commons_task_catalogue_and_validation() -> None:
    assert "kokonut_commons_synthesis" in list_tasks()
    task = get_task("kokonut_commons_synthesis")
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert validate_output("kokonut_commons_synthesis", {}) == ["Missing required output field: summary"]


def test_kokonut_commons_agent_summarizes_public_safe_records() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{"policy_name": "Anti-capture", "community_veto_enabled": True}]
            if self.calls == 2:
                return [
                    {"policy_name": "Current", "policy_status": "active"},
                    {"policy_name": "Scenario", "policy_status": "proposed"},
                ]
            if self.calls == 3:
                return [{"protocol_name": "Federation", "permissionless_forking_enabled": True}]
            if self.calls == 4:
                return [{"mechanism_name": "Operator support", "implementation_status": "proposed"}]
            return [{"experiment_name": "Vibes check", "decision_binding": "advisory"}]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    summary = synthesize_kokonut_commons(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["anti_capture_policy_count"] == 1
    assert summary["redistribution_policy_count"] == 2
    assert summary["active_redistribution_policy_count"] == 1
    assert summary["proposed_redistribution_policy_count"] == 1
    assert summary["federation_protocol_count"] == 1
    assert summary["algorithmic_redistribution_count"] == 1
    assert summary["participatory_signal_count"] == 1
    assert "proposed redistribution scenarios are not commitments" in summary["safety_note"]


def test_kokonut_commons_report_generators_registered_and_public_safe() -> None:
    for report_type in [
        "anti_capture_governance",
        "redistribution_policy",
        "federation_mutual_aid",
        "algorithmic_redistribution",
        "participatory_signal",
    ]:
        assert report_type in REPORT_GENERATORS

    class Cursor:
        def execute(self, query, params=None):
            pass

        def fetchall(self):
            return [{
                "community_veto_enabled": True,
                "worker_or_operator_veto_enabled": True,
                "policy_status": "active",
                "policy_scope": "scenario",
                "permissionless_forking_enabled": True,
                "implementation_status": "proposed",
                "decision_binding": "advisory",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    conn = Conn()
    location_id = "a0000000-0000-0000-0000-000000000001"
    assert generate_anti_capture_governance(conn, location_id)["community_veto_count"] == 1
    assert generate_redistribution_policy(conn, location_id)["scenario_policy_count"] == 1
    federation = generate_federation_mutual_aid(conn)
    assert federation["permissionless_forking_count"] == 1
    assert federation["location_id"] is None
    assert generate_algorithmic_redistribution(conn, location_id)["report_type"] == "algorithmic_redistribution"
    participatory = generate_participatory_signal(conn)
    assert participatory["advisory_count"] == 1
    assert participatory["location_id"] is None


@pytest.mark.parametrize(
    "report_type,generator",
    [
        ("anti_capture_governance", generate_anti_capture_governance),
        ("redistribution_policy", generate_redistribution_policy),
        ("algorithmic_redistribution", generate_algorithmic_redistribution),
    ],
)
@pytest.mark.parametrize("location_id", [None, ""])
def test_location_required_commons_reports_reject_missing_scope_before_cursor(
    report_type, generator, location_id
) -> None:
    assert report_type in REPORT_GENERATORS
    assert report_type not in NETWORK_LEVEL_REPORTS
    assert report_type not in ALL_LOCATION_REPORTS

    class Conn:
        cursor_called = False

        def cursor(self, cursor_factory=None):
            self.cursor_called = True
            raise AssertionError("a missing location must fail before opening a cursor")

    conn = Conn()
    with pytest.raises(ValueError, match="requires an explicit location_id"):
        generator(conn, location_id)
    assert not conn.cursor_called


@pytest.mark.parametrize(
    "report_type,generator",
    [
        ("anti_capture_governance", generate_anti_capture_governance),
        ("redistribution_policy", generate_redistribution_policy),
        ("algorithmic_redistribution", generate_algorithmic_redistribution),
    ],
)
@pytest.mark.parametrize("location_id", ["x", "not-a-uuid", "a0000000-0000-0000-0000-000000000001,all"])
def test_location_required_commons_reports_reject_malformed_scope_before_cursor(
    report_type, generator, location_id
) -> None:
    class Conn:
        cursor_called = False

        def cursor(self, cursor_factory=None):
            self.cursor_called = True
            raise AssertionError("malformed location must fail before opening a cursor")

    conn = Conn()
    with pytest.raises(ValueError, match="requires a valid location_id"):
        generator(conn, location_id)
    assert report_type in REPORT_GENERATORS
    assert not conn.cursor_called


@pytest.mark.parametrize(
    "report_type,generator,view_name",
    [
        (
            "anti_capture_governance",
            generate_anti_capture_governance,
            "v_public_anti_capture_governance_policy",
        ),
        (
            "redistribution_policy",
            generate_redistribution_policy,
            "v_public_commons_redistribution_policy",
        ),
        (
            "algorithmic_redistribution",
            generate_algorithmic_redistribution,
            "v_public_algorithmic_redistribution_mechanism",
        ),
    ],
)
def test_location_required_commons_reports_query_only_location_and_global_rows(
    report_type, generator, view_name
) -> None:
    class Cursor:
        query = None
        params = None

        def execute(self, query, params=None):
            self.query = query
            self.params = params

        def fetchall(self):
            return []

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_instance = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_instance

    conn = Conn()
    generator(conn, "11111111-1111-4111-8111-111111111111")
    assert view_name in conn.cursor_instance.query
    assert "WHERE location_id = %s OR location_id IS NULL" in conn.cursor_instance.query
    assert conn.cursor_instance.params == ("11111111-1111-4111-8111-111111111111",)


def test_commons_public_view_helpers_select_exact_ordered_columns_and_preserve_rows() -> None:
    expected_columns = {
        "v_public_anti_capture_governance_policy": (
            "id, location_id, policy_name, governance_body, policy_scope, voting_method, voting_cap_pct, "
            "quadratic_or_conviction_enabled, one_person_one_vote_enabled, sybil_resistance_method, "
            "worker_or_operator_veto_enabled, community_veto_enabled, delegation_limits, enforcement_mode, "
            "policy_summary, public_summary, evidence_maturity, status, metadata, source_system, source_id, "
            "source_raw, created_at, updated_at, created_by, updated_by, evidence_maturity_label"
        ),
        "v_public_commons_redistribution_policy": (
            "id, location_id, policy_name, scenario_name, policy_scope, policy_status, revenue_basis, "
            "commons_allocation_pct, local_cooperative_allocation_pct, operator_allocation_pct, "
            "digital_commons_allocation_pct, reserve_allocation_pct, trigger_conditions, enforcement_mode, "
            "audit_cadence, policy_summary, public_summary, evidence_maturity, status, metadata, source_system, "
            "source_id, source_raw, created_at, updated_at, created_by, updated_by, evidence_maturity_label"
        ),
        "v_public_federation_protocol": (
            "id, protocol_name, target_region, federation_scope, permissionless_forking_enabled, "
            "local_adaptation_rights, mutual_aid_commitments, shared_infrastructure, onboarding_requirements, "
            "anti_extractive_safeguards, conflict_resolution_path, protocol_status, public_summary, "
            "evidence_maturity, status, metadata, created_at, updated_at, created_by, updated_by, "
            "evidence_maturity_label"
        ),
        "v_public_algorithmic_redistribution_mechanism": (
            "id, location_id, mechanism_name, mechanism_type, beneficiary_scope, allocation_formula, "
            "funding_source, eligibility_criteria, privacy_safeguards, implementation_status, enforcement_mode, "
            "mechanism_summary, public_summary, evidence_maturity, status, metadata, source_system, source_id, "
            "source_raw, created_at, updated_at, created_by, updated_by, evidence_maturity_label"
        ),
        "v_public_participatory_signal_experiment": (
            "id, experiment_name, signal_type, governance_scope, decision_binding, experiment_status, "
            "participation_rules, moderation_policy, safety_boundaries, public_summary, evidence_maturity, status, "
            "metadata, created_at, updated_at, created_by, updated_by, evidence_maturity_label"
        ),
    }
    cases = [
        (generate_anti_capture_governance, "v_public_anti_capture_governance_policy", "policies", "policy_scope, policy_name", True),
        (generate_redistribution_policy, "v_public_commons_redistribution_policy", "policies", "policy_status, policy_scope, policy_name", True),
        (generate_federation_mutual_aid, "v_public_federation_protocol", "protocols", "protocol_status, federation_scope, protocol_name", False),
        (generate_algorithmic_redistribution, "v_public_algorithmic_redistribution_mechanism", "mechanisms", "implementation_status, mechanism_type, mechanism_name", True),
        (generate_participatory_signal, "v_public_participatory_signal_experiment", "experiments", "experiment_status, signal_type, experiment_name", False),
    ]
    location_id = "11111111-1111-4111-8111-111111111111"
    for generator, view_name, result_key, order_by, location_scoped in cases:
        source_row = {
            "id": "record-1",
            "location_id": location_id if location_scoped else None,
            "public_summary": "Reviewed public summary",
        }

        class Cursor:
            query = None
            params = None

            def execute(self, query, params=None):
                self.query = " ".join(query.split())
                self.params = params

            def fetchall(self):
                return [source_row]

            def close(self):
                pass

        class Conn:
            def __init__(self):
                self.cursor_instance = Cursor()

            def cursor(self, cursor_factory=None):
                return self.cursor_instance

        conn = Conn()
        report = generator(conn, location_id if location_scoped else None)
        query = conn.cursor_instance.query
        projection = query.split(f" FROM {view_name}", 1)[0].removeprefix("SELECT ")

        assert projection == expected_columns[view_name]
        assert query.endswith(f"ORDER BY {order_by}")
        if location_scoped:
            assert "WHERE location_id = %s OR location_id IS NULL" in query
            assert conn.cursor_instance.params == (location_id,)
            assert report["location_id"] == location_id
        else:
            assert "WHERE location_id" not in query
            assert conn.cursor_instance.params is None
            assert report["location_id"] is None
        assert report[result_key] == [source_row]


@pytest.mark.parametrize(
    "generator,view_name",
    [
        (generate_federation_mutual_aid, "v_public_federation_protocol"),
        (generate_participatory_signal, "v_public_participatory_signal_experiment"),
    ],
)
def test_explicit_network_commons_reports_keep_network_wide_queries(generator, view_name) -> None:
    class Cursor:
        query = None

        def execute(self, query, params=None):
            self.query = query

        def fetchall(self):
            return []

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_instance = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_instance

    conn = Conn()
    result = generator(conn)
    assert result["location_id"] is None
    assert view_name in conn.cursor_instance.query
    assert "WHERE location_id" not in conn.cursor_instance.query


if __name__ == "__main__":
    test_kokonut_commons_schema_defines_records_and_public_views()
    test_kokonut_commons_seed_and_dashboards_exist()
    test_pilot_seed_has_flexible_policy_and_excludes_unsupported_claims()
    test_kokonut_commons_task_catalogue_and_validation()
    test_kokonut_commons_agent_summarizes_public_safe_records()
    test_kokonut_commons_report_generators_registered_and_public_safe()
