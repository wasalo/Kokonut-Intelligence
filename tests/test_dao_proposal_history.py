"""Tests for the dao_proposal_history report generator.

Read-only: spins up an in-memory view of the governance_event shape via a
MagicMock connection, then asserts the generator aggregates proposals, tallies
votes, derives lifecycle, and builds the executive summary.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from services.export import report_generator as rg


def _fake_rows():
    """Aggregated governance_event rows shaped like RealDictCursor output."""
    return [
        {"proposal_id": "1", "title": "Missing Loot in Migration", "description": "recover loot",
         "proposal_type": "ISSUE", "content_uri": None,
         "yes_votes": 1, "no_votes": 0, "processed": True, "cancelled": False,
         "sponsored": False, "passed": "True", "action_failed": "False"},
        {"proposal_id": "8", "title": "4 coconuts", "description": "grow",
         "proposal_type": "ISSUE", "content_uri": None,
         "yes_votes": 0, "no_votes": 3, "processed": False, "cancelled": False,
         "sponsored": False, "passed": None, "action_failed": None},
        {"proposal_id": "9", "title": "Renounce Coco", "description": "driving",
         "proposal_type": "MULTICALL", "content_uri": None,
         "yes_votes": 1, "no_votes": 0, "processed": False, "cancelled": True,
         "sponsored": False, "passed": None, "action_failed": None},
        {"proposal_id": "12", "title": "Donny_Jerri", "description": "grow coconuts",
         "proposal_type": "ISSUE", "content_uri": None,
         "yes_votes": 0, "no_votes": 1, "processed": False, "cancelled": False,
         "sponsored": True, "passed": None, "action_failed": None},
        {"proposal_id": "15", "title": "Grant Request: Adelphi", "description": "irrigation",
         "proposal_type": "TRANSFER_ERC20", "content_uri": "https://x/15",
         "yes_votes": 4, "no_votes": 0, "processed": True, "cancelled": False,
         "sponsored": False, "passed": "True", "action_failed": "False"},
    ]


def _fake_conn_with_events(execute_rows=None, voter_rows=None):
    conn = MagicMock()
    cur = MagicMock()
    # First execute() -> aggregated proposal rows; second -> voter rows.
    cur.fetchall.side_effect = [execute_rows or _fake_rows(), voter_rows or []]
    cur.__enter__.return_value = cur
    cur.__exit__.return_value = False
    conn.cursor.return_value = cur
    return conn


def test_dao_proposal_history_aggregates_and_tallies():
    conn = _fake_conn_with_events()
    report = rg.generate_dao_proposal_history(conn)
    assert report["report_type"] == "dao_proposal_history"
    assert report["chain"] == "gnosis"
    proposals = {p["proposal_id"]: p for p in report["proposals"]}
    assert len(proposals) == 5

    assert proposals["1"]["lifecycle"] == "executed"
    assert proposals["1"]["yes_votes"] == 1 and proposals["1"]["no_votes"] == 0
    assert proposals["1"]["passed"] is True

    # No terminal/sponsor event -> aligned with adapter default (sponsored).
    assert proposals["8"]["lifecycle"] == "sponsored"
    assert proposals["8"]["no_votes"] == 3

    assert proposals["9"]["lifecycle"] == "cancelled"
    assert proposals["12"]["lifecycle"] == "sponsored"
    assert proposals["15"]["lifecycle"] == "executed"
    assert proposals["15"]["content_uri"] == "https://x/15"

    assert report["summary"]["total"] == 5
    assert report["summary"]["executed"] == 2
    assert report["summary"]["cancelled"] == 1
    assert report["summary"]["total_votes"] == 10
    assert len(report["executive_summary"]) >= 1
    assert "limitations" in report


def test_dao_proposal_history_resolves_voters():
    voters = [
        {"proposal_id": "15", "wallet_id": "wid-1", "address": "0xVOTER1"},
        {"proposal_id": "15", "wallet_id": "wid-2", "address": "0xVOTER2"},
        {"proposal_id": "15", "wallet_id": "wid-1", "address": "0xVOTER1"},  # duplicate -> de-duped
    ]
    conn = _fake_conn_with_events(voter_rows=voters)
    report = rg.generate_dao_proposal_history(conn)
    p15 = [p for p in report["proposals"] if p["proposal_id"] == "15"][0]
    assert p15["voters"] == ["0xVOTER1", "0xVOTER2"]


def test_dao_proposal_history_registered():
    assert "dao_proposal_history" in rg.REPORT_GENERATORS
    assert rg.REPORT_GENERATORS["dao_proposal_history"] is rg.generate_dao_proposal_history
