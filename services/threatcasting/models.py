"""Pydantic models for Threatcasting service: threat, flag, cross-impact, signal,
narrative, horizon, desirability, backcast, cascade."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Threat
# ---------------------------------------------------------------------------
class Threat(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    location_id: str
    threat_name: str
    threat_type: str  # climate, policy, market, technology, ecological, social, health, security
    description: Optional[str] = None
    severity_potential: str  # low, medium, high, critical
    probability: Optional[float] = Field(None, ge=0, le=1)
    velocity: str  # slow, moderate, fast, rapid
    reversibility: str  # reversible, partially, irreversible
    time_horizon_years: int = 5
    is_active: bool = True
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ThreatCreate(BaseModel):
    location_id: str
    threat_name: str
    threat_type: str
    description: Optional[str] = None
    severity_potential: str = "medium"
    probability: Optional[float] = Field(None, ge=0, le=1)
    velocity: str = "moderate"
    reversibility: str = "partially"
    time_horizon_years: int = 5
    tags: List[str] = []


# ---------------------------------------------------------------------------
# Threat Flag
# ---------------------------------------------------------------------------
class ThreatFlag(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: str
    flag_name: str
    description: Optional[str] = None
    indicator_type: str  # quantitative, qualitative, threshold, pattern, manual
    current_value: Optional[str] = None
    previous_value: Optional[str] = None
    threshold_critical: Optional[float] = None
    threshold_warning: Optional[float] = None
    threshold_normal: Optional[float] = None
    comparison_operator: str = "gte"
    unit: Optional[str] = None
    status: str = "normal"  # normal, elevated, warning, critical, unknown
    data_source: Optional[str] = None
    check_frequency_hours: int = 24
    last_checked_at: Optional[datetime] = None
    last_value_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ThreatFlagCreate(BaseModel):
    threat_id: str
    flag_name: str
    description: Optional[str] = None
    indicator_type: str = "quantitative"
    threshold_critical: Optional[float] = None
    threshold_warning: Optional[float] = None
    threshold_normal: Optional[float] = None
    comparison_operator: str = "gte"
    unit: Optional[str] = None
    data_source: Optional[str] = None
    check_frequency_hours: int = 24


# ---------------------------------------------------------------------------
# Cross-Impact
# ---------------------------------------------------------------------------
class CrossImpact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_threat_id: str
    target_threat_id: str
    impact_type: str  # amplifies, attenuates, triggers, delays, redirects, enables
    impact_magnitude: float = Field(ge=0, le=1)
    impact_direction: str  # positive, negative
    description: Optional[str] = None
    confidence_level: str = "medium"
    evidence_source: Optional[str] = None
    lag_days: int = 0
    is_enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CrossImpactCreate(BaseModel):
    source_threat_id: str
    target_threat_id: str
    impact_type: str
    impact_magnitude: float = Field(ge=0, le=1)
    impact_direction: str
    description: Optional[str] = None
    confidence_level: str = "medium"
    evidence_source: Optional[str] = None
    lag_days: int = 0


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------
class ThreatSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: Optional[str] = None
    signal_source: str
    source_reference: Optional[str] = None
    signal_type: str  # text, numeric, categorical, event, alert
    content: str
    structured_data: Dict[str, Any] = {}
    confidence: Optional[float] = Field(None, ge=0, le=1)
    relevance_score: Optional[float] = Field(None, ge=0, le=1)
    sentiment: Optional[float] = Field(None, ge=-1, le=1)
    signal_date: datetime
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    classified: bool = False
    classification_notes: Optional[str] = None
    metadata: Dict[str, Any] = {}


class SignalIngestRequest(BaseModel):
    threat_id: Optional[str] = None
    signal_source: str
    source_reference: Optional[str] = None
    signal_type: str = "text"
    content: str
    structured_data: Dict[str, Any] = {}
    confidence: Optional[float] = Field(None, ge=0, le=1)
    signal_date: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------
class ThreatNarrative(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_id: str
    narrative_type: str  # desirable, undesirable, baseline, wildcard
    title: str
    summary: str
    detailed_story: str
    timeline_years: int
    probability_estimate: Optional[float] = Field(None, ge=0, le=1)
    desirability_score: Optional[float] = Field(None, ge=-1, le=1)
    impact_severity: Optional[str] = None
    key_indicators: List[str] = []
    cascading_effects: List[str] = []
    recommended_preparedness: Optional[str] = None
    recommended_response: Optional[str] = None
    is_primary: bool = False
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NarrativeCreate(BaseModel):
    threat_id: str
    narrative_type: str
    title: str
    summary: str
    detailed_story: str
    timeline_years: int
    probability_estimate: Optional[float] = Field(None, ge=0, le=1)
    impact_severity: Optional[str] = None
    key_indicators: List[str] = []
    recommended_preparedness: Optional[str] = None
    recommended_response: Optional[str] = None


# ---------------------------------------------------------------------------
# Horizon
# ---------------------------------------------------------------------------
class ThreatHorizon(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    location_id: str
    horizon_name: str
    horizon_years: int
    description: Optional[str] = None
    focus_areas: List[str] = []
    desirability_framework: str = "gnh_aligned"
    review_frequency_months: int = 12
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HorizonCreate(BaseModel):
    location_id: str
    horizon_name: str
    horizon_years: int
    description: Optional[str] = None
    focus_areas: List[str] = []
    desirability_framework: str = "gnh_aligned"
    review_frequency_months: int = 12


class HorizonThreatLink(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    horizon_id: str
    threat_id: str
    relevance_score: Optional[float] = Field(None, ge=0, le=1)
    time_to_impact_years: Optional[float] = None
    priority_rank: Optional[int] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Desirability Assessment
# ---------------------------------------------------------------------------
class DesirabilityAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    narrative_id: str
    assessment_framework: str  # gnh, 8_forms_capital, sdg, wellbeing, composite, custom
    dimension: str
    score: float = Field(ge=-1, le=1)
    weight: float = Field(default=1.0, ge=0, le=1)
    rationale: Optional[str] = None
    data_sources: List[str] = []
    assessed_by: Optional[str] = None
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DesirabilityAssessmentCreate(BaseModel):
    narrative_id: str
    assessment_framework: str
    dimension: str
    score: float = Field(ge=-1, le=1)
    weight: float = 1.0
    rationale: Optional[str] = None
    data_sources: List[str] = []
    assessed_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Backcast Plan
# ---------------------------------------------------------------------------
class BackcastPlanHeader(BaseModel):
    """Canonical backcast plan record, separate from its milestones."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    narrative_id: str
    location_id: str
    plan_name: str
    future_state_description: str
    current_gap_analysis: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BackcastMilestone(BaseModel):
    """Normalized milestone belonging to a canonical backcast plan."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    milestone_order: int
    milestone_description: str
    milestone_target_date: Optional[date] = None
    milestone_status: str = "pending"
    dependencies: List[str] = Field(default_factory=list)
    responsible_party: Optional[str] = None
    resource_requirements: Optional[str] = None
    completion_evidence: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BackcastPlan(BaseModel):
    """Flattened milestone compatibility model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    narrative_id: str
    location_id: str
    plan_name: str
    future_state_description: str
    current_gap_analysis: str
    milestone_order: int
    milestone_description: str
    milestone_target_date: Optional[date] = None
    milestone_status: str = "pending"
    dependencies: List[str] = []
    responsible_party: Optional[str] = None
    resource_requirements: Optional[str] = None
    completion_evidence: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BackcastPlanCreate(BaseModel):
    """Compatibility request model accepted by the plan creation service."""
    narrative_id: str
    location_id: str
    plan_name: str
    future_state_description: str
    current_gap_analysis: str
    milestones: List[Dict[str, Any]]  # [{order, description, target_date, dependencies, responsible_party, resource_requirements}]


# ---------------------------------------------------------------------------
# Cascade
# ---------------------------------------------------------------------------
class ThreatCascade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trigger_threat_id: str
    cascade_name: str
    description: Optional[str] = None
    failure_chain: List[str] = []  # ordered list of threat IDs
    cascade_probability: Optional[float] = Field(None, ge=0, le=1)
    total_impact_severity: Optional[str] = None
    time_to_cascade_hours: Optional[int] = None
    mitigation_strategies: List[str] = []
    early_warning_signals: List[str] = []
    is_enabled: bool = True
    last_evaluated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CascadeCreate(BaseModel):
    trigger_threat_id: str
    cascade_name: str
    description: Optional[str] = None
    failure_chain: List[str] = []
    mitigation_strategies: List[str] = []
    early_warning_signals: List[str] = []


# ---------------------------------------------------------------------------
# Aggregate Results
# ---------------------------------------------------------------------------
class CrossImpactMatrix(BaseModel):
    location_id: str
    threats: List[Dict[str, Any]]
    impacts: List[CrossImpact]
    amplification_chains: List[List[str]]
    summary: Dict[str, Any]


class ThreatLandscape(BaseModel):
    location_id: str
    threat_count: int
    threats_by_type: Dict[str, int]
    threats_by_severity: Dict[str, int]
    active_flags: int
    warning_flags: int
    critical_flags: int
    active_cascades: int
    overall_risk_score: float
    horizon_count: int
    narrative_count: int


class NarrativeEvaluation(BaseModel):
    narrative_id: str
    overall_desirability_score: float
    framework_scores: Dict[str, float]
    dimension_scores: Dict[str, float]
    alignment_summary: str


class CascadeSimulation(BaseModel):
    cascade_id: str
    trigger_threat: str
    chain_length: int
    cumulative_probability: float
    estimated_time_hours: Optional[int]
    affected_threats: List[str]
    mitigation_effectiveness: Dict[str, float]
    recommendation: str


class BackcastProgress(BaseModel):
    plan_id: str
    plan_name: str
    total_milestones: int
    completed_milestones: int
    progress_pct: float
    overdue_milestones: List[Dict[str, Any]]
    next_milestone: Optional[Dict[str, Any]]
    gaps: List[str]


# ---------------------------------------------------------------------------
# Backcast Principle
# ---------------------------------------------------------------------------
class BackcastPrinciple(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    narrative_id: str
    location_id: str
    principle_name: str
    description: str
    principle_type: str  # sustainability, operational, financial, ecological, social, custom
    metric_key: Optional[str] = None
    comparison_operator: str = "gte"  # gt, gte, lt, lte, eq, neq, between
    target_value: Optional[float] = None
    target_value_upper: Optional[float] = None
    invert_direction: bool = False
    weight: float = Field(default=1.0, ge=0, le=1)
    source_system: str = "manual"  # metric, crisp, manual
    crisp_dimension: Optional[str] = None
    is_active: bool = True
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BackcastPrincipleCreate(BaseModel):
    narrative_id: str
    location_id: str
    principle_name: str
    description: str
    principle_type: str = "custom"
    metric_key: Optional[str] = None
    comparison_operator: str = "gte"
    target_value: Optional[float] = None
    target_value_upper: Optional[float] = None
    invert_direction: bool = False
    weight: float = 1.0
    source_system: str = "manual"
    crisp_dimension: Optional[str] = None


# ---------------------------------------------------------------------------
# Backcast Principle Alignment
# ---------------------------------------------------------------------------
class BackcastPrincipleAlignment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    milestone_id: str
    principle_id: str
    alignment_score: float = Field(ge=-1, le=1)
    current_value: Optional[float] = None
    target_value: Optional[float] = None
    gap: Optional[float] = None
    alignment_evidence: Optional[str] = None
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Backcast Assumption Challenge
# ---------------------------------------------------------------------------
class BackcastAssumptionChallenge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    narrative_id: str
    original_assumption: str
    challenged_assumption: str
    challenge_reason: Optional[str] = None
    outcome: str = "pending"  # pending, confirmed, modified, rejected
    revised_milestone_id: Optional[str] = None
    impact_on_principles: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None


class AssumptionChallengeCreate(BaseModel):
    plan_id: str
    narrative_id: str
    original_assumption: str
    challenged_assumption: str
    challenge_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Backcast Path Comparison
# ---------------------------------------------------------------------------
class BackcastPathComparison(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    location_id: str
    comparison_name: str
    narrative_ids: List[str]
    comparison_criteria: Dict[str, Any] = Field(default_factory=dict)
    auto_scores: Dict[str, Any] = Field(default_factory=dict)
    manual_scores: Dict[str, Any] = Field(default_factory=dict)
    final_scores: Dict[str, Any] = Field(default_factory=dict)
    evaluation_status: str = "not_evaluated"
    score_completeness: Dict[str, Any] = Field(default_factory=dict)
    scoring_version: str = "v2"
    evaluated_at: Optional[datetime] = None
    winner_narrative_id: Optional[str] = None
    winner_score: Optional[float] = None
    rationale: Optional[str] = None
    compared_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PathComparisonCreate(BaseModel):
    location_id: str
    comparison_name: str
    narrative_ids: List[str]
    comparison_criteria: Dict[str, Any] = Field(default_factory=dict)


class PathComparisonScores(BaseModel):
    scores: Dict[str, Dict[str, Optional[float]]]


class PathPremortem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    comparison_id: str
    narrative_id: str
    failure_modes: List[Dict[str, Any]] = Field(default_factory=list)
    assumptions: List[Dict[str, Any]] = Field(default_factory=list)
    early_warning_signals: List[Dict[str, Any]] = Field(default_factory=list)
    mitigations: List[Dict[str, Any]] = Field(default_factory=list)
    residual_risk_notes: Optional[str] = None
    evidence_notes: Optional[str] = None
    status: str = "draft"
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
