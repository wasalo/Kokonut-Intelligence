"""Kokonut Commons governance, redistribution, federation, and participatory signal tests."""

from pathlib import Path

from services.agents.kokonut_commons_agent import synthesize_kokonut_commons
from services.agents.tasks import get_task, list_tasks, validate_output
from services.export.report_generator import (
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
    assert generate_anti_capture_governance(conn, "x")["community_veto_count"] == 1
    assert generate_redistribution_policy(conn, "x")["scenario_policy_count"] == 1
    assert generate_federation_mutual_aid(conn, "x")["permissionless_forking_count"] == 1
    assert generate_algorithmic_redistribution(conn, "x")["report_type"] == "algorithmic_redistribution"
    assert generate_participatory_signal(conn, "x")["advisory_count"] == 1


if __name__ == "__main__":
    test_kokonut_commons_schema_defines_records_and_public_views()
    test_kokonut_commons_seed_and_dashboards_exist()
    test_pilot_seed_has_flexible_policy_and_excludes_unsupported_claims()
    test_kokonut_commons_task_catalogue_and_validation()
    test_kokonut_commons_agent_summarizes_public_safe_records()
    test_kokonut_commons_report_generators_registered_and_public_safe()
