"""
Agent Action Logging

Legacy action-log reads and writes fail closed until they can use an
authenticated principal and an appropriately scoped query. Historical rows are
left unchanged.
"""

from typing import Optional


class AgentActionIdentityUnavailable(RuntimeError):
    """Raised when a legacy action-log call has no authenticated scope."""


def log_agent_action(
    agent_id: str,
    task_id: Optional[str],
    action: str,
    collection: str,
    record_id: Optional[str] = None,
    payload_hash: Optional[str] = None,
    action_result: str = "success",
    error_message: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> str:
    """Reject unauthenticated legacy writes to ``agent_action_log``.

    The ``agent_id`` argument is caller-controlled and cannot establish an
    authenticated principal. A bounded signed-worker logging function will
    replace this path when workers need durable action receipts.
    """
    raise AgentActionIdentityUnavailable(
        "agent action logging requires an authenticated worker or operator identity"
    )


def get_agent_actions(
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    high_risk_only: bool = False,
    limit: int = 50,
) -> list:
    """Reject legacy global action-log reads without an authenticated scope."""
    raise AgentActionIdentityUnavailable(
        "agent action history requires an authenticated operator or signed worker scope"
    )
