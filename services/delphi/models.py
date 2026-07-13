"""Pydantic models for the Real-time Delphi service: study, panel member, item,
contribution, consensus, recommendation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Study
# ---------------------------------------------------------------------------
class DelphiStudy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    location_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    variation: str = "real_time"
    status: str = "draft"
    facilitator_type: str = "agent"
    stopping_criteria: Dict[str, Any] = Field(
        default_factory=lambda: {
            "max_duration_hours": 720,
            "stability_pct": 5.0,
            "min_participants": 3,
            "iqr_threshold": 1.0,
        }
    )
    created_by: Optional[str] = None
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DelphiStudyCreate(BaseModel):
    location_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    variation: str = "real_time"
    facilitator_type: str = "agent"
    stopping_criteria: Dict[str, Any] = Field(
        default_factory=lambda: {
            "max_duration_hours": 720,
            "stability_pct": 5.0,
            "min_participants": 3,
            "iqr_threshold": 1.0,
        }
    )
    created_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Panel member
# ---------------------------------------------------------------------------
class DelphiPanelMember(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    participant_ref_type: str = "farmer_identity"
    participant_ref_id: Optional[str] = None
    display_token: str
    is_anonymous: bool = True
    expert_weight: float = Field(default=1.0, ge=0, le=10)
    role: str = "expert"
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DelphiPanelMemberCreate(BaseModel):
    study_id: str
    participant_ref_type: str = "farmer_identity"
    participant_ref_id: Optional[str] = None
    display_token: str
    is_anonymous: bool = True
    expert_weight: float = Field(default=1.0, ge=0, le=10)
    role: str = "expert"


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------
class DelphiItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    item_type: str = "option"
    label: str
    description: Optional[str] = None
    scale: str = "desirability"
    min_value: float = -1.0
    max_value: float = 1.0
    target_entity_type: Optional[str] = None
    target_entity_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DelphiItemCreate(BaseModel):
    study_id: str
    item_type: str = "option"
    label: str
    description: Optional[str] = None
    scale: str = "desirability"
    min_value: float = -1.0
    max_value: float = 1.0
    target_entity_type: Optional[str] = None
    target_entity_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Contribution
# ---------------------------------------------------------------------------
class DelphiContribution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    item_id: str
    panel_member_id: str
    score: float
    reasoning: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DelphiContributionCreate(BaseModel):
    item_id: str
    panel_member_id: str
    score: float
    reasoning: Optional[str] = None


# ---------------------------------------------------------------------------
# Consensus
# ---------------------------------------------------------------------------
class DelphiConsensus(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    item_id: str
    median: Optional[float] = None
    mean: Optional[float] = None
    iqr: Optional[float] = None
    stddev: Optional[float] = None
    cv: Optional[float] = None
    participant_count: int = 0
    weighted_median: Optional[float] = None
    consensus_reached: bool = False
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DelphiConsensusHistory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    item_id: str
    median: Optional[float] = None
    iqr: Optional[float] = None
    participant_count: int = 0
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------
class DelphiRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    study_id: str
    summary: Optional[str] = None
    recommendation_text: str
    status: str = "draft"
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DelphiRecommendationCreate(BaseModel):
    study_id: str
    recommendation_text: str
    summary: Optional[str] = None
    created_by: Optional[str] = None
