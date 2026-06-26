"""Agent safety helpers for bounded write and audit behavior."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

from services.agents.logging import log_agent_action

HIGH_RISK_ACTIONS = {
    "publish",
    "attest",
    "onchain_submit",
    "delete",
    "bulk_update",
    "financial_write",
    "status_change_to_published",
}

AGENT_ALLOWED_REVIEW_STATUSES = {"draft", "submitted", "rejected"}
AGENT_ALLOWED_SUMMARY_STATUSES = {"draft", "submitted", "rejected"}


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    high_risk: bool
    requires_human_approval: bool
    reason: str


def payload_hash(payload: Optional[dict[str, Any]]) -> Optional[str]:
    """Return a stable SHA-256 hash for audit logging."""
    if payload is None:
        return None
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assess_agent_action(action: str, collection: str, payload: Optional[dict[str, Any]] = None) -> SafetyDecision:
    """Assess whether an agent action is allowed before writing."""
    payload = payload or {}
    high_risk = action in HIGH_RISK_ACTIONS

    if collection == "agent_task":
        review_status = payload.get("review_status")
        if review_status and review_status not in AGENT_ALLOWED_REVIEW_STATUSES:
            return SafetyDecision(False, True, True, "agents cannot verify or publish agent_task records")

    if collection == "ai_summary":
        status = payload.get("status")
        if status and status not in AGENT_ALLOWED_SUMMARY_STATUSES:
            return SafetyDecision(False, True, True, "agents cannot verify or publish ai_summary records")

    if action == "status_change_to_published":
        return SafetyDecision(False, True, True, "agents cannot publish records directly")

    return SafetyDecision(True, high_risk, high_risk, "allowed")


def assert_agent_action_allowed(action: str, collection: str, payload: Optional[dict[str, Any]] = None) -> SafetyDecision:
    """Raise ValueError when the action violates Kokonut agent safety rules."""
    decision = assess_agent_action(action, collection, payload)
    if not decision.allowed:
        raise ValueError(decision.reason)
    return decision


def audit_agent_action(
    agent_id: str,
    action: str,
    collection: str,
    payload: Optional[dict[str, Any]] = None,
    task_id: Optional[str] = None,
    record_id: Optional[str] = None,
    action_result: str = "success",
    error_message: Optional[str] = None,
) -> str:
    """Assess and write an agent_action_log entry."""
    decision = assess_agent_action(action, collection, payload)
    return log_agent_action(
        agent_id=agent_id,
        task_id=task_id,
        action=action,
        collection=collection,
        record_id=record_id,
        payload_hash=payload_hash(payload),
        action_result=action_result,
        error_message=error_message,
        metadata={
            "allowed": decision.allowed,
            "reason": decision.reason,
            "requires_human_approval": decision.requires_human_approval,
        },
    )
