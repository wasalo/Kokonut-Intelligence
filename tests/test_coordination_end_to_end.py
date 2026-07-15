"""Cross-domain coordination cockpit and task safety coverage."""

from pathlib import Path

from services.agents.tasks import get_task
from services.export.report_generator import REPORT_GENERATORS


def test_coordination_task_and_cockpit_are_catalogued():
    task = get_task("coordination_strategy_draft")
    assert task["writes"] == ["coordination_alliance:draft"]
    assert "coordination_cockpit" in REPORT_GENERATORS


def test_public_coordination_schema_excludes_private_evidence():
    schema = (Path(__file__).resolve().parents[1] / "schemas/postgres/238_coordination_governance_cockpit.sql").read_text()
    assert "v_public_coordination_alliance" in schema
    assert "privacy_limitation" in schema
    assert "public_summary" in schema
    assert "private evidence" in schema
