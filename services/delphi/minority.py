"""Governed minority reports for Delphi studies."""

import uuid
from typing import Optional

import psycopg2.extras


class MinorityReportManager:
    def __init__(self, conn):
        self.conn = conn

    def create(self, study_id: str, title: str, position_summary: str, rationale: str,
               item_id: Optional[str] = None, panel_member_id: Optional[str] = None,
               implications: Optional[str] = None) -> dict:
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO delphi_minority_report
               (study_id,item_id,title,position_summary,rationale,implications,created_by_panel_member_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (study_id, item_id, title, position_summary, rationale, implications, panel_member_id),
        )
        row = dict(cur.fetchone())
        self.conn.commit()
        cur.close()
        return row

    def submit(self, report_id: str) -> dict:
        return self._transition(report_id, "draft", "submitted", None, None)

    def review(self, report_id: str, result: str, reviewer_id: str, notes: str) -> dict:
        if result not in {"verified", "rejected"}:
            raise ValueError("result must be verified or rejected")
        uuid.UUID(reviewer_id)
        if not notes.strip():
            raise ValueError("review notes are required")
        return self._transition(report_id, "submitted", result, reviewer_id, notes)

    def _transition(self, report_id, expected, result, reviewer_id, notes):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """UPDATE delphi_minority_report SET status=%s,
               submitted_at=CASE WHEN %s='submitted' THEN NOW() ELSE submitted_at END,
               verified_by=%s, verified_at=CASE WHEN %s='verified' THEN NOW() ELSE NULL END,
               verification_notes=%s, updated_at=NOW()
               WHERE id=%s AND status=%s RETURNING *""",
            (result, result, reviewer_id, result, notes, report_id, expected),
        )
        row = cur.fetchone()
        if not row:
            self.conn.rollback()
            cur.close()
            raise ValueError("Invalid minority report transition")
        self.conn.commit()
        cur.close()
        return dict(row)
