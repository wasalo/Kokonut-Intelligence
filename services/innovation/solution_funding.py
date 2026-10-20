"""Legacy solution funding API, retained as a fail-closed compatibility shim.

Funding proposals and review decisions must use the location-scoped Gateway.
Disbursement remains disabled until a separately reviewed custody contract is
implemented.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, NoReturn, Optional


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def _retired(action: str) -> NoReturn:
    raise RuntimeError(
        f"legacy solution funding {action} is disabled; use the location-scoped "
        "solution-lifecycle Gateway workflow"
    )


def create_case(conn, solution_id: str, capital_stage: str, funding_instrument: str, requested_amount: float, rationale: str, *, experiment_id: Optional[str] = None, strategy_investment_id: Optional[str] = None, minimum_viable_amount: Optional[float] = None, maximum_authorized_amount: Optional[float] = None, currency: str = "USD", risk_adjusted_expected_value: Optional[float] = None, public_goods_value: Optional[float] = None, community_share: Optional[float] = None, downside_exposure: Optional[float] = None, evidence: Optional[list[Any]] = None) -> Dict[str, Any]:
    """Retired: create cases through the signed, location-scoped Gateway."""
    _retired("case creation")


def submit_case(conn, case_id: str, submitted_by_party_id: str) -> Dict[str, Any]:
    """Retired: submit cases through the signed, location-scoped Gateway."""
    _retired("case submission")


def approve_case(conn, case_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    """Retired: approve cases through the independent Gateway review action."""
    _retired("case approval")


def add_tranche(conn, case_id: str, tranche_number: int, amount: float, milestone_conditions: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
    """Retired: propose tranches through the location-scoped Gateway."""
    _retired("tranche creation")


def approve_tranche(conn, tranche_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    """Retired: approve tranches through the independent Gateway review action."""
    _retired("tranche approval")


def release_tranche(conn, tranche_id: str, amount: float, released_by_party_id: str, milestone_evidence: list[Any]) -> Dict[str, Any]:
    """Retired: disbursement requires a separately reviewed custody contract."""
    _retired("tranche release")
