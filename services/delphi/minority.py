"""Legacy Delphi minority-report facade with no unscoped database access.

Minority-report lifecycle and independent review need the authenticated,
location-scoped Gateway contract. Until that contract exists, these legacy
helpers must not use an injected shared connection to read or mutate records.
"""

from __future__ import annotations

from typing import NoReturn, Optional


class MinorityReportManager:
    """Compatibility facade that fails closed for legacy report operations."""

    def __init__(self, conn):
        # Retain the argument for source compatibility, but never use it.
        self.conn = conn

    @staticmethod
    def _deny_database_access() -> NoReturn:
        raise RuntimeError(
            "Direct Delphi minority-report database access is disabled; use an "
            "authenticated, location-scoped Gateway workflow when available"
        )

    def create(
        self,
        study_id: str,
        title: str,
        position_summary: str,
        rationale: str,
        item_id: Optional[str] = None,
        panel_member_id: Optional[str] = None,
        implications: Optional[str] = None,
    ) -> dict:
        self._deny_database_access()

    def submit(self, report_id: str) -> dict:
        self._deny_database_access()

    def review(
        self,
        report_id: str,
        result: str,
        reviewer_id: str,
        notes: str,
    ) -> dict:
        self._deny_database_access()

    def _transition(
        self,
        report_id,
        expected,
        result,
        reviewer_id,
        notes,
    ):
        self._deny_database_access()
