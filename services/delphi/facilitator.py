"""Legacy Delphi facade with no unscoped database access.

Study authoring, participation, evaluation, and review now use authenticated,
location-scoped Gateway contracts. Keep these method signatures for callers
that need a clear migration error, but do not allow the legacy service to open
a shared connection or mutate/read Delphi records directly.
"""

from __future__ import annotations

from typing import Any, Dict, List, NoReturn, Optional

_GATEWAY_REQUIRED = (
    "Direct Delphi database access is disabled; use the authenticated, "
    "location-scoped Gateway"
)


class Facilitator:
    """Compatibility facade that fails closed for legacy database methods."""

    def __init__(self, conn=None):
        # Retain the argument for source compatibility, but never use it.
        self._conn = conn

    @staticmethod
    def _deny_database_access() -> NoReturn:
        raise RuntimeError(_GATEWAY_REQUIRED)

    def _get_conn(self):
        """Prevent callers from obtaining a shared connection via this facade."""
        self._deny_database_access()

    def create_study(
        self,
        title: str,
        description: Optional[str] = None,
        location_id: Optional[str] = None,
        variation: str = "real_time",
        facilitator_type: str = "agent",
        stopping_criteria: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._deny_database_access()

    def open_study(self, study_id: str) -> Dict[str, Any]:
        self._deny_database_access()

    def close_study(self, study_id: str) -> Dict[str, Any]:
        self._deny_database_access()

    def get_study(self, study_id: str) -> Optional[Dict[str, Any]]:
        self._deny_database_access()

    def add_item(
        self,
        study_id: str,
        label: str,
        item_type: str = "option",
        scale: str = "desirability",
        description: Optional[str] = None,
        min_value: float = -1.0,
        max_value: float = 1.0,
        target_entity_type: Optional[str] = None,
        target_entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._deny_database_access()

    def submit_contribution(
        self,
        study_id: str,
        item_id: str,
        panel_member_id: str,
        score: float,
        reasoning: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._deny_database_access()

    def _recompute_consensus(self, cur, study_id: str, item_id: str) -> Dict[str, Any]:
        self._deny_database_access()

    def get_live_summary(self, study_id: str) -> Dict[str, Any]:
        self._deny_database_access()

    def _panel_size(self, cur, study_id: str) -> int:
        self._deny_database_access()

    def check_stopping(self, study_id: str) -> Dict[str, Any]:
        self._deny_database_access()

    def draft_recommendation(
        self,
        study_id: str,
        recommendation_text: str,
        summary: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._deny_database_access()

    def approve_recommendation(
        self,
        recommendation_id: str,
        approved_by: str,
    ) -> Dict[str, Any]:
        self._deny_database_access()

    def reject_recommendation(
        self,
        recommendation_id: str,
        rejected_by: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._deny_database_access()

    def list_recommendations(self, study_id: str) -> List[Dict[str, Any]]:
        self._deny_database_access()

    def calibrate_panel(self, study_id: str) -> Dict[str, Any]:
        self._deny_database_access()
