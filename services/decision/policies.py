"""Decision policy definitions — default rules for the policy engine.

These define the standard decision policies that can be seeded into
the database. Each policy has trigger conditions and action configurations.
"""

from __future__ import annotations

from typing import Any, Dict, List


DEFAULT_POLICIES: List[Dict[str, Any]] = [
    {
        "policy_name": "critical_situation_intervention",
        "policy_type": "rule",
        "description": "Create intervention draft when situation is critical",
        "priority": 100,
        "trigger_situation_grade": "critical",
        "trigger_dimension": None,
        "trigger_score_min": None,
        "trigger_score_max": None,
        "trigger_event_type": None,
        "action_type": "create_intervention_draft",
        "action_config": {
            "priority": "high",
            "draft_type": "emergency_intervention",
        },
        "requires_approval": True,
        "approval_role": "admin",
        "cooldown_minutes": 120,
        "max_executions_per_day": 5,
        "risk_level": "high",
    },
    {
        "policy_name": "warning_situation_alert",
        "policy_type": "rule",
        "description": "Send alert notification when situation is warning",
        "priority": 80,
        "trigger_situation_grade": "warning",
        "trigger_dimension": None,
        "trigger_score_min": None,
        "trigger_score_max": None,
        "trigger_event_type": None,
        "action_type": "send_alert_notification",
        "action_config": {
            "channel": "directus",
            "severity": "warning",
            "include_dimensions": True,
        },
        "requires_approval": True,
        "approval_role": "operator",
        "cooldown_minutes": 60,
        "max_executions_per_day": 10,
        "risk_level": "medium",
    },
    {
        "policy_name": "climate_dimension_critical",
        "policy_type": "rule",
        "description": "Trigger reassessment when climate risk is critical",
        "priority": 90,
        "trigger_situation_grade": None,
        "trigger_dimension": "climate",
        "trigger_score_min": None,
        "trigger_score_max": 30.0,
        "trigger_event_type": None,
        "action_type": "trigger_reassessment",
        "action_config": {
            "assessment_type": "deep",
            "focus_frameworks": ["climate_risk", "ecological_modeling"],
        },
        "requires_approval": True,
        "approval_role": "operator",
        "cooldown_minutes": 30,
        "max_executions_per_day": 8,
        "risk_level": "medium",
    },
    {
        "policy_name": "anomaly_cluster_investigation",
        "policy_type": "rule",
        "description": "Create data stream post when anomaly cluster detected",
        "priority": 70,
        "trigger_situation_grade": None,
        "trigger_dimension": None,
        "trigger_score_min": None,
        "trigger_score_max": None,
        "trigger_event_type": "anomaly_cluster",
        "action_type": "create_data_stream_post",
        "action_config": {
            "post_type": "monitoring_report",
            "title_template": "Anomaly Cluster Detected — {location_name}",
            "auto_generate_summary": True,
        },
        "requires_approval": True,
        "approval_role": "operator",
        "cooldown_minutes": 45,
        "max_executions_per_day": 6,
        "risk_level": "low",
    },
    {
        "policy_name": "adaptive_sampling_high_uncertainty",
        "policy_type": "rule",
        "description": "Increase sampling rate when uncertainty is high",
        "priority": 60,
        "trigger_situation_grade": None,
        "trigger_dimension": None,
        "trigger_score_min": None,
        "trigger_score_max": 40.0,
        "trigger_event_type": None,
        "action_type": "adjust_sampling_rate",
        "action_config": {
            "adjustment": "increase",
            "factor": 0.5,
            "reason": "high_uncertainty",
        },
        "requires_approval": True,
        "approval_role": "operator",
        "cooldown_minutes": 240,
        "max_executions_per_day": 4,
        "risk_level": "low",
    },
]


def list_policies() -> List[Dict[str, Any]]:
    """Return the list of default policy definitions."""
    return DEFAULT_POLICIES


def get_policy(policy_name: str) -> Dict[str, Any]:
    """Get a specific policy definition by name."""
    for policy in DEFAULT_POLICIES:
        if policy["policy_name"] == policy_name:
            return policy
    raise KeyError(f"Policy '{policy_name}' not found")
