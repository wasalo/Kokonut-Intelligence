"""OIDC routes for location-scoped solution lifecycle reads."""

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)


def _solution_response_uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("UUID value is invalid") from exc
    raise ValueError("UUID value is invalid")


_SolutionResponseUUID = Annotated[UUID, BeforeValidator(_solution_response_uuid)]


def _solution_response_decimal(value):
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float)):
        raise ValueError("numeric value is invalid")
    try:
        result = Decimal(str(value))
    except (ValueError, TypeError) as exc:
        raise ValueError("numeric value is invalid") from exc
    if not result.is_finite():
        raise ValueError("numeric value is invalid")
    return result


_SolutionResponseDecimal = Annotated[Decimal, BeforeValidator(_solution_response_decimal)]


class SolutionRetirementCandidateItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    solution_id: _SolutionResponseUUID
    solution_name: str = Field(max_length=255)
    solution_type: str = Field(max_length=80)
    current_stage: str = Field(max_length=80)
    solution_status: str = Field(max_length=80)


class SolutionRetirementCandidatesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _SolutionResponseUUID
    offset: int = Field(ge=0, le=10000, strict=True)
    solutions: list[SolutionRetirementCandidateItemResponse] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(strict=True)

    @model_validator(mode="after")
    def validate_continuation(self):
        if self.has_more:
            if not self.solutions or self.next_offset != self.offset + len(self.solutions):
                raise ValueError("Retirement candidate continuation is inconsistent")
        elif self.next_offset is not None:
            raise ValueError("Terminal retirement candidate page cannot continue")
        return self


_SolutionStage = Literal[
    "discovered", "triaged", "framed", "experiment_ready", "testing",
    "validated", "investment_ready", "funded", "pilot_active",
    "adoption_ready", "adopting", "scaled", "maintained", "paused",
    "superseded", "retired", "failed",
]

_MAX_POSTGRES_BIGINT = 9_223_372_036_854_775_807
_SOLUTION_LIFECYCLE_MAX_OFFSET = 10_000
_SolutionLifecycleCount = Annotated[
    int,
    Field(ge=0, le=_MAX_POSTGRES_BIGINT, strict=True),
]


class _SolutionLifecycleCountSet(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class SolutionLifecycleStageCounts(_SolutionLifecycleCountSet):
    discovered: _SolutionLifecycleCount
    triaged: _SolutionLifecycleCount
    framed: _SolutionLifecycleCount
    experiment_ready: _SolutionLifecycleCount
    testing: _SolutionLifecycleCount
    validated: _SolutionLifecycleCount
    investment_ready: _SolutionLifecycleCount
    funded: _SolutionLifecycleCount
    pilot_active: _SolutionLifecycleCount
    adoption_ready: _SolutionLifecycleCount
    adopting: _SolutionLifecycleCount
    scaled: _SolutionLifecycleCount
    maintained: _SolutionLifecycleCount
    paused: _SolutionLifecycleCount
    superseded: _SolutionLifecycleCount
    retired: _SolutionLifecycleCount
    failed: _SolutionLifecycleCount


class SolutionLifecycleStatusCounts(_SolutionLifecycleCountSet):
    active: _SolutionLifecycleCount
    paused: _SolutionLifecycleCount
    retired: _SolutionLifecycleCount
    superseded: _SolutionLifecycleCount


class SolutionLifecycleGateStatusCounts(_SolutionLifecycleCountSet):
    draft: _SolutionLifecycleCount
    ready: _SolutionLifecycleCount
    approved: _SolutionLifecycleCount
    failed: _SolutionLifecycleCount
    retired: _SolutionLifecycleCount


class SolutionLifecycleLatestGateEvaluationCounts(_SolutionLifecycleCountSet):
    passed: _SolutionLifecycleCount
    failed: _SolutionLifecycleCount


class SolutionLifecycleExperimentStatusCounts(_SolutionLifecycleCountSet):
    draft: _SolutionLifecycleCount
    submitted: _SolutionLifecycleCount
    protocol_approved: _SolutionLifecycleCount
    baseline_ready: _SolutionLifecycleCount
    active: _SolutionLifecycleCount
    paused: _SolutionLifecycleCount
    completed: _SolutionLifecycleCount
    results_review: _SolutionLifecycleCount
    validated: _SolutionLifecycleCount
    invalidated: _SolutionLifecycleCount
    inconclusive: _SolutionLifecycleCount
    requires_replication: _SolutionLifecycleCount


class SolutionLifecycleExperimentResultCounts(_SolutionLifecycleCountSet):
    validated: _SolutionLifecycleCount
    invalidated: _SolutionLifecycleCount
    inconclusive: _SolutionLifecycleCount
    requires_replication: _SolutionLifecycleCount


class SolutionLifecycleReplicationStatusCounts(_SolutionLifecycleCountSet):
    proposed: _SolutionLifecycleCount
    approved: _SolutionLifecycleCount
    active: _SolutionLifecycleCount
    completed: _SolutionLifecycleCount
    failed: _SolutionLifecycleCount


class SolutionLifecycleFundingDecisionCounts(_SolutionLifecycleCountSet):
    draft: _SolutionLifecycleCount
    submitted: _SolutionLifecycleCount
    approved: _SolutionLifecycleCount
    rejected: _SolutionLifecycleCount
    closed: _SolutionLifecycleCount


class SolutionLifecycleAdoptionProgramStatusCounts(_SolutionLifecycleCountSet):
    draft: _SolutionLifecycleCount
    community_review: _SolutionLifecycleCount
    enablement_ready: _SolutionLifecycleCount
    launch: _SolutionLifecycleCount
    onboarding: _SolutionLifecycleCount
    active: _SolutionLifecycleCount
    paused: _SolutionLifecycleCount
    assessed: _SolutionLifecycleCount
    expand: _SolutionLifecycleCount
    redesign: _SolutionLifecycleCount
    retired: _SolutionLifecycleCount


class SolutionLifecycleConfigurationApprovalCounts(_SolutionLifecycleCountSet):
    draft: _SolutionLifecycleCount
    submitted: _SolutionLifecycleCount
    approved: _SolutionLifecycleCount
    rejected: _SolutionLifecycleCount


class SolutionLifecycleAdopterReadinessCounts(_SolutionLifecycleCountSet):
    not_ready: _SolutionLifecycleCount
    remediating: _SolutionLifecycleCount
    ready: _SolutionLifecycleCount
    expired: _SolutionLifecycleCount


class SolutionLifecycleScaleGateStatusCounts(_SolutionLifecycleCountSet):
    pending: _SolutionLifecycleCount
    passed: _SolutionLifecycleCount
    failed: _SolutionLifecycleCount
    waived: _SolutionLifecycleCount


class SolutionLifecycleLearningDecisionCounts(_SolutionLifecycleCountSet):
    proposed: _SolutionLifecycleCount
    accepted: _SolutionLifecycleCount
    rejected: _SolutionLifecycleCount
    applied: _SolutionLifecycleCount


class SolutionLifecycleRetirementStatusCounts(_SolutionLifecycleCountSet):
    proposed: _SolutionLifecycleCount
    impact_review: _SolutionLifecycleCount
    approved: _SolutionLifecycleCount
    migration: _SolutionLifecycleCount
    sunset: _SolutionLifecycleCount
    completed: _SolutionLifecycleCount
    rejected: _SolutionLifecycleCount


class SolutionLifecycleSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _SolutionResponseUUID
    solution_count: _SolutionLifecycleCount
    stage_counts: SolutionLifecycleStageCounts
    solution_status_counts: SolutionLifecycleStatusCounts
    stage_gate_status_counts: SolutionLifecycleGateStatusCounts
    latest_gate_evaluation_counts: SolutionLifecycleLatestGateEvaluationCounts
    experiment_status_counts: SolutionLifecycleExperimentStatusCounts
    experiment_result_counts: SolutionLifecycleExperimentResultCounts
    replication_status_counts: SolutionLifecycleReplicationStatusCounts
    funding_decision_counts: SolutionLifecycleFundingDecisionCounts
    adoption_program_status_counts: SolutionLifecycleAdoptionProgramStatusCounts
    configuration_approval_counts: SolutionLifecycleConfigurationApprovalCounts
    adopter_readiness_counts: SolutionLifecycleAdopterReadinessCounts
    scale_gate_status_counts: SolutionLifecycleScaleGateStatusCounts
    learning_decision_counts: SolutionLifecycleLearningDecisionCounts
    retirement_status_counts: SolutionLifecycleRetirementStatusCounts

    @model_validator(mode="after")
    def validate_solution_count_totals(self):
        if sum(self.stage_counts.model_dump().values()) != self.solution_count:
            raise ValueError("Solution lifecycle stage totals are inconsistent")
        if sum(self.solution_status_counts.model_dump().values()) != self.solution_count:
            raise ValueError("Solution lifecycle status totals are inconsistent")
        return self


class SolutionLifecycleExperimentItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    solution_id: _SolutionResponseUUID
    solution_name: str = Field(max_length=255)
    solution_type: Literal[
        "practice", "policy", "technology", "service", "governance",
        "business_model", "ecological_intervention", "data_product", "other",
    ]
    current_stage: _SolutionStage
    solution_status: Literal["active", "paused", "retired", "superseded"]
    experiment_id: _SolutionResponseUUID
    protocol_version: str = Field(max_length=40)
    experiment_status: Literal[
        "draft", "submitted", "protocol_approved", "baseline_ready", "active",
        "paused", "completed", "results_review", "validated", "invalidated",
        "inconclusive", "requires_replication",
    ]
    duration_days: int | None = Field(gt=0, le=2_147_483_647, strict=True)
    primary_metric_count: int | None = Field(
        ge=0, le=2_147_483_647, strict=True
    )
    secondary_metric_count: int | None = Field(
        ge=0, le=2_147_483_647, strict=True
    )
    experiment_created_at: AwareDatetime
    experiment_updated_at: AwareDatetime
    started_at: AwareDatetime | None
    completed_at: AwareDatetime | None
    latest_result_outcome: Literal[
        "validated", "invalidated", "inconclusive", "requires_replication"
    ] | None
    latest_result_reviewed_at: AwareDatetime | None

    @model_validator(mode="after")
    def validate_latest_result(self):
        if (self.latest_result_outcome is None) != (
            self.latest_result_reviewed_at is None
        ):
            raise ValueError("Latest experiment result fields are inconsistent")
        return self


class SolutionLifecycleExperimentPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _SolutionResponseUUID
    offset: int = Field(ge=0, le=10000, strict=True)
    experiments: list[SolutionLifecycleExperimentItemResponse] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)

    @model_validator(mode="after")
    def validate_continuation_and_order(self):
        if self.has_more:
            if not self.experiments or self.next_offset is None:
                raise ValueError("Solution experiment continuation is inconsistent")
        elif self.next_offset is not None:
            raise ValueError("Terminal solution experiment page cannot continue")
        seen_experiment_ids = set()
        previous = None
        for experiment in self.experiments:
            if experiment.experiment_id in seen_experiment_ids:
                raise ValueError("Solution experiment page contains a duplicate item")
            seen_experiment_ids.add(experiment.experiment_id)
            if previous is not None and (
                previous.experiment_created_at < experiment.experiment_created_at
                or (
                    previous.experiment_created_at == experiment.experiment_created_at
                    and previous.experiment_id.int > experiment.experiment_id.int
                )
            ):
                raise ValueError("Solution experiment page order is inconsistent")
            previous = experiment
        return self


class SolutionLifecycleFundingTargetItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    solution_id: _SolutionResponseUUID
    solution_name: str = Field(max_length=255)
    solution_type: Literal[
        "practice", "policy", "technology", "service", "governance",
        "business_model", "ecological_intervention", "data_product", "other",
    ]
    current_stage: _SolutionStage
    solution_status: Literal["active", "paused", "retired", "superseded"]


class SolutionLifecycleFundingTargetsPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _SolutionResponseUUID
    offset: int = Field(ge=0, le=10000, strict=True)
    solutions: list[SolutionLifecycleFundingTargetItemResponse] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)

    @model_validator(mode="after")
    def validate_continuation_and_identity(self):
        if self.has_more:
            if not self.solutions or self.next_offset is None:
                raise ValueError("Funding-target continuation is inconsistent")
        elif self.next_offset is not None:
            raise ValueError("Terminal funding-target page cannot continue")
        seen_solution_ids = set()
        previous = None
        for solution in self.solutions:
            if solution.solution_id in seen_solution_ids:
                raise ValueError("Funding-target page contains a duplicate solution")
            seen_solution_ids.add(solution.solution_id)
            if (
                previous is not None
                and previous.solution_name == solution.solution_name
                and previous.solution_id.int > solution.solution_id.int
            ):
                raise ValueError("Funding-target name tie-break order is inconsistent")
            previous = solution
        return self


class SolutionLifecycleGateItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    solution_id: _SolutionResponseUUID
    solution_name: str = Field(max_length=255)
    solution_type: Literal[
        "practice", "policy", "technology", "service", "governance",
        "business_model", "ecological_intervention", "data_product", "other",
    ]
    current_stage: _SolutionStage
    solution_status: Literal["active", "paused", "retired", "superseded"]
    gate_id: _SolutionResponseUUID
    from_stage: _SolutionStage
    to_stage: _SolutionStage
    gate_criterion: str | None = Field(max_length=4000)
    required_evidence_maturity: int | None = Field(
        default=None, ge=1, le=6, strict=True
    )
    required_experiment_count: int = Field(ge=0, strict=True)
    requires_human_approval: bool = Field(strict=True)
    gate_status: Literal["draft", "ready", "approved", "failed", "retired"]
    gate_created_at: AwareDatetime
    latest_evaluation_passed: bool | None = Field(strict=True)
    latest_evaluated_at: AwareDatetime | None

    @model_validator(mode="after")
    def validate_latest_evaluation(self):
        if (self.latest_evaluation_passed is None) != (
            self.latest_evaluated_at is None
        ):
            raise ValueError("Latest solution gate evaluation fields are inconsistent")
        return self


class SolutionLifecycleGatePageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _SolutionResponseUUID
    offset: int = Field(ge=0, le=10000, strict=True)
    gates: list[SolutionLifecycleGateItemResponse] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)

    @model_validator(mode="after")
    def validate_continuation(self):
        if self.has_more:
            if not self.gates or self.next_offset is None:
                raise ValueError("Solution gate continuation is inconsistent")
        elif self.next_offset is not None:
            raise ValueError("Terminal solution gate page cannot continue")
        seen_gate_ids = set()
        previous = None
        for gate in self.gates:
            if gate.gate_id in seen_gate_ids:
                raise ValueError("Solution gate page contains a duplicate gate")
            seen_gate_ids.add(gate.gate_id)
            if previous is not None and (
                previous.gate_created_at < gate.gate_created_at
                or (
                    previous.gate_created_at == gate.gate_created_at
                    and previous.gate_id.int > gate.gate_id.int
                )
            ):
                raise ValueError("Solution gate page order is inconsistent")
            previous = gate
        return self


class SolutionScaleGateAssessmentTargetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    solution_id: _SolutionResponseUUID
    solution_name: str = Field(max_length=255)
    scale_gate_id: _SolutionResponseUUID
    gate_type: Literal[
        "impact",
        "safety",
        "financial_sustainability",
        "operational_capacity",
        "supply_chain",
        "regulatory",
        "community_acceptance",
        "equity",
        "data_quality",
        "maintainability",
        "replicability",
    ]
    requirement: str = Field(max_length=2000)
    threshold: str | None = Field(max_length=1000)
    metric_key: str | None = Field(max_length=120)
    comparison_operator: Literal["lt", "lte", "eq", "gte", "gt"] | None
    threshold_numeric: _SolutionResponseDecimal | None
    unit: str | None = Field(max_length=50)
    minimum_sample: int | None = Field(gt=0, le=2_147_483_647, strict=True)
    gate_status: Literal["pending", "failed"]


class SolutionScaleGateAssessmentTargetsPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _SolutionResponseUUID
    offset: int = Field(ge=0, le=10000, strict=True)
    targets: list[SolutionScaleGateAssessmentTargetResponse] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)

    @model_validator(mode="after")
    def validate_continuation_and_order(self):
        if self.has_more:
            if not self.targets or self.next_offset is None:
                raise ValueError("Scale-gate target continuation is inconsistent")
        elif self.next_offset is not None:
            raise ValueError("Terminal scale-gate target page cannot continue")

        gate_ids = [target.scale_gate_id for target in self.targets]
        if gate_ids != sorted(set(gate_ids), key=lambda gate_id: gate_id.int):
            raise ValueError("Scale-gate target page order is inconsistent")
        return self


class SolutionLifecycleStageTransitionTargetItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    solution_id: _SolutionResponseUUID
    solution_name: str = Field(max_length=255)
    solution_type: Literal[
        "practice", "policy", "technology", "service", "governance",
        "business_model", "ecological_intervention", "data_product", "other",
    ]
    current_stage: _SolutionStage
    solution_status: Literal["active", "paused"]
    updated_at: AwareDatetime


class SolutionLifecycleStageTransitionTargetPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _SolutionResponseUUID
    offset: int = Field(ge=0, le=10000, strict=True)
    solutions: list[SolutionLifecycleStageTransitionTargetItemResponse] = Field(
        max_length=50
    )
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)

    @model_validator(mode="after")
    def validate_continuation(self):
        if self.has_more:
            if not self.solutions or self.next_offset is None:
                raise ValueError("Stage-transition target continuation is inconsistent")
        elif self.next_offset is not None:
            raise ValueError("Terminal stage-transition target page cannot continue")
        solution_ids = [solution.solution_id for solution in self.solutions]
        if len(solution_ids) != len(set(solution_ids)):
            raise ValueError("Stage-transition target page contains duplicate solutions")
        return self


class SolutionAdoptionProgramReviewQueueItemResponse(BaseModel):
    """Exact migration-520 projection for an independent adoption-program reviewer."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    program_id: _SolutionResponseUUID
    solution_id: _SolutionResponseUUID
    solution_name: str = Field(min_length=1, max_length=255, strict=True)
    program_status: Literal["community_review"]
    adoption_pathway: str = Field(min_length=1, max_length=2000, strict=True)
    local_adaptation_policy: str | None = Field(max_length=4000, strict=True)
    submitted_at: AwareDatetime
    consent_data_category: Literal["solution_adoption_participation"] | None
    consent_purpose: str | None = Field(min_length=1, max_length=255, strict=True)
    consent_version: str | None = Field(
        min_length=1,
        max_length=30,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,29}$",
        strict=True,
    )

    @model_validator(mode="after")
    def validate_consent_policy(self):
        consent_values = (
            self.consent_data_category,
            self.consent_purpose,
            self.consent_version,
        )
        if any(value is None for value in consent_values) and any(
            value is not None for value in consent_values
        ):
            raise ValueError("Adoption program consent policy projection is incomplete")
        return self


class SolutionAdoptionProgramReviewQueueResponse(BaseModel):
    """Strict, location-bound page envelope for the migration-520 queue."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _SolutionResponseUUID
    limit: int = Field(ge=1, le=25, strict=True)
    offset: int = Field(ge=0, le=_SOLUTION_LIFECYCLE_MAX_OFFSET, strict=True)
    programs: list[SolutionAdoptionProgramReviewQueueItemResponse] = Field(max_length=25)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(
        ge=0, le=_SOLUTION_LIFECYCLE_MAX_OFFSET, strict=True
    )
    offset_limited: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.programs) > self.limit:
            raise ValueError("Adoption program page exceeds its requested limit")
        if self.offset_limited:
            if (
                self.has_more
                or self.next_offset is not None
                or len(self.programs) != self.limit
                or self.offset + len(self.programs) <= _SOLUTION_LIFECYCLE_MAX_OFFSET
            ):
                raise ValueError("Adoption program offset-cap marker is inconsistent")
        elif self.has_more:
            if (
                len(self.programs) != self.limit
                or self.next_offset != self.offset + len(self.programs)
                or self.next_offset > _SOLUTION_LIFECYCLE_MAX_OFFSET
            ):
                raise ValueError("Adoption program continuation is inconsistent")
        elif self.next_offset is not None:
            raise ValueError("Terminal adoption program page cannot continue")

        program_ids = [program.program_id for program in self.programs]
        if len(program_ids) != len(set(program_ids)):
            raise ValueError("Adoption program page contains duplicate programs")
        order = [(program.submitted_at, program.program_id) for program in self.programs]
        if order != sorted(order):
            raise ValueError("Adoption program page is not in SQL order")
        return self


class SolutionAdoptionProgramDraftItemResponse(BaseModel):
    """Exact migration-520 projection for an operator's own adoption draft."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    program_id: _SolutionResponseUUID
    solution_id: _SolutionResponseUUID
    solution_name: str = Field(min_length=1, max_length=255, strict=True)
    program_status: Literal["draft"]
    adoption_pathway: str = Field(min_length=1, max_length=2000, strict=True)
    local_adaptation_policy: str | None = Field(max_length=4000, strict=True)
    created_at: AwareDatetime
    consent_data_category: Literal["solution_adoption_participation"] | None
    consent_purpose: str | None = Field(min_length=1, max_length=255, strict=True)
    consent_version: str | None = Field(
        min_length=1,
        max_length=30,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,29}$",
        strict=True,
    )

    @model_validator(mode="after")
    def validate_consent_policy(self):
        consent_values = (
            self.consent_data_category,
            self.consent_purpose,
            self.consent_version,
        )
        if any(value is None for value in consent_values) and any(
            value is not None for value in consent_values
        ):
            raise ValueError("Adoption program draft consent policy projection is incomplete")
        return self


class SolutionAdoptionProgramDraftPageResponse(BaseModel):
    """Strict, location-bound page envelope for migration-520 own drafts."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _SolutionResponseUUID
    limit: int = Field(ge=1, le=25, strict=True)
    offset: int = Field(ge=0, le=_SOLUTION_LIFECYCLE_MAX_OFFSET, strict=True)
    drafts: list[SolutionAdoptionProgramDraftItemResponse] = Field(max_length=25)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(
        ge=0, le=_SOLUTION_LIFECYCLE_MAX_OFFSET, strict=True
    )
    offset_limited: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.drafts) > self.limit:
            raise ValueError("Adoption program draft page exceeds its requested limit")
        if self.offset_limited:
            if (
                self.has_more
                or self.next_offset is not None
                or len(self.drafts) != self.limit
                or self.offset + len(self.drafts) <= _SOLUTION_LIFECYCLE_MAX_OFFSET
            ):
                raise ValueError("Adoption program draft offset-cap marker is inconsistent")
        elif self.has_more:
            if (
                len(self.drafts) != self.limit
                or self.next_offset != self.offset + len(self.drafts)
                or self.next_offset > _SOLUTION_LIFECYCLE_MAX_OFFSET
            ):
                raise ValueError("Adoption program draft continuation is inconsistent")
        elif self.next_offset is not None:
            raise ValueError("Terminal adoption program draft page cannot continue")

        program_ids = [draft.program_id for draft in self.drafts]
        if len(program_ids) != len(set(program_ids)):
            raise ValueError("Adoption program draft page contains duplicate programs")
        order = [(draft.created_at, -draft.program_id.int) for draft in self.drafts]
        if order != sorted(order, reverse=True):
            raise ValueError("Adoption program draft page is not in SQL order")
        return self


def register_solution_lifecycle_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.solution_lifecycle_actions import (
        SolutionLifecycleActionInvalid,
        activate_location_solution_replication,
        analyze_location_solution_experiment,
        apply_location_solution_learning,
        approve_location_solution_experiment_protocol,
        approve_location_solution_funding,
        approve_location_solution_funding_tranche,
        approve_location_solution_gate,
        approve_location_solution_retirement,
        complete_location_solution_experiment,
        configure_location_solution_adoption_consent_policy,
        create_location_solution,
        create_location_solution_adoption_program,
        create_location_solution_configuration_draft,
        create_location_solution_experiment,
        create_location_solution_gate,
        get_location_solution_adopter_readiness_review_queue,
        get_location_solution_adoption_program_drafts,
        get_location_solution_adoption_program_review_queue,
        get_location_solution_configuration_drafts,
        get_location_solution_configuration_review_queue,
        list_location_solution_adoption_program_redesigns,
        propose_location_solution_funding,
        propose_location_solution_learning,
        propose_location_solution_replication,
        propose_location_solution_replication_completion,
        propose_location_solution_retirement,
        record_location_solution_adoption_event,
        record_location_solution_experiment_observation,
        record_location_solution_gate_evaluation,
        review_location_solution_adopter_readiness,
        review_location_solution_adoption_program,
        review_location_solution_configuration,
        review_location_solution_experiment,
        review_location_solution_learning,
        review_location_solution_replication,
        review_location_solution_replication_completion,
        review_location_solution_scale_gate_assessment,
        revise_location_solution_adoption_program,
        start_location_solution_experiment,
        submit_location_solution_adopter_readiness,
        submit_location_solution_adoption_program,
        submit_location_solution_configuration,
        submit_location_solution_experiment_protocol,
        submit_location_solution_funding,
        submit_location_solution_scale_gate_assessment,
        transition_location_solution_gate,
        transition_location_solution_retirement,
        transition_location_solution_stage,
    )
    from services.gateway.solution_lifecycle_reads import (
        SolutionLifecycleReadInvalid,
        SolutionLifecycleRecordNotFound,
        SolutionLifecycleResponseTooLarge,
        SolutionLifecycleReviewNotFound,
        get_location_solution_adoption_event_summary,
        get_location_solution_experiment_protocol_review,
        get_location_solution_experiment_review,
        get_location_solution_funding_review_detail,
        get_location_solution_funding_tranche_review_detail,
        get_location_solution_gate_review,
        get_location_solution_learning_review_detail,
        get_location_solution_lifecycle_summary,
        get_location_solution_replication_completion_review_detail,
        get_location_solution_replication_review_detail,
        get_location_solution_retirement_review_detail,
        get_location_solution_scale_gate_review_detail,
        list_location_solution_adoption,
        list_location_solution_experiments,
        list_location_solution_funding,
        list_location_solution_funding_review_queue,
        list_location_solution_funding_targets,
        list_location_solution_gates,
        list_location_solution_learning,
        list_location_solution_learning_applications,
        list_location_solution_learning_review_queue,
        list_location_solution_replication_completion_review_queue,
        list_location_solution_replication_review_queue,
        list_location_solution_replications,
        list_location_solution_retirement_candidates,
        list_location_solution_retirement_review_queue,
        list_location_solution_retirements,
        list_location_solution_scale_gate_assessment_targets,
        list_location_solution_scale_gate_review_queue,
        list_location_solution_scale_gates,
        list_location_solution_stage_transition_targets,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.post("/operator/api/solution-lifecycle/{location_id}/solutions")
    async def create_solution(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "canonical_key", "name", "solution_type",
            "problem_statement", "rationale", "evidence", "acknowledged",
        }
        optional_fields = {
            "theory_of_change", "baseline_alternative", "risk_class", "reversibility",
        }
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Location solution fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_solution,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload["request_id"],
                payload["canonical_key"],
                payload["name"],
                payload["solution_type"],
                payload["problem_statement"],
                payload["rationale"],
                payload["evidence"],
                theory_of_change=payload.get("theory_of_change"),
                baseline_alternative=payload.get("baseline_alternative"),
                risk_class=payload.get("risk_class", "medium"),
                reversibility=payload.get("reversibility", "medium"),
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Location solution input is invalid"}, headers=headers)
            if code == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Solution key or request identifier already exists; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Location solution creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Location solution creation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/gates"
    )
    async def create_solution_gate(request: Request, location_id: str, solution_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "to_stage", "criterion", "required_experiment_count",
            "acknowledged",
        }
        optional_fields = {"required_evidence_maturity"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Location solution gate fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_solution_gate,
                request.state.operator_session.operator.operator_id,
                location_id,
                solution_id,
                payload["request_id"],
                payload["to_stage"],
                payload["criterion"],
                payload.get("required_evidence_maturity"),
                payload["required_experiment_count"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin active solution not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Location solution gate input is invalid"},
                    headers=headers,
                )
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "A gate already exists or the solution stage changed; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Location solution gate creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Location solution gate creation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/experiments"
    )
    async def create_solution_experiment(request: Request, location_id: str, solution_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "protocol", "acknowledged"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment protocol fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_solution_experiment,
                request.state.operator_session.operator.operator_id,
                location_id,
                solution_id,
                payload["request_id"],
                payload["protocol"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin solution not found"},
                    headers=headers,
                )
            if code == "55000":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The solution is not active and experiment-ready"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment protocol input is invalid"},
                    headers=headers,
                )
            if code == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Experiment request identifier already exists; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Location solution experiment creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Location solution experiment creation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/submit"
    )
    async def submit_solution_experiment_protocol(
        request: Request, location_id: str, experiment_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "acknowledged"}
        if (
            not isinstance(payload, dict)
            or set(payload) != required_fields
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment submission fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_solution_experiment_protocol,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle submit access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active location submit grant and protocol owner identity are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location experiment protocol not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment submission input is invalid"},
                    headers=headers,
                )
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "The experiment is no longer an eligible draft; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment protocol submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment protocol submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/evaluations"
    )
    async def record_solution_gate_evaluation(
        request: Request, location_id: str, gate_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "passed", "observed", "evidence"}
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution gate evaluation fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                record_location_solution_gate_evaluation,
                request.state.operator_session.operator.operator_id,
                location_id,
                gate_id,
                payload["request_id"],
                payload["passed"],
                payload["observed"],
                payload["evidence"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin solution gate not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution gate evaluation is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Solution gate changed; refresh and retry"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution gate evaluation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution gate evaluation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/review"
    )
    async def review_solution_gate_evaluation(
        request: Request, location_id: str, gate_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_gate_review,
                request.state.operator_session.operator.operator_id,
                location_id,
                gate_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReviewNotFound:
            return JSONResponse(
                status_code=404,
                content={"error": "Location-origin solution gate not found"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle review grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution gate review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution gate review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/approve"
    )
    async def approve_solution_gate(
        request: Request, location_id: str, gate_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution gate approval fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                approve_location_solution_gate,
                request.state.operator_session.operator.operator_id,
                location_id,
                gate_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active independent human reviewer with a current location review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin solution gate not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution gate approval request is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Gate is not eligible for approval; refresh and review the latest evaluation"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution gate approval unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution gate approval unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/gates/{gate_id}/transition"
    )
    async def transition_solution_gate(
        request: Request, location_id: str, gate_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {
            "request_id", "rationale", "evidence", "rollback_plan"
        }:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution gate transition fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_location_solution_gate,
                request.state.operator_session.operator.operator_id,
                location_id,
                gate_id,
                payload["request_id"],
                payload["rationale"],
                payload["evidence"],
                payload["rollback_plan"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle transition access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle transition grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin solution gate not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution gate transition request is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Gate prerequisites changed; refresh and review the latest lifecycle state"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution gate transition unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution gate transition unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/stage-transition"
    )
    async def transition_solution_stage(
        request: Request, location_id: str, solution_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "expected_from_stage", "to_stage", "rationale",
            "evidence", "rollback_plan", "acknowledged",
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution stage transition fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_location_solution_stage,
                request.state.operator_session.operator.operator_id,
                location_id,
                solution_id,
                payload["expected_from_stage"],
                payload["to_stage"],
                payload["request_id"],
                payload["rationale"],
                payload["evidence"],
                payload["rollback_plan"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle transition access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle transition grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin solution not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution stage transition request is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Solution stage changed or transition conflicts with lifecycle prerequisites; refresh and retry"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution stage transition unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution stage transition unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/summary",
        response_model=SolutionLifecycleSummaryResponse,
    )
    async def location_solution_lifecycle_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_lifecycle_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = SolutionLifecycleSummaryResponse.model_validate(result)
            if validated.location_id != UUID(location_id):
                raise ValueError("Solution lifecycle summary does not match request location")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Solution lifecycle summary unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="python")), headers=headers
        )

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/protocol-review"
    )
    async def review_solution_experiment_protocol_detail(
        request: Request, location_id: str, experiment_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_experiment_protocol_review,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReviewNotFound:
            return JSONResponse(
                status_code=404,
                content={"error": "Submitted exact-location experiment protocol not found"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Submitted exact-location experiment protocol not found"},
                    headers=headers,
                )
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle review grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment protocol review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment protocol review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/protocol-review"
    )
    async def approve_solution_experiment_protocol(
        request: Request, location_id: str, experiment_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Protocol approval fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                approve_location_solution_experiment_protocol,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active review grant and independent human reviewer are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Submitted exact-location experiment protocol not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Protocol approval request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "The protocol is no longer eligible for approval; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment protocol approval unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment protocol approval unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/start"
    )
    async def start_solution_experiment(
        request: Request, location_id: str, experiment_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment start fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                start_location_solution_experiment,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle transition access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active transition grant and human identity are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location experiment not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment start acknowledgement is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "The experiment is not eligible to start; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment start unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment start unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/observations"
    )
    async def record_solution_experiment_observation_route(
        request: Request, location_id: str, experiment_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "metric_key", "value", "arm", "adverse_event",
            "evidence", "acknowledged",
        }
        optional_fields = {"unit_ref", "participant_link_id"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or set(payload) - required_fields - optional_fields
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment observation fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                record_location_solution_experiment_observation,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["metric_key"],
                payload["value"],
                payload["arm"],
                payload.get("unit_ref"),
                payload["adverse_event"],
                payload["evidence"],
                payload.get("participant_link_id"),
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle collection access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active exact-location collection grant and current consent are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location active experiment not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment observation input is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Experiment observation is not eligible; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment observation capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment observation capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 200 if result.get("replayed") else 201
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/analyze"
    )
    async def analyze_solution_experiment_route(
        request: Request, location_id: str, experiment_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "metric_key", "acknowledged"}
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment analysis fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                analyze_location_solution_experiment,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["metric_key"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle analysis access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active exact-location analysis grant and current observation consent are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location active experiment not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment analysis input or protocol settings are invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Experiment analysis is not eligible; refresh and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment analysis unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment analysis unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 200 if result.get("replayed") else 201
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/complete"
    )
    async def complete_solution_experiment_route(
        request: Request, location_id: str, experiment_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "acknowledged"}
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Experiment completion fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                complete_location_solution_experiment,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle transition access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "Active exact-location transition and analyze grants are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location active experiment not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Experiment completion request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Experiment is not at a current approved stopping boundary; refresh analysis and retry"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Experiment completion unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Experiment completion unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 200 if result.get("replayed") else 201
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/review"
    )
    async def review_solution_experiment_detail(
        request: Request, location_id: str, experiment_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_experiment_review,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active human with a current exact location review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Pending exact-location experiment review was not found"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution experiment review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution experiment review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/experiments/{experiment_id}/review"
    )
    async def submit_solution_experiment_review(
        request: Request, location_id: str, experiment_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "outcome", "primary_results", "secondary_results",
            "limitations", "evidence",
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution experiment review fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_solution_experiment,
                request.state.operator_session.operator.operator_id,
                location_id,
                experiment_id,
                payload["request_id"],
                payload["outcome"],
                payload["primary_results"],
                payload["secondary_results"],
                payload["limitations"],
                payload["evidence"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active human distinct from the experiment owner and protocol approver with a current location review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location solution experiment was not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution experiment review request is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Experiment is no longer eligible for review; refresh the lifecycle view"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution experiment result review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution experiment result review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/adoption/programs"
    )
    async def create_solution_adoption_program(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "solution_id", "adoption_pathway", "acknowledged",
            "consent_purpose", "consent_version",
        }
        optional_fields = {"local_adaptation_policy"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Location adoption program fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_solution_adoption_program,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload["solution_id"],
                payload["request_id"],
                payload["adoption_pathway"],
                consent_purpose=payload["consent_purpose"],
                consent_version=payload["consent_version"],
                local_adaptation_policy=payload.get("local_adaptation_policy"),
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Location adoption program input is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001", "23514"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "The adoption program is no longer eligible; refresh the lifecycle view"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption program creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution adoption program creation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/adoption/programs/{program_id}/consent-policy"
    )
    async def configure_solution_adoption_consent_policy(
        request: Request, location_id: str, program_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {
            "request_id", "consent_purpose", "consent_version", "acknowledged",
        }:
            return JSONResponse(status_code=400, content={"error": "Adoption consent policy fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                configure_location_solution_adoption_consent_policy,
                request.state.operator_session.operator.operator_id,
                location_id,
                program_id,
                payload["request_id"],
                payload["consent_purpose"],
                payload["consent_version"],
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle create access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current exact-location solution lifecycle create grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Exact-location adoption program was not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Adoption consent policy input is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001", "23514"}:
                return JSONResponse(status_code=409, content={"error": "The adoption consent policy is already set or the draft is no longer eligible"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption consent policy unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Adoption consent policy configuration unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/adoption/programs/drafts",
        response_model=SolutionAdoptionProgramDraftPageResponse,
    )
    async def location_solution_adoption_program_drafts(
        request: Request,
        location_id: str,
        limit: int = Query(default=10, ge=1, le=25),
        offset: int = Query(default=0, ge=0, le=_SOLUTION_LIFECYCLE_MAX_OFFSET),
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_solution_adoption_program_drafts,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=int(limit),
                offset=int(offset),
            )
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Adoption program draft page is invalid"}, headers=headers)
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle submit access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle submit grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption program drafts unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution adoption program drafts unavailable"}, headers={**headers, "Retry-After": "30"})
        try:
            if not isinstance(result, dict):
                raise ValueError("Adoption program draft result is not an object")
            page = {
                **result,
                "location_id": location_id,
                "limit": limit,
                "offset": offset,
                "offset_limited": False,
            }
            next_offset = result.get("next_offset")
            if (
                result.get("has_more") is True
                and type(next_offset) is int
                and next_offset > _SOLUTION_LIFECYCLE_MAX_OFFSET
            ):
                drafts = result.get("drafts")
                if (
                    not isinstance(drafts, list)
                    or len(drafts) != limit
                    or next_offset != offset + len(drafts)
                ):
                    raise ValueError("Adoption program draft continuation is inconsistent")
                page["has_more"] = False
                page["next_offset"] = None
                page["offset_limited"] = True
            validated = SolutionAdoptionProgramDraftPageResponse.model_validate(page)
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption program draft response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Solution adoption program drafts unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="python")), headers=headers
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/adoption/programs/redesigns")
    async def location_solution_adoption_program_redesigns(
        request: Request, location_id: str, limit: int = Query(default=25, ge=1, le=50), offset: int = Query(default=0, ge=0, le=10000)
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                list_location_solution_adoption_program_redesigns,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=int(limit),
                offset=int(offset),
            )
        except (TypeError, ValueError):
            return JSONResponse(status_code=400, content={"error": "Adoption program revision page is invalid"}, headers=headers)
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle create access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle create grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption program redesigns unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Adoption program redesigns unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/solution-lifecycle/{location_id}/adoption/programs/{program_id}/revise")
    async def revise_solution_adoption_program(request: Request, location_id: str, program_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "adoption_pathway", "acknowledged",
            "consent_purpose", "consent_version",
        }
        optional_fields = {"local_adaptation_policy"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(status_code=400, content={"error": "Adoption program revision fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                revise_location_solution_adoption_program,
                request.state.operator_session.operator.operator_id,
                location_id,
                program_id,
                payload["request_id"],
                payload["adoption_pathway"],
                consent_purpose=payload["consent_purpose"],
                consent_version=payload["consent_version"],
                local_adaptation_policy=payload.get("local_adaptation_policy"),
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle create access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle create grant is required"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Adoption program revision input is invalid"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Exact-location redesigned adoption program not found"}, headers=headers)
            if code in {"23505", "55000", "40001", "23514"}:
                return JSONResponse(status_code=409, content={"error": "The adoption program is no longer eligible for revision; refresh the lifecycle view"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption program revision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Adoption program revision unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post("/operator/api/solution-lifecycle/{location_id}/adoption/programs/{program_id}/submit")
    async def submit_solution_adoption_program(request: Request, location_id: str, program_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(status_code=400, content={"error": "Adoption program submission fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                submit_location_solution_adoption_program,
                request.state.operator_session.operator.operator_id,
                location_id,
                program_id,
                payload["request_id"],
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle submit access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle submit grant is required"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Adoption program submission input is invalid"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Exact-location adoption program not found"}, headers=headers)
            if code in {"23505", "55000", "40001", "23514"}:
                return JSONResponse(status_code=409, content={"error": "Adoption program is no longer eligible; refresh the lifecycle view"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption program submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution adoption program submission unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/adoption/programs/review-queue",
        response_model=SolutionAdoptionProgramReviewQueueResponse,
    )
    async def location_solution_adoption_program_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=10, ge=1, le=25),
        offset: int = Query(default=0, ge=0, le=_SOLUTION_LIFECYCLE_MAX_OFFSET),
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_solution_adoption_program_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=int(limit),
                offset=int(offset),
            )
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Adoption program review page is invalid"}, headers=headers)
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption program review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution adoption program review queue unavailable"}, headers={**headers, "Retry-After": "30"})
        try:
            if not isinstance(result, dict):
                raise ValueError("Adoption program review result is not an object")
            page = {
                **result,
                "location_id": location_id,
                "limit": limit,
                "offset": offset,
                "offset_limited": False,
            }
            next_offset = result.get("next_offset")
            if result.get("has_more") is True and type(next_offset) is int and (
                next_offset > _SOLUTION_LIFECYCLE_MAX_OFFSET
            ):
                programs = result.get("programs")
                if (
                    not isinstance(programs, list)
                    or len(programs) != limit
                    or next_offset != offset + len(programs)
                ):
                    raise ValueError("Adoption program continuation is inconsistent")
                page["has_more"] = False
                page["next_offset"] = None
                page["offset_limited"] = True
            validated = SolutionAdoptionProgramReviewQueueResponse.model_validate(page)
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption program review response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Solution adoption program review queue unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(validated.model_dump(mode="python")), headers=headers)

    @router.post("/operator/api/solution-lifecycle/{location_id}/adoption/programs/{program_id}/review")
    async def review_solution_adoption_program(request: Request, location_id: str, program_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {
            "request_id", "decision", "review_note", "acknowledged",
        }:
            return JSONResponse(status_code=400, content={"error": "Adoption program review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_adoption_program,
                request.state.operator_session.operator.operator_id,
                location_id,
                program_id,
                payload["request_id"],
                payload["decision"],
                payload["review_note"],
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current independent location review grant is required"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Adoption program review input is invalid"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Exact-location adoption program not found"}, headers=headers)
            if code in {"23505", "55000", "40001", "23514"}:
                return JSONResponse(status_code=409, content={"error": "Adoption program is no longer eligible; refresh the review queue"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption program review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution adoption program review unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers)

    @router.post("/operator/api/solution-lifecycle/{location_id}/adoption/readiness")
    async def submit_solution_adopter_readiness(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "solution_id", "current_level", "required_level", "acknowledged",
        }
        optional_fields = {"remediation_plan"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(status_code=400, content={"error": "Readiness assessment fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                submit_location_solution_adopter_readiness,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload["solution_id"],
                payload["request_id"],
                payload["current_level"],
                payload["required_level"],
                remediation_plan=payload.get("remediation_plan"),
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle create access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle create grant is required"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Readiness assessment input is invalid"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Active location-origin solution not found"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "The readiness assessment is no longer current; refresh the lifecycle view"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption readiness submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution adoption readiness submission unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/adoption/readiness/review-queue")
    async def solution_adopter_readiness_review_queue(
        request: Request, location_id: str, limit: int = Query(default=25, ge=1, le=100), offset: int = Query(default=0, ge=0, le=10000)
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_solution_adopter_readiness_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=int(limit),
                offset=int(offset),
            )
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Readiness review page is invalid"}, headers=headers)
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption readiness review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution adoption readiness review queue unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/solution-lifecycle/{location_id}/adoption/readiness/{assessment_id}/review")
    async def review_solution_adopter_readiness(request: Request, location_id: str, assessment_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "decision", "review_note", "acknowledged"}
        if (
            not isinstance(payload, dict)
            or set(payload) != required_fields
        ):
            return JSONResponse(status_code=400, content={"error": "Readiness review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_adopter_readiness,
                request.state.operator_session.operator.operator_id,
                location_id,
                assessment_id,
                payload["request_id"],
                payload["decision"],
                payload["review_note"],
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current independent location review grant is required"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Readiness review input is invalid"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Location readiness assessment not found"}, headers=headers)
            if code in {"23505", "55000", "40001", "23514"}:
                return JSONResponse(status_code=409, content={"error": "The readiness assessment is no longer eligible; refresh the review queue"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption readiness review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution adoption readiness review unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers)

    @router.post("/operator/api/solution-lifecycle/{location_id}/adoption/configurations")
    async def create_solution_configuration_draft(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        fields = {
            "request_id", "solution_id", "invariant_components",
            "configurable_components", "prohibited_components", "local_assumptions",
            "comparability_class", "evidence_impact", "acknowledged",
        }
        if not isinstance(payload, dict) or set(payload) != fields:
            return JSONResponse(status_code=400, content={"error": "Configuration draft fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                create_location_solution_configuration_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload["solution_id"],
                payload["request_id"],
                payload["invariant_components"],
                payload["configurable_components"],
                payload["prohibited_components"],
                payload["local_assumptions"],
                payload["comparability_class"],
                payload["evidence_impact"],
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle create access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle create grant is required"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Configuration draft input is invalid"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Active location-origin solution not found"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Configuration draft is no longer eligible; refresh the lifecycle view"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution configuration draft creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution configuration draft creation unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/adoption/configurations/drafts")
    async def location_solution_configuration_drafts(
        request: Request, location_id: str, limit: int = Query(default=10, ge=1, le=25), offset: int = Query(default=0, ge=0, le=10000)
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_solution_configuration_drafts,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=int(limit),
                offset=int(offset),
            )
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Configuration draft page is invalid"}, headers=headers)
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle submit access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle submit grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution configuration draft list unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution configuration draft list unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/solution-lifecycle/{location_id}/adoption/configurations/{configuration_id}/submit")
    async def submit_solution_configuration(request: Request, location_id: str, configuration_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(status_code=400, content={"error": "Configuration submission fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                submit_location_solution_configuration,
                request.state.operator_session.operator.operator_id,
                location_id,
                configuration_id,
                payload["request_id"],
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle submit access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle submit grant is required"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Configuration submission input is invalid"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Location configuration draft not found"}, headers=headers)
            if code in {"23505", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Configuration draft is no longer eligible; refresh the lifecycle view"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution configuration submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution configuration submission unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/adoption/configurations/review-queue")
    async def location_solution_configuration_review_queue(
        request: Request, location_id: str, limit: int = Query(default=10, ge=1, le=25), offset: int = Query(default=0, ge=0, le=10000)
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_solution_configuration_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=int(limit),
                offset=int(offset),
            )
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Configuration review page is invalid"}, headers=headers)
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "A current location solution lifecycle review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution configuration review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution configuration review queue unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/solution-lifecycle/{location_id}/adoption/configurations/{configuration_id}/review")
    async def review_solution_configuration(request: Request, location_id: str, configuration_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {
            "request_id", "decision", "review_note", "acknowledged",
        }:
            return JSONResponse(status_code=400, content={"error": "Configuration review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_configuration,
                request.state.operator_session.operator.operator_id,
                location_id,
                configuration_id,
                payload["request_id"],
                payload["decision"],
                payload["review_note"],
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current independent location review grant is required"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Configuration review input is invalid"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Location configuration not found"}, headers=headers)
            if code in {"23505", "55000", "40001", "23514"}:
                return JSONResponse(status_code=409, content={"error": "Configuration is no longer eligible; refresh the review queue"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution configuration review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution configuration review unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/adoption")
    async def location_solution_lifecycle_adoption(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_adoption,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle adoption unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle adoption unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/adoption/{program_id}/events"
    )
    async def location_solution_lifecycle_adoption_event_summary(
        request: Request, location_id: str, program_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_adoption_event_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
                program_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleRecordNotFound:
            return JSONResponse(
                status_code=404,
                content={"error": "Exact-location adoption program was not found"},
                headers=headers,
            )
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location adoption program was not found"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption event summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution adoption event summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/adoption/programs/{program_id}/events"
    )
    async def capture_location_solution_adoption_event(
        request: Request, location_id: str, program_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "participant_ref", "event_type", "acknowledged",
        }
        optional_fields = {"fidelity_score"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Adoption event fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                record_location_solution_adoption_event,
                request.state.operator_session.operator.operator_id,
                location_id,
                program_id,
                payload["request_id"],
                payload["participant_ref"],
                payload["event_type"],
                fidelity_score=payload.get("fidelity_score"),
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle collect access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact-location participant consent grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Exact-location adoption program or participant reference was not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Adoption event input is invalid"}, headers=headers)
            if code in {"23505", "55000", "40001", "23514"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "The adoption program or participant consent is no longer eligible"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution adoption event capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution adoption event capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/scale-gates")
    async def location_solution_scale_gates(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_scale_gates,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution scale-gate read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution scale-gate read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/scale-gates/assessment-targets",
        response_model=SolutionScaleGateAssessmentTargetsPageResponse,
    )
    async def location_solution_scale_gate_assessment_targets(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                list_location_solution_scale_gate_assessment_targets,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified assessment access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location create grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate assessment targets unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Scale-gate assessment targets unavailable"}, headers={**headers, "Retry-After": "30"})
        try:
            validated = SolutionScaleGateAssessmentTargetsPageResponse.model_validate(
                result
            )
            if (
                validated.location_id != UUID(location_id)
                or validated.offset != offset
                or len(validated.targets) > limit
                or (
                    validated.has_more
                    and (
                        len(validated.targets) != limit
                        or validated.next_offset != offset + limit
                    )
                )
            ):
                raise ValueError("Scale-gate targets do not match request scope or bounds")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate target response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Scale-gate assessment targets unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="python")), headers=headers
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/scale-gates/{gate_id}/evaluations"
    )
    async def submit_solution_scale_gate_assessment(
        request: Request, location_id: str, gate_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "measured_value", "sample_size", "reported_pass",
            "evidence_refs", "acknowledged",
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(status_code=400, content={"error": "Scale-gate assessment fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                submit_location_solution_scale_gate_assessment,
                request.state.operator_session.operator.operator_id,
                location_id,
                gate_id,
                payload["request_id"],
                payload["measured_value"],
                payload["sample_size"],
                payload["reported_pass"],
                payload["evidence_refs"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified scale-gate assessment access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location create grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Scale gate not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Scale-gate assessment input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Scale gate already has a pending assessment or the request conflicts"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate assessment unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Scale-gate assessment unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/scale-gates/review")
    async def location_solution_scale_gate_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                list_location_solution_scale_gate_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified scale-gate review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Scale-gate review queue unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/scale-gates/review/{assessment_id}"
    )
    async def location_solution_scale_gate_review_detail(
        request: Request, location_id: str, assessment_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_solution_scale_gate_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                assessment_id,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified scale-gate review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Scale-gate review detail unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/scale-gates/review/{assessment_id}"
    )
    async def review_solution_scale_gate_assessment(
        request: Request, location_id: str, assessment_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "decision", "review_reason", "acknowledged"}
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(status_code=400, content={"error": "Scale-gate review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_scale_gate_assessment,
                request.state.operator_session.operator.operator_id,
                location_id,
                assessment_id,
                payload["request_id"],
                payload["decision"],
                payload["review_reason"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified scale-gate review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An active independent human location review grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Pending scale-gate assessment not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Scale-gate review input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Scale-gate assessment was already reviewed or the request conflicts"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Scale-gate review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Scale-gate review unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/replications")
    async def location_solution_replications(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_replications,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/replications/review")
    async def location_solution_replication_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_replication_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/review")
    async def location_solution_replication_review_detail(
        request: Request, location_id: str, replication_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_replication_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/review")
    async def review_solution_replication(request: Request, location_id: str, replication_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "decision", "acknowledged"}
        optional_fields = {"review_reason"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(status_code=400, content={"error": "Replication review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_replication,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                payload["request_id"],
                payload["decision"],
                payload.get("review_reason"),
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An independent human with an active location review grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Pending attributed replication proposal not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Replication review input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Replication proposal has already been reviewed or changed"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/replications/completion-review"
    )
    async def location_solution_replication_completion_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_replication_completion_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Replication completion review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Replication completion review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/completion-proposals/{proposal_id}/review"
    )
    async def location_solution_replication_completion_review_detail(
        request: Request,
        location_id: str,
        replication_id: str,
        proposal_id: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_replication_completion_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                proposal_id,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Replication completion review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Replication completion review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/completion-proposals/{proposal_id}/review"
    )
    async def review_solution_replication_completion(
        request: Request,
        location_id: str,
        replication_id: str,
        proposal_id: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "decision", "acknowledged"}
        optional_fields = {"review_reason"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(status_code=400, content={"error": "Completion review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_replication_completion,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                proposal_id,
                payload["request_id"],
                payload["decision"],
                payload.get("review_reason"),
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An independent human with an active location review grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Pending completion report with current source lineage not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Completion review input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Completion report has already been reviewed or changed"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Replication completion review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Replication completion review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/start"
    )
    async def start_solution_replication(
        request: Request, location_id: str, replication_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Replication activation fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                activate_location_solution_replication,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                payload["request_id"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle transition access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active human with a current location transition grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Independently approved replication not found for this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Replication activation input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Replication cannot be started in its current state"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication activation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication activation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/completion-proposals"
    )
    async def propose_solution_replication_completion(
        request: Request, location_id: str, replication_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "outcome", "evidence_maturity", "outcome_summary", "evidence", "acknowledged"
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Replication completion proposal fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_solution_replication_completion,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                payload["request_id"],
                payload["outcome"],
                payload["evidence_maturity"],
                payload["outcome_summary"],
                payload["evidence"],
                acknowledged=payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle submit access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active human with a current location submit grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Started replication not found for this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Replication completion proposal is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001", "55P03"}:
                return JSONResponse(status_code=409, content={"error": "A completion proposal is already pending or this replication changed"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication completion proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication completion proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/learning")
    async def location_solution_learning(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_learning,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/replications/{replication_id}/learning"
    )
    async def propose_solution_learning(
        request: Request, location_id: str, replication_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "lesson_type", "finding", "recommended_action", "evidence"
        }
        optional_fields = {
            "confidence", "transferability", "affected_assumptions", "affected_metrics"
        }
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Learning proposal fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_solution_learning,
                request.state.operator_session.operator.operator_id,
                location_id,
                replication_id,
                payload["request_id"],
                payload["lesson_type"],
                payload["finding"],
                payload["recommended_action"],
                payload["evidence"],
                confidence=payload.get("confidence", "moderate"),
                transferability=payload.get("transferability", "unknown"),
                affected_assumptions=payload.get("affected_assumptions", []),
                affected_metrics=payload.get("affected_metrics", []),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Completed reviewed replication not found in this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Learning proposal input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Learning proposal conflicts with current state"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/learning/application")
    async def location_solution_learning_application_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_learning_applications,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified application access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location apply grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning application queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning application queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/learning/{learning_record_id}/apply"
    )
    async def apply_solution_learning(
        request: Request, location_id: str, learning_record_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "applied_to_version", "acknowledged"}
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Learning application fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                apply_location_solution_learning,
                request.state.operator_session.operator.operator_id,
                location_id,
                learning_record_id,
                payload["request_id"],
                payload["applied_to_version"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified application access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location apply grant distinct from the reviewer is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Accepted learning with current source lineage not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Learning application input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Learning record is already applied or its application request conflicts"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning application unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning application unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/learning/review")
    async def location_solution_learning_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_learning_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/learning/{learning_record_id}/review"
    )
    async def location_solution_learning_review_detail(
        request: Request, location_id: str, learning_record_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_learning_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                learning_record_id,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(status_code=403, content={"error": "An active human location review grant is required"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/learning/{learning_record_id}/review"
    )
    async def review_solution_learning(
        request: Request, location_id: str, learning_record_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {"request_id", "decision", "acknowledged"}
        optional_fields = {"review_reason"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(status_code=400, content={"error": "Learning review fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                review_location_solution_learning,
                request.state.operator_session.operator.operator_id,
                location_id,
                learning_record_id,
                payload["request_id"],
                payload["decision"],
                payload.get("review_reason"),
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An independent human with an active location review grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Pending learning proposal with current source lineage not found for this location"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Learning review input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Learning proposal has already been reviewed or changed"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution learning review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution learning review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post("/operator/api/solution-lifecycle/{location_id}/replications")
    async def propose_solution_replication(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "source_experiment_id", "target_context", "replication_protocol"
        }
        optional_fields = {"adaptation_required"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(required_fields | optional_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Replication proposal fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_solution_replication,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload["source_experiment_id"],
                payload["request_id"],
                payload["target_context"],
                payload.get("adaptation_required"),
                payload["replication_protocol"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Validated source experiment not found for this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Replication proposal input is invalid"},
                    headers=headers,
                )
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Replication proposal conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution replication proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution replication proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/retirements")
    async def location_solution_retirements(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_retirements,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/retirement-candidates",
        response_model=SolutionRetirementCandidatesResponse,
    )
    async def location_solution_retirement_candidates(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_retirement_candidates,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement candidate read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement candidate read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = SolutionRetirementCandidatesResponse.model_validate(result)
            if (
                page.location_id != UUID(location_id)
                or page.offset != offset
                or len(page.solutions) > limit
                or (page.has_more and len(page.solutions) != limit)
            ):
                raise ValueError("Retirement candidate page does not match request bounds")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement candidate response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Solution retirement candidate read unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/solution-lifecycle/{location_id}/retirements/review")
    async def location_solution_retirement_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_retirement_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle review grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/retirements/review/{retirement_id}"
    )
    async def location_solution_retirement_review_detail(
        request: Request, location_id: str, retirement_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_retirement_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                retirement_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReviewNotFound:
            return JSONResponse(
                status_code=404,
                content={"error": "Pending location-origin retirement review was not found"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle review grant is required"},
                    headers=headers,
                )
            if getattr(exc, "pgcode", None) == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Pending location-origin retirement review was not found"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/retirements"
    )
    async def propose_solution_retirement(
        request: Request, location_id: str, solution_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "retirement_type", "trigger_reason", "evidence_refs", "migration_plan"
        }
        allowed_fields = required_fields | {"replacement_solution_id"}
        if (
            not isinstance(payload, dict)
            or not required_fields.issubset(payload)
            or not set(payload).issubset(allowed_fields)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Retirement proposal fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_solution_retirement,
                request.state.operator_session.operator.operator_id,
                location_id,
                solution_id,
                payload["request_id"],
                payload["retirement_type"],
                payload["trigger_reason"],
                payload["evidence_refs"],
                payload["migration_plan"],
                payload.get("replacement_solution_id"),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle create access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Location solution not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Retirement proposal input is invalid"}, headers=headers)
            if code in {"23505", "23514", "55000", "40001"}:
                return JSONResponse(status_code=409, content={"error": "Retirement proposal conflicts with current state"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result), status_code=200 if result.get("replayed") else 201, headers=headers
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/approve"
    )
    async def approve_solution_retirement(
        request: Request, location_id: str, retirement_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Retirement approval must contain only request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                approve_location_solution_retirement,
                request.state.operator_session.operator.operator_id,
                location_id,
                retirement_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Retirement not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Retirement approval request is invalid"}, headers=headers)
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(status_code=409, content={"error": "Retirement state conflicts with approval"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement approval unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement approval unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    async def _transition_solution_retirement(
        request: Request, location_id: str, retirement_id: str, action: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "note", "evidence_refs", "effective_at", "acknowledged"
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Retirement transition fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_location_solution_retirement,
                request.state.operator_session.operator.operator_id,
                location_id,
                retirement_id,
                payload["request_id"],
                action,
                payload["note"],
                payload["evidence_refs"],
                payload["effective_at"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution retirement transition access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current active-human location transition or review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Retirement not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Retirement transition input is invalid"}, headers=headers)
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(status_code=409, content={"error": "Retirement is not eligible for this transition"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution retirement transition unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution retirement transition unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/migration"
    )
    async def begin_solution_retirement_migration(
        request: Request, location_id: str, retirement_id: str
    ):
        return await _transition_solution_retirement(
            request, location_id, retirement_id, "migration_started"
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/sunset"
    )
    async def sunset_location_solution_retirement(
        request: Request, location_id: str, retirement_id: str
    ):
        return await _transition_solution_retirement(
            request, location_id, retirement_id, "sunset"
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/retirements/{retirement_id}/post-retirement-review"
    )
    async def complete_location_solution_retirement_review(
        request: Request, location_id: str, retirement_id: str
    ):
        return await _transition_solution_retirement(
            request, location_id, retirement_id, "post_retirement_review"
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/funding")
    async def location_solution_lifecycle_funding(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_funding,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle funding unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle funding unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/funding/targets",
        response_model=SolutionLifecycleFundingTargetsPageResponse,
    )
    async def location_solution_funding_targets(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_funding_targets,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution-lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding targets unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding targets unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = SolutionLifecycleFundingTargetsPageResponse.model_validate(result)
            expected_location = UUID(location_id)
            expected_next_offset = offset + limit if validated.has_more else None
            if (
                validated.location_id != expected_location
                or validated.offset != offset
                or validated.next_offset != expected_next_offset
                or len(validated.solutions) > limit
            ):
                raise ValueError("Funding-target response does not match request bounds")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding target response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Solution funding targets unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="python")), headers=headers
        )

    @router.get("/operator/api/solution-lifecycle/{location_id}/funding/review")
    async def location_solution_funding_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_funding_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact-location solution lifecycle review grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/review"
    )
    async def location_solution_funding_review_detail(
        request: Request, location_id: str, funding_case_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_funding_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                funding_case_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound:
            return JSONResponse(status_code=404, content={"error": "Funding review case not found"}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact-location solution lifecycle review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Funding review case not found"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding review detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding review detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/tranches/{tranche_id}/review"
    )
    async def location_solution_funding_tranche_review_detail(
        request: Request, location_id: str, funding_case_id: str, tranche_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_solution_funding_tranche_review_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                funding_case_id,
                tranche_id,
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle review access is required"}, headers=headers)
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleReviewNotFound:
            return JSONResponse(status_code=404, content={"error": "Funding tranche was not found"}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "A current exact-location funding review grant is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Funding tranche was not found"}, headers=headers)
            if code == "54000":
                return JSONResponse(status_code=413, content={"error": "Funding tranche review terms exceed the allowed size"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding tranche review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution funding tranche review unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/approve"
    )
    async def approve_solution_funding(
        request: Request, location_id: str, funding_case_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution funding approval fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                approve_location_solution_funding,
                request.state.operator_session.operator.operator_id,
                location_id,
                funding_case_id,
                payload["request_id"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle review access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active independent human with a current location review grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Submitted funding case was not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution funding approval is invalid"}, headers=headers)
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Funding case is no longer eligible for approval"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding approval unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding approval unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/tranches/{tranche_id}/approve"
    )
    async def approve_solution_funding_tranche_route(
        request: Request, location_id: str, funding_case_id: str, tranche_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(status_code=400, content={"error": "Solution tranche approval fields are invalid"}, headers=headers)
        try:
            result = await run_in_threadpool(
                approve_location_solution_funding_tranche,
                request.state.operator_session.operator.operator_id,
                location_id,
                funding_case_id,
                tranche_id,
                payload["request_id"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(status_code=403, content={"error": "Tenant-qualified solution lifecycle review access is required"}, headers=headers)
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(status_code=403, content={"error": "An active independent human distinct from the submitter and case approver is required"}, headers=headers)
            if code == "P0002":
                return JSONResponse(status_code=404, content={"error": "Funding tranche was not found"}, headers=headers)
            if code == "22023":
                return JSONResponse(status_code=400, content={"error": "Solution funding tranche approval is invalid"}, headers=headers)
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(status_code=409, content={"error": "Funding case or tranche is no longer eligible for approval"}, headers=headers)
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding tranche approval unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=503, content={"error": "Solution funding tranche approval unavailable"}, headers={**headers, "Retry-After": "30"})
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/funding"
    )
    async def propose_solution_funding(
        request: Request, location_id: str, solution_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        required_fields = {
            "request_id", "capital_stage", "funding_instrument", "requested_amount",
            "minimum_viable_amount", "maximum_authorized_amount", "currency",
            "risk_adjusted_expected_value", "public_goods_value", "community_share",
            "downside_exposure", "rationale", "evidence", "tranches",
        }
        if not isinstance(payload, dict) or set(payload) != required_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution funding proposal fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_location_solution_funding,
                request.state.operator_session.operator.operator_id,
                location_id,
                solution_id,
                payload["request_id"],
                payload["capital_stage"],
                payload["funding_instrument"],
                payload["requested_amount"],
                payload["minimum_viable_amount"],
                payload["maximum_authorized_amount"],
                payload["currency"],
                payload["risk_adjusted_expected_value"],
                payload["public_goods_value"],
                payload["community_share"],
                payload["downside_exposure"],
                payload["rationale"],
                payload["evidence"],
                payload["tranches"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active human with a current location solution-lifecycle create grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Location-origin solution was not found"},
                    headers=headers,
                )
            if code in {"22023", "22003"}:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Solution funding proposal is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Funding proposal conflicts with an existing request"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result.get("replayed") else 201,
            headers=headers,
        )

    @router.post(
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/submit"
    )
    async def submit_solution_funding(
        request: Request, location_id: str, funding_case_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        if not isinstance(payload, dict) or set(payload) != {"request_id", "acknowledged"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Solution funding submission fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_solution_funding,
                request.state.operator_session.operator.operator_id,
                location_id,
                funding_case_id,
                payload["request_id"],
                payload["acknowledged"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle submit access is required"},
                headers=headers,
            )
        except SolutionLifecycleActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active human with a current location solution-lifecycle submit grant is required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Funding draft was not found for this operator and location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Solution funding submission is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Funding draft is no longer eligible for submission"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution funding submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution funding submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/gates",
        response_model=SolutionLifecycleGatePageResponse,
    )
    async def location_solution_lifecycle_gates(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_gates,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle gates unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle gates unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        except Exception as exc:
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle gates unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle gates unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = SolutionLifecycleGatePageResponse.model_validate(result)
            expected_location = UUID(location_id)
            expected_next_offset = offset + limit if validated.has_more else None
            if (
                validated.location_id != expected_location
                or validated.offset != offset
                or validated.next_offset != expected_next_offset
                or len(validated.gates) > limit
            ):
                raise ValueError("Solution gate response does not match request bounds")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle gate response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Solution lifecycle gates unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="python")), headers=headers
        )

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/stage-transition-targets",
        response_model=SolutionLifecycleStageTransitionTargetPageResponse,
    )
    async def location_solution_stage_transition_targets(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_stage_transition_targets,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution stage-transition targets unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution stage-transition targets unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = SolutionLifecycleStageTransitionTargetPageResponse.model_validate(
                result
            )
            expected_location = UUID(location_id)
            expected_next_offset = offset + limit if validated.has_more else None
            if (
                validated.location_id != expected_location
                or validated.offset != offset
                or validated.next_offset != expected_next_offset
                or len(validated.solutions) > limit
            ):
                raise ValueError(
                    "Stage-transition target response does not match request bounds"
                )
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution stage-transition target response rejected (%s)",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Solution stage-transition targets unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="python")), headers=headers
        )

    @router.get(
        "/operator/api/solution-lifecycle/{location_id}/experiments",
        response_model=SolutionLifecycleExperimentPageResponse,
    )
    async def location_solution_lifecycle_experiments(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_solution_experiments,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified solution lifecycle access is required"},
                headers=headers,
            )
        except SolutionLifecycleReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except SolutionLifecycleResponseTooLarge as exc:
            return JSONResponse(status_code=413, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location solution lifecycle read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle experiments unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Solution lifecycle experiments unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = SolutionLifecycleExperimentPageResponse.model_validate(result)
            expected_location = UUID(location_id)
            expected_next_offset = offset + limit if validated.has_more else None
            if (
                validated.location_id != expected_location
                or validated.offset != offset
                or validated.next_offset != expected_next_offset
                or len(validated.experiments) > limit
            ):
                raise ValueError("Solution experiment response does not match request bounds")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.solution_lifecycle").warning(
                "Solution lifecycle experiment response rejected (%s)",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Solution lifecycle experiments unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="python")), headers=headers
        )
