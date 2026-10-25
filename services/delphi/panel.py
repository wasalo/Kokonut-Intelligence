"""Legacy Delphi panel facade with no unscoped database access.

Panel membership is created by the authenticated consent and invite Gateway
flows. Unscoped legacy reads and writes stay unavailable until each has a
location-scoped authorization and privacy contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, NoReturn, Optional


class PanelManager:
    """Compatibility facade that fails closed for legacy panel operations."""

    def __init__(self, conn=None):
        # Retain the argument for source compatibility, but never use it.
        self._conn = conn

    @staticmethod
    def _deny_database_access() -> NoReturn:
        raise RuntimeError(
            "Direct Delphi panel database access is disabled; use the authenticated, "
            "location-scoped Gateway"
        )

    def _get_conn(self):
        """Prevent callers from obtaining a shared connection via this facade."""
        self._deny_database_access()

    def add_member(
        self,
        study_id: str,
        participant_ref_type: str = "farmer_identity",
        participant_ref_id: Optional[str] = None,
        role: str = "expert",
        display_token: Optional[str] = None,
        is_anonymous: bool = True,
        expert_weight: Optional[float] = None,
    ) -> Dict[str, Any]:
        self._deny_database_access()

    def list_members(self, study_id: str) -> List[Dict[str, Any]]:
        self._deny_database_access()

    def get_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        self._deny_database_access()

    def remove_member(self, member_id: str) -> bool:
        self._deny_database_access()

    def _derive_weight(
        self,
        cur,
        participant_ref_type: str,
        participant_ref_id: Optional[str],
        role: str,
    ) -> float:
        self._deny_database_access()

    def member_weights(self, study_id: str) -> Dict[str, float]:
        self._deny_database_access()

    def assess_diversity(self, study_id: str) -> Dict[str, Any]:
        self._deny_database_access()
