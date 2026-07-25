"""Agent safety helper tests."""


import psycopg2
import pytest

from services.agents.safety import (
    GOVERNED_COLLECTIONS,
    assert_agent_action_allowed,
    assess_agent_action,
    payload_hash,
    set_agent_context,
)


def test_payload_hash_is_stable() -> None:
    assert payload_hash({"b": 2, "a": 1}) == payload_hash({"a": 1, "b": 2})


def test_blocks_agent_publish_status() -> None:
    decision = assess_agent_action(
        "update", "agent_task", {"review_status": "published"}
    )
    assert decision.allowed is False
    assert decision.requires_human_approval is True


def test_high_risk_action_requires_human_approval() -> None:
    decision = assert_agent_action_allowed("attest", "attestation_request", {})
    assert decision.allowed is True
    assert decision.high_risk is True
    assert decision.requires_human_approval is True


def test_modeled_decision_outputs_are_governed() -> None:
    expected = {
        "report_snapshot",
        "forecast_scenario",
        "forecast_output",
        "crisp_risk_assessment",
        "threat_narrative",
        "backcast_path_comparison",
        "backcast_path_premortem",
        "prediction_ledger",
        "prediction_outcome",
        "reference_class",
        "outside_view_comparison",
        "delphi_minority_report",
        "threat_forecast_resolution",
    }
    assert expected <= GOVERNED_COLLECTIONS


def test_agent_cannot_publish_modeled_decision_output() -> None:
    decision = assess_agent_action(
        "update", "report_snapshot", {"status": "published"}
    )
    assert decision.allowed is False
    assert decision.requires_human_approval is True


def test_stakeholder_human_review_collections_are_write_protected() -> None:
    for collection in (
        "stakeholder_consent",
        "stakeholder_decision",
        "buyer_verification",
        "party_trust_evidence",
        "nature_stewardship_obligation",
    ):
        decision = assess_agent_action("create", collection, {})
        assert decision.allowed is False
        assert decision.requires_human_approval is True


def test_agent_can_read_stakeholder_records() -> None:
    decision = assess_agent_action("read", "stakeholder_decision", {})
    assert decision.allowed is True


def test_set_agent_context_exists() -> None:
    """set_agent_context helper is importable and callable."""
    assert callable(set_agent_context)


# ---------------------------------------------------------------------------
# DB-level trigger tests (require running PostgreSQL with migration 350 applied)
# ---------------------------------------------------------------------------

def _db_available() -> bool:
    """Check if the database is reachable."""
    try:
        from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD,
        )
        conn.close()
        return True
    except Exception:
        return False


def _trigger_exists(conn, table_name: str) -> bool:
    """Check if the trg_agent_safety trigger exists on a table."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_trigger WHERE tgname = 'trg_agent_safety' AND tgrelid = %s::regclass",
            (table_name,),
        )
        return cur.fetchone() is not None


def _function_exists(conn) -> bool:
    """Check if the assert_agent_safety() function exists."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_proc WHERE proname = 'assert_agent_safety'"
        )
        return cur.fetchone() is not None


DB_SKIP_REASON = "no database available — trigger tests require PostgreSQL with migration 350"


@pytest.mark.skipif(not _db_available(), reason=DB_SKIP_REASON)
def test_trigger_function_exists(db):
    """The assert_agent_safety() trigger function is created by migration 350."""
    assert _function_exists(db)


@pytest.mark.skipif(not _db_available(), reason=DB_SKIP_REASON)
def test_trigger_applied_to_impact_claim(db):
    """trg_agent_safety trigger exists on impact_claim."""
    assert _trigger_exists(db, "impact_claim")


@pytest.mark.skipif(not _db_available(), reason=DB_SKIP_REASON)
def test_trigger_applied_to_carbon_credit(db):
    """trg_agent_safety trigger exists on carbon_credit."""
    assert _trigger_exists(db, "carbon_credit")


@pytest.mark.skipif(not _db_available(), reason=DB_SKIP_REASON)
def test_trigger_applied_to_data_stream_post(db):
    """trg_agent_safety trigger exists on data_stream_post."""
    assert _trigger_exists(db, "data_stream_post")


@pytest.mark.skipif(not _db_available(), reason=DB_SKIP_REASON)
def test_trigger_applied_to_threat(db):
    """trg_agent_safety trigger exists on threat."""
    assert _trigger_exists(db, "threat")


@pytest.mark.skipif(not _db_available(), reason=DB_SKIP_REASON)
def test_trigger_applied_to_coordination_alliance(db):
    """trg_agent_safety trigger exists on coordination_alliance."""
    assert _trigger_exists(db, "coordination_alliance")


@pytest.mark.skipif(not _db_available(), reason=DB_SKIP_REASON)
def test_agent_blocked_from_publishing_via_direct_sql(db):
    """Direct SQL UPDATE with agent_id set cannot escalate status to 'published'."""
    # Create a temp table to test the trigger without touching real data
    with db.cursor() as cur:
        cur.execute("""
            CREATE TEMPORARY TABLE test_agent_safety_check (
                id SERIAL PRIMARY KEY,
                status TEXT DEFAULT 'draft'
            )
        """)
        cur.execute("INSERT INTO test_agent_safety_check (status) VALUES ('draft') RETURNING id")
        row_id = cur.fetchone()[0]

        # Apply the trigger function and trigger to the temp table
        cur.execute("""
            CREATE TRIGGER trg_agent_safety
                BEFORE UPDATE ON test_agent_safety_check
                FOR EACH ROW
                WHEN (NEW.status IS DISTINCT FROM OLD.status)
                EXECUTE FUNCTION assert_agent_safety('status')
        """)

        # Set agent context and try to publish — should fail
        cur.execute("SET LOCAL app.agent_id = 'test_agent'")
        with pytest.raises(psycopg2.errors.RaiseException, match="Agent test_agent cannot set status to published"):
            cur.execute(
                "UPDATE test_agent_safety_check SET status = 'published' WHERE id = %s",
                (row_id,),
            )
        db.rollback()

    # Clean up temp table
    with db.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS test_agent_safety_check")
    db.commit()


@pytest.mark.skipif(not _db_available(), reason=DB_SKIP_REASON)
def test_human_operation_allowed_via_direct_sql(db):
    """Direct SQL UPDATE without agent_id set (human operation) can publish."""
    with db.cursor() as cur:
        cur.execute("""
            CREATE TEMPORARY TABLE test_human_safety_check (
                id SERIAL PRIMARY KEY,
                status TEXT DEFAULT 'draft'
            )
        """)
        cur.execute("INSERT INTO test_human_safety_check (status) VALUES ('draft') RETURNING id")
        row_id = cur.fetchone()[0]

        # Apply the trigger
        cur.execute("""
            CREATE TRIGGER trg_agent_safety
                BEFORE UPDATE ON test_human_safety_check
                FOR EACH ROW
                WHEN (NEW.status IS DISTINCT FROM OLD.status)
                EXECUTE FUNCTION assert_agent_safety('status')
        """)

        # No agent_id set — this is a human operation, should succeed
        cur.execute(
            "UPDATE test_human_safety_check SET status = 'published' WHERE id = %s",
            (row_id,),
        )
        cur.execute("SELECT status FROM test_human_safety_check WHERE id = %s", (row_id,))
        assert cur.fetchone()[0] == "published"
    db.rollback()


@pytest.mark.skipif(not _db_available(), reason=DB_SKIP_REASON)
def test_agent_can_draft_via_direct_sql(db):
    """Agent can set status to 'draft' or 'submitted' — only verified/published blocked."""
    with db.cursor() as cur:
        cur.execute("""
            CREATE TEMPORARY TABLE test_agent_draft_check (
                id SERIAL PRIMARY KEY,
                status TEXT DEFAULT 'draft'
            )
        """)
        cur.execute("INSERT INTO test_agent_draft_check (status) VALUES ('draft') RETURNING id")
        row_id = cur.fetchone()[0]

        cur.execute("""
            CREATE TRIGGER trg_agent_safety
                BEFORE UPDATE ON test_agent_draft_check
                FOR EACH ROW
                WHEN (NEW.status IS DISTINCT FROM OLD.status)
                EXECUTE FUNCTION assert_agent_safety('status')
        """)

        # Set agent context
        cur.execute("SET LOCAL app.agent_id = 'test_agent'")

        # Agent setting status to 'submitted' should succeed
        cur.execute(
            "UPDATE test_agent_draft_check SET status = 'submitted' WHERE id = %s",
            (row_id,),
        )
        cur.execute("SELECT status FROM test_agent_draft_check WHERE id = %s", (row_id,))
        assert cur.fetchone()[0] == "submitted"

        # Agent setting status to 'draft' (from submitted) should succeed
        cur.execute(
            "UPDATE test_agent_draft_check SET status = 'draft' WHERE id = %s",
            (row_id,),
        )
        cur.execute("SELECT status FROM test_agent_draft_check WHERE id = %s", (row_id,))
        assert cur.fetchone()[0] == "draft"
    db.rollback()


if __name__ == "__main__":
    test_payload_hash_is_stable()
    test_blocks_agent_publish_status()
    test_high_risk_action_requires_human_approval()
    test_set_agent_context_exists()
