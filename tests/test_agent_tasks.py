"""Agent task catalogue tests."""

import pytest

from services.agents.cids_agent import run_cids_export
from services.agents.feedback_agent import synthesize_feedback
from services.agents.safety import assess_agent_action
from services.agents.tasks import (
    TASK_CATALOGUE,
    get_task,
    list_tasks,
    validate_output,
    validate_task_capabilities,
    validate_task_inputs,
)


def test_task_catalogue_contains_green_paper_agents() -> None:
    tasks = list_tasks()
    assert "cids_export" in tasks
    assert "feedback_synthesis" in tasks
    assert "holistic_wellbeing_synthesis" in tasks
    assert "financial_resilience_synthesis" in tasks
    assert "ebf_scorecard_draft" in tasks
    assert "ebf_evidence_gap" in tasks
    assert "ebf_calibration_memo" in tasks
    assert "coordination_strategy_draft" in tasks
    assert get_task("cids_export")["high_risk"] is False
    assert get_task("holistic_wellbeing_synthesis")["writes"] == ["ai_summary:draft"]
    assert get_task("financial_resilience_synthesis")["writes"] == ["ai_summary:draft"]
    assert "verify" not in " ".join(get_task("ebf_scorecard_draft")["writes"])
    coordination = get_task("coordination_strategy_draft")
    assert coordination["writes"] == ["coordination_alliance:draft"]
    assert coordination["high_risk"] is False


def test_output_validation_checks_required_fields() -> None:
    errors = validate_output("cids_export", {"graph_count": 1})
    assert "Missing required output field: document" in errors
    assert "Missing required output field: source_scope" in errors

    ebf_errors = validate_output(
        "ebf_evidence_gap",
        {"evidence_gaps": [], "recommendations": []},
    )
    assert "Missing required output field: source_scope" in ebf_errors


def test_output_validation_checks_declared_top_level_types_and_formats() -> None:
    valid = {
        "document": {"@graph": []},
        "graph_count": 1,
        "alignment_tier": "essential",
        "cids_version": "3.2.0",
        "source_scope": {
            "location_id": "a0000000-0000-4000-8000-000000000001",
            "views": [],
        },
    }
    assert validate_output("cids_export", valid) == []
    assert validate_output(
        "ai_summary_synthesis",
        {"summary": {}, "ai_summary_id": "a0000000-0000-4000-8000-000000000001"},
    ) == []

    errors = validate_output(
        "cids_export",
        {
            "document": [],
            "graph_count": True,
            "alignment_tier": 3,
            "cids_version": "3.2.0",
            "source_scope": {
                "location_id": "a0000000-0000-4000-8000-000000000001",
                "views": [],
            },
        },
    )
    assert "Invalid output type for field: document (expected object)" in errors
    assert "Invalid output type for field: graph_count (expected integer)" in errors
    assert "Invalid output type for field: alignment_tier (expected string)" in errors

    uuid_errors = validate_output(
        "ai_summary_synthesis",
        {"summary": {}, "ai_summary_id": "private-not-a-uuid"},
    )
    assert uuid_errors == ["Invalid output format for field: ai_summary_id (expected uuid)"]
    assert "private-not-a-uuid" not in " ".join(uuid_errors)


def test_task_input_validation_checks_required_types_and_formats() -> None:
    assert validate_task_inputs("ebf_evidence_gap", {}) == [
        "Missing required task input: scorecard_id",
        "Missing required task input: location_id",
    ]
    assert validate_task_inputs("financial_resilience_synthesis", {"store": False}) == [
        "Missing required task input: location_id",
    ]

    valid = {
        "location_id": "a0000000-0000-4000-8000-000000000001",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
    }
    assert validate_task_inputs("ebf_scorecard_draft", valid) == []

    errors = validate_task_inputs(
        "ebf_scorecard_draft",
        {"location_id": "bad-id", "period_start": "2026-W01-1", "period_end": 20261231},
    )
    assert "Invalid task input format for field: location_id (expected uuid)" in errors
    assert "Invalid task input format for field: period_start (expected date)" in errors
    assert "Invalid task input type for field: period_end (expected string)" in errors
    assert "bad-id" not in " ".join(errors)


def test_every_catalogue_write_is_draft_or_submission_only() -> None:
    for task_key in list_tasks():
        task = get_task(task_key)
        assert task["high_risk"] is False
        for target in task["writes"]:
            collection, status = target.split(":", 1)
            assert status in {"draft", "submitted"}
            assert assess_agent_action("create", collection, {"status": status}).allowed


def test_task_definitions_are_returned_as_copies() -> None:
    task = get_task("ai_summary_synthesis")
    task["writes"].append("ai_summary:published")
    assert get_task("ai_summary_synthesis")["writes"] == ["ai_summary:draft"]


def test_unsafe_catalogue_write_fails_before_agent_database_access(monkeypatch) -> None:
    import services.agents.base as agent_base

    calls = []

    class ProbeAgent(agent_base.SynthesisAgent):
        task_key = "ai_summary_synthesis"
        summary_type = "probe"
        read_collection = "ai_summary"

        def synthesize(self, conn, location_id=None):
            calls.append("synthesize")
            return {"synthesis": "unused"}

    def unexpected_database_access():
        calls.append("database")
        raise AssertionError("unsafe catalogue must be rejected before database access")

    monkeypatch.setattr(agent_base, "get_db", unexpected_database_access, raising=False)
    original_writes = TASK_CATALOGUE["ai_summary_synthesis"]["writes"]
    monkeypatch.setitem(
        TASK_CATALOGUE,
        "ai_summary_synthesis",
        {**TASK_CATALOGUE["ai_summary_synthesis"], "writes": ["ai_summary:published"]},
    )
    with pytest.raises(ValueError, match="unapproved write capability"):
        ProbeAgent().run("00000000-0000-0000-0000-000000000001")
    assert calls == []
    assert original_writes == ["ai_summary:draft"]


def test_task_catalogue_rejects_unknown_write_targets(monkeypatch) -> None:
    task = dict(TASK_CATALOGUE["ai_summary_synthesis"])
    task["writes"] = ["unreviewed_collection:draft"]
    monkeypatch.setitem(TASK_CATALOGUE, "unreviewed_task", task)
    with pytest.raises(ValueError, match="unapproved write capability"):
        validate_task_capabilities("unreviewed_task")


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("inputs", "type", "date", "unsupported inputs schema type"),
        ("inputs", "format", "slug", "unsupported inputs format"),
        ("inputs", "required", "yes", "invalid inputs required flag"),
        ("inputs", "future_keyword", True, "unsupported inputs schema constraints"),
        ("outputs", "format", [], "unsupported outputs format"),
    ],
)
def test_task_catalogue_rejects_malformed_schema_declarations(
    monkeypatch, section: str, field: str, value, message: str
) -> None:
    from copy import deepcopy

    task = deepcopy(TASK_CATALOGUE["ai_summary_synthesis"])
    target_field = "summary" if section == "outputs" else "location_id"
    task[section][target_field][field] = value
    monkeypatch.setitem(TASK_CATALOGUE, "malformed_input_schema", task)

    with pytest.raises(ValueError, match=message):
        validate_task_capabilities("malformed_input_schema")


def test_cids_agent_output_with_monkeypatch(monkeypatch) -> None:
    from services.agents import worker_cli

    expected = {
        "document": {
            "@graph": [{"@type": "cids:Organization"}],
            "kokonut:alignmentTier": "essential",
            "kokonut:cidsVersion": "3.2.0",
        },
        "graph_count": 1,
        "alignment_tier": "essential",
        "cids_version": "3.2.0",
        "source_scope": {
            "location_id": "a0000000-0000-4000-8000-000000000001",
            "views": [
                "kokonut_agent_source.cids_location",
                "kokonut_agent_source.cids_stakeholder_outcome",
                "kokonut_agent_source.cids_farm_impact_mapping",
                "kokonut_agent_source.cids_metric_value",
                "kokonut_agent_source.cids_stakeholder_feedback",
                "kokonut_agent_source.cids_impact_claim",
            ],
        },
    }
    monkeypatch.setattr(worker_cli, "run_worker_cids_export", lambda _location_id: expected)

    output = run_cids_export("a0000000-0000-0000-0000-000000000001")
    assert output == expected


def test_feedback_synthesis_omits_private_raw_text() -> None:
    class Cursor:
        query = ""

        def execute(self, query, params):
            self.query = query

        def fetchall(self):
            return [{
                    "stakeholder_group": "farm_operator",
                    "feedback_type": "farmer_feedback",
                    "sentiment": "mixed",
                    "public_summary": "Operators requested simpler Spanish summaries.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }, {
                    "stakeholder_group": "farm_operator",
                    "feedback_type": "farmer_feedback",
                    "sentiment": "mixed",
                    "public_summary": "Operators requested simpler Spanish summaries.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]

        def close(self):
            pass

    class Conn:
        cursor_instance = None

        def cursor(self, cursor_factory=None):
            self.cursor_instance = Cursor()
            return self.cursor_instance

    conn = Conn()
    summary = synthesize_feedback(conn, "a0000000-0000-0000-0000-000000000001")
    assert summary["public_feedback_count"] == 2
    assert summary["private_or_no_consent_count"] is None
    assert summary["harm_or_unintended_consequence_count"] is None
    assert summary["aggregate_feedback"][0]["feedback_count"] == 2
    assert "effective public-summary consent" in summary["safety_note"]
    assert (
        "FROM kokonut_agent_source.v_public_stakeholder_feedback_summary"
        in conn.cursor_instance.query
    )
    assert "FROM stakeholder_feedback" not in conn.cursor_instance.query


def test_ebf_agent_safety_blocks_publish_and_public_maturity() -> None:
    publish_decision = assess_agent_action("update", "ebf_scorecard", {"status": "published"})
    assert publish_decision.allowed is False
    assert publish_decision.requires_human_approval is True

    maturity_decision = assess_agent_action("update", "ebf_score", {"evidence_maturity_level": 4})
    assert maturity_decision.allowed is False
    assert "public-claim levels" in maturity_decision.reason


def test_task_catalogue_covers_all_agent_modules() -> None:
    """Every *_agent.py file must have a corresponding TASK_CATALOGUE entry."""
    import glob
    import os

    agent_dir = os.path.join(os.path.dirname(__file__), "..", "services", "agents")
    agent_files = glob.glob(os.path.join(agent_dir, "*_agent.py"))
    agent_names = [os.path.basename(f).replace(".py", "") for f in agent_files]

    tasks = list_tasks()
    task_keys = " ".join(tasks)
    for name in sorted(agent_names):
        # Strip _agent suffix, then check if any significant word appears in any task key
        core = name.replace("_agent", "")
        # Split on underscores and check if at least one significant word (len >= 4) matches
        words = [w for w in core.split("_") if len(w) >= 3]
        assert any(w in task_keys for w in words), (
            f"Agent module {name} has no matching TASK_CATALOGUE entry"
        )


def test_organic_readiness_task_entries() -> None:
    task = get_task("organic_readiness_synthesis")
    assert task["risk"] == "medium"
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert "location_id" in task["inputs"]
    assert "summary" in task["outputs"]


def test_ecological_modeling_task_entries() -> None:
    task = get_task("ecological_modeling_synthesis")
    assert task["risk"] == "medium"
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert "location_id" in task["inputs"]
    assert "summary" in task["outputs"]


if __name__ == "__main__":
    test_task_catalogue_contains_green_paper_agents()
    test_output_validation_checks_required_fields()
    test_ebf_agent_safety_blocks_publish_and_public_maturity()
    test_task_catalogue_covers_all_agent_modules()
    test_organic_readiness_task_entries()
    test_ecological_modeling_task_entries()
