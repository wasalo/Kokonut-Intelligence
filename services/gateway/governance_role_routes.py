"""OIDC route registration for location-scoped governance reads and actions."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)


def _response_uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("UUID value is invalid") from exc
    raise ValueError("UUID value is invalid")


_GovernanceResponseUUID = Annotated[UUID, BeforeValidator(_response_uuid)]
_ROLE_STATUS = Literal[
    "draft", "submitted", "approved", "active", "suspended", "rejected", "retired"
]
_CIRCLE_STATUS = Literal["draft", "submitted", "active", "suspended", "rejected", "retired"]
_GOVERNANCE_SCOPE = Literal[
    "network",
    "organization",
    "location",
    "farm",
    "cooperative",
    "value_stream",
    "initiative",
    "decision",
]


class GovernanceRoleDetailRoleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    role_key: str = Field(max_length=120)
    name: str = Field(max_length=255)
    purpose: str
    status: _ROLE_STATUS
    effective_from: AwareDatetime | None
    effective_until: AwareDatetime | None
    review_due_at: AwareDatetime | None
    created_at: AwareDatetime
    circle_key: str = Field(max_length=120)
    circle_name: str = Field(max_length=255)
    circle_status: _CIRCLE_STATUS


class GovernanceRoleAccountabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    accountability: str
    priority: int = Field(ge=1, le=5, strict=True)
    required: bool = Field(strict=True)


class GovernanceRoleAuthorityDomainResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    domain_type: str = Field(max_length=40)
    domain_key: str = Field(max_length=160)
    scope_type: _GOVERNANCE_SCOPE
    authority_level: Literal["observe", "recommend", "decide", "execute"]
    requires_human_approval: bool = Field(strict=True)


class GovernanceRoleDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    role: GovernanceRoleDetailRoleResponse
    accountabilities: list[GovernanceRoleAccountabilityResponse] = Field(max_length=100)
    accountabilities_truncated: bool = Field(strict=True)
    authority_domains: list[GovernanceRoleAuthorityDomainResponse] = Field(max_length=100)
    authority_domains_truncated: bool = Field(strict=True)


class GovernanceCircleDetailItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    circle_key: str = Field(max_length=120, strict=True)
    name: str = Field(max_length=255, strict=True)
    purpose: str = Field(strict=True)
    description: str | None = Field(strict=True)
    parent_circle_id: _GovernanceResponseUUID | None
    status: _CIRCLE_STATUS


class GovernanceCircleDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    circle: GovernanceCircleDetailItemResponse


class GovernanceRoleListItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    role_key: str = Field(max_length=120)
    name: str = Field(max_length=255)
    purpose: str
    status: _ROLE_STATUS
    effective_from: AwareDatetime | None
    effective_until: AwareDatetime | None
    review_due_at: AwareDatetime | None
    created_at: AwareDatetime
    circle_key: str = Field(max_length=120)
    circle_name: str = Field(max_length=255)
    circle_status: _CIRCLE_STATUS
    active_accountability_count: int = Field(ge=0, strict=True)
    current_assignment_count: int = Field(ge=0, strict=True)
    applicable_authority_domain_count: int = Field(ge=0, strict=True)


class GovernanceRoleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    items: list[GovernanceRoleListItemResponse] = Field(max_length=100)
    next_cursor: _GovernanceResponseUUID | None


class GovernanceSummaryCircleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    circle_key: str = Field(max_length=120)
    name: str = Field(max_length=255)
    status: _CIRCLE_STATUS
    review_due_at: AwareDatetime | None
    active_role_count: int = Field(ge=0, strict=True)
    overdue_role_review_count: int = Field(ge=0, strict=True)
    active_assignment_count: int = Field(ge=0, strict=True)
    proposed_assignment_count: int = Field(ge=0, strict=True)
    active_authority_domain_count: int = Field(ge=0, strict=True)


class GovernanceSummaryTensionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    total: int = Field(ge=0, strict=True)
    unresolved: int = Field(ge=0, strict=True)
    high_severity_unresolved: int = Field(ge=0, strict=True)
    overdue_reviews: int = Field(ge=0, strict=True)


class GovernanceSummaryTacticalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    sessions: int = Field(ge=0, strict=True)
    open_items: int = Field(ge=0, strict=True)
    overdue_items: int = Field(ge=0, strict=True)
    disposed_items: int = Field(ge=0, strict=True)


class GovernanceSummaryResponse(BaseModel):
    """Location-scoped counts and circle metadata from the governance summary query."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    circles: list[GovernanceSummaryCircleResponse]
    tensions: GovernanceSummaryTensionsResponse
    tactical: GovernanceSummaryTacticalResponse


class GovernanceTacticalItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    requested_next_action: str = Field(min_length=1, max_length=4000)
    priority: int = Field(ge=1, le=5, strict=True)
    due_at: AwareDatetime | None
    status: Literal["open", "in_progress"]
    created_at: AwareDatetime
    session_type: Literal[
        "weekly_review",
        "stakeholder_health",
        "relationship_review",
        "risk_triage",
        "governance_followup",
    ]
    session_title: str = Field(max_length=255)
    scheduled_at: AwareDatetime | None
    session_status: Literal["planned", "active", "completed"]
    owner_role_key: str | None = Field(max_length=120)

    @field_validator("requested_next_action")
    @classmethod
    def _requested_action_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("requested_next_action must not be blank")
        return value


class GovernanceTacticalItemPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    items: list[GovernanceTacticalItemResponse] = Field(max_length=100)
    next_cursor: _GovernanceResponseUUID | None

    def validate_request(self, *, location_id: str, limit: int, cursor: str | None):
        if self.location_id != UUID(location_id) or len(self.items) > limit:
            raise ValueError("Governance tactical page does not match request bounds")
        if self.next_cursor is not None:
            if (
                not self.items
                or len(self.items) != limit
                or self.next_cursor != self.items[-1].id
            ):
                raise ValueError("Governance tactical cursor does not match the page")
        if cursor is not None:
            input_cursor = UUID(cursor)
            if input_cursor in {item.id for item in self.items} or self.next_cursor == input_cursor:
                raise ValueError("Governance tactical page repeats its input cursor")
        return self


class GovernanceTacticalSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    session_type: Literal[
        "weekly_review",
        "stakeholder_health",
        "relationship_review",
        "risk_triage",
        "governance_followup",
    ]
    title: str = Field(max_length=255)
    scheduled_at: AwareDatetime | None
    status: Literal["planned", "active", "completed", "cancelled"]
    created_at: AwareDatetime
    circle_key: str = Field(max_length=120)
    circle_name: str = Field(max_length=255)
    item_count: int = Field(ge=0, strict=True)
    open_item_count: int = Field(ge=0, strict=True)
    disposed_item_count: int = Field(ge=0, strict=True)
    overdue_item_count: int = Field(ge=0, strict=True)


class GovernanceTacticalSessionPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    items: list[GovernanceTacticalSessionResponse] = Field(max_length=100)
    next_cursor: _GovernanceResponseUUID | None

    def validate_request(self, *, location_id: str, limit: int, cursor: str | None):
        if self.location_id != UUID(location_id) or len(self.items) > limit:
            raise ValueError("Governance tactical session page does not match request bounds")
        if self.next_cursor is not None:
            if (
                not self.items
                or len(self.items) != limit
                or self.next_cursor != self.items[-1].id
            ):
                raise ValueError("Governance tactical session cursor does not match the page")
        if cursor is not None:
            input_cursor = UUID(cursor)
            if input_cursor in {item.id for item in self.items} or self.next_cursor == input_cursor:
                raise ValueError("Governance tactical session page repeats its input cursor")
        return self


def register_governance_role_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.governance_assignment_proposal_reads import (
        GovernanceAssignmentProposalReadInvalid,
        list_own_governance_assignment_proposals,
    )
    from services.gateway.governance_assignment_proposals import (
        GovernanceAssignmentConflict,
        GovernanceAssignmentInvalid,
        propose_governance_role_assignment,
    )
    from services.gateway.governance_assignment_review import (
        GovernanceAssignmentReviewConflict,
        GovernanceAssignmentReviewInvalid,
        decide_governance_assignment,
        list_governance_assignment_reviews,
    )
    from services.gateway.governance_definition_actions import (
        GovernanceDefinitionActionConflict,
        GovernanceDefinitionActionInvalid,
        transition_governance_definition,
    )
    from services.gateway.governance_definition_mutations import (
        GovernanceDefinitionMutationConflict,
        GovernanceDefinitionMutationInvalid,
        mutate_governance_definition,
    )
    from services.gateway.governance_operations import (
        GovernanceOperationsInvalid,
        get_location_governance_circle_detail,
        get_location_governance_role_detail,
        list_location_governance_roles,
        list_location_governance_tactical_items,
        list_location_governance_tactical_sessions,
    )
    from services.gateway.governance_roles import get_location_governance_summary
    from services.gateway.governance_tactical_actions import (
        GovernanceTacticalActionConflict,
        GovernanceTacticalActionInvalid,
        transition_governance_tactical_item,
    )
    from services.gateway.governance_tactical_mutations import (
        GovernanceTacticalMutationConflict,
        GovernanceTacticalMutationInvalid,
        mutate_governance_tactical_content,
    )
    from services.gateway.governance_tactical_session_mutations import (
        GovernanceTacticalSessionInvalid,
        create_governance_tactical_session,
    )
    from services.gateway.governance_tension_actions import (
        GovernanceTensionConflict,
        GovernanceTensionInvalid,
        report_governance_tension,
        submit_governance_tension,
    )
    from services.gateway.governance_tension_review import (
        GovernanceTensionReviewDetailResponse,
        GovernanceTensionReviewInvalid,
        GovernanceTensionReviewNotFound,
        GovernanceTensionReviewQueueResponse,
        get_location_governance_tension,
        list_location_governance_tensions,
    )

    def error_response(exc, *, headers):
        if isinstance(exc, TenantContextDenied):
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        if isinstance(exc, GovernanceTensionInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionReviewInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionConflict):
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionReviewNotFound):
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceDefinitionActionInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceDefinitionActionConflict):
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, psycopg2.Error):
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance action grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance tension request is invalid"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Governance definition was not found in this location"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance tension request conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_tensions").warning(
                "Governance tension action unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tension action unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        raise exc

    @router.get(
        "/operator/api/governance/{location_id}/summary",
        response_model=GovernanceSummaryResponse,
    )
    async def location_governance_summary(request: Request, location_id: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            summary = await run_in_threadpool(
                get_location_governance_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers=headers,
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )

        try:
            response = GovernanceSummaryResponse.model_validate(summary)
            if response.location_id != UUID(location_id):
                raise ValueError("Governance summary location does not match request")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance summary unavailable"},
                headers=headers,
            )

        return JSONResponse(jsonable_encoder(response.model_dump(mode="python")), headers=headers)

    @router.get(
        "/operator/api/governance/{location_id}/roles",
        response_model=GovernanceRoleListResponse,
    )
    async def location_governance_roles(
        request: Request,
        location_id: str,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_roles,
                request.state.operator_session.operator.operator_id,
                location_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance role registry unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role registry unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            response = GovernanceRoleListResponse.model_validate(result)
            if response.location_id != UUID(location_id) or len(response.items) > limit:
                raise ValueError("Governance role page does not match request bounds")
            if response.next_cursor is not None and (
                not response.items or response.next_cursor != response.items[-1].id
            ):
                raise ValueError("Governance role cursor does not match the page")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance role page response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance role registry unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/governance/{location_id}/roles/{role_id}",
        response_model=GovernanceRoleDetailResponse,
    )
    async def location_governance_role_detail(
        request: Request,
        location_id: str,
        role_id: str,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_governance_role_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                role_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance role detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Governance role not found"},
                headers=headers,
            )
        try:
            response = GovernanceRoleDetailResponse.model_validate(result)
            if response.location_id != UUID(location_id) or response.role.id != UUID(role_id):
                raise ValueError("Governance role detail does not match request scope")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance role detail response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance role detail unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/governance/{location_id}/circles/{circle_id}",
        response_model=GovernanceCircleDetailResponse,
    )
    async def location_governance_circle_detail(
        request: Request,
        location_id: str,
        circle_id: str,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_governance_circle_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                circle_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance circle detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance circle detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Governance circle not found"},
                headers=headers,
            )
        try:
            response = GovernanceCircleDetailResponse.model_validate(result)
            if (
                response.location_id != UUID(location_id)
                or response.circle.id != UUID(circle_id)
            ):
                raise ValueError("Governance circle detail does not match request scope")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance circle detail response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance circle detail unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/governance/{location_id}/assignment-proposals"
    )
    async def own_governance_assignment_proposals(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        cursor_created_at: str | None = None,
        cursor_assignment_id: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_own_governance_assignment_proposals,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_assignment_id=cursor_assignment_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceAssignmentProposalReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active governance role read grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance role proposal cursor is invalid"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance role proposal readback unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role proposal readback unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/governance/{location_id}/assignment-review-queue"
    )
    async def governance_assignment_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        cursor_created_at: str | None = None,
        cursor_assignment_id: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_governance_assignment_reviews,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_assignment_id=cursor_assignment_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceAssignmentReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active governance role review grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance assignment review cursor is invalid"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance assignment review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance assignment review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    async def decide_assignment_route(
        request: Request,
        location_id: str,
        role_id: str,
        assignment_id: str,
        decision: str,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Assignment decision must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                decide_governance_assignment,
                request.state.operator_session.operator.operator_id,
                location_id,
                role_id,
                assignment_id,
                decision,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceAssignmentReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except GovernanceAssignmentReviewConflict as exc:
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active governance role decision grant and independent person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance assignment decision is invalid"},
                    headers=headers,
                )
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance assignment has already changed or been decided"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance assignment decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance assignment decision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/governance/{location_id}/roles/{role_id}/assignments/{assignment_id}/approve"
    )
    async def approve_governance_role_assignment_route(
        request: Request, location_id: str, role_id: str, assignment_id: str
    ):
        return await decide_assignment_route(
            request, location_id, role_id, assignment_id, "approve"
        )

    @router.post(
        "/operator/api/governance/{location_id}/roles/{role_id}/assignments/{assignment_id}/reject"
    )
    async def reject_governance_role_assignment_route(
        request: Request, location_id: str, role_id: str, assignment_id: str
    ):
        return await decide_assignment_route(
            request, location_id, role_id, assignment_id, "reject"
        )

    @router.post(
        "/operator/api/governance/{location_id}/roles/{role_id}/assignments",
        status_code=201,
    )
    async def propose_governance_role_assignment_route(
        request: Request, location_id: str, role_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Role nomination must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_governance_role_assignment,
                request.state.operator_session.operator.operator_id,
                location_id,
                role_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceAssignmentInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except GovernanceAssignmentConflict as exc:
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance role creation grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance role nomination is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance role nomination conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance role nomination unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role nomination unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    async def governance_definition_action_route(
        request: Request,
        location_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance lifecycle content must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_governance_definition,
                request.state.operator_session.operator.operator_id,
                location_id,
                entity_type,
                entity_id,
                action,
                payload,
            )
        except (
            TenantContextDenied,
            GovernanceDefinitionActionInvalid,
            GovernanceDefinitionActionConflict,
            psycopg2.Error,
        ) as exc:
            if isinstance(exc, (GovernanceDefinitionActionInvalid, GovernanceDefinitionActionConflict)):
                status_code = 400 if isinstance(exc, GovernanceDefinitionActionInvalid) else 409
                return JSONResponse(status_code=status_code, content={"error": str(exc)}, headers=headers)
            if isinstance(exc, TenantContextDenied):
                return JSONResponse(
                    status_code=403,
                    content={"error": "Tenant-qualified operator access is required"},
                    headers=headers,
                )
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance action grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance definition action is invalid"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Governance definition was not found in this location"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance definition action conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_definitions").warning(
                "Governance definition action unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance definition action unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    def circle_action_endpoint(action):
        async def endpoint(request: Request, location_id: str, circle_id: str):
            return await governance_definition_action_route(
                request, location_id, "circle", circle_id, action
            )

        return endpoint

    def role_action_endpoint(action):
        async def endpoint(request: Request, location_id: str, role_id: str):
            return await governance_definition_action_route(
                request, location_id, "role", role_id, action
            )

        return endpoint

    async def governance_definition_mutation_route(
        request: Request,
        location_id: str,
        entity_type: str,
        action: str,
        entity_id: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance definition content must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                mutate_governance_definition,
                request.state.operator_session.operator.operator_id,
                location_id,
                entity_type,
                action,
                entity_id,
                payload,
            )
        except (
            TenantContextDenied,
            GovernanceDefinitionMutationInvalid,
            GovernanceDefinitionMutationConflict,
            psycopg2.Error,
        ) as exc:
            if isinstance(exc, GovernanceDefinitionMutationInvalid):
                return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
            if isinstance(exc, GovernanceDefinitionMutationConflict):
                return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
            if isinstance(exc, TenantContextDenied):
                return JSONResponse(
                    status_code=403,
                    content={"error": "Tenant-qualified operator access is required"},
                    headers=headers,
                )
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance mutation grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance definition content is invalid"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Governance definition was not found in this location"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance definition is unavailable or changed state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_definitions").warning(
                "Governance definition mutation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance definition mutation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=201 if action == "create" else 200,
            headers=headers,
        )

    def create_definition_endpoint(entity_type):
        async def endpoint(request: Request, location_id: str):
            return await governance_definition_mutation_route(
                request, location_id, entity_type, "create"
            )

        return endpoint

    def update_definition_endpoint(entity_type):
        async def endpoint(request: Request, location_id: str, definition_id: str):
            return await governance_definition_mutation_route(
                request, location_id, entity_type, "update", definition_id
            )

        return endpoint

    for entity_type, route_name in (("circle", "circle"), ("role", "role")):
        router.add_api_route(
            f"/operator/api/governance/{{location_id}}/{route_name}s",
            create_definition_endpoint(entity_type),
            methods=["POST"],
            name=f"create_governance_{route_name}",
        )
        router.add_api_route(
            f"/operator/api/governance/{{location_id}}/{route_name}s/{{definition_id}}",
            update_definition_endpoint(entity_type),
            methods=["PATCH"],
            name=f"update_governance_{route_name}",
        )

    for circle_action in ("submit", "reject", "activate", "suspend", "retire"):
        router.add_api_route(
            f"/operator/api/governance/{{location_id}}/circles/{{circle_id}}/{circle_action}",
            circle_action_endpoint(circle_action),
            methods=["POST"],
            name=f"transition_governance_circle_{circle_action}",
        )

    for role_action in ("submit", "approve", "reject", "activate", "suspend", "retire"):
        router.add_api_route(
            f"/operator/api/governance/{{location_id}}/roles/{{role_id}}/{role_action}",
            role_action_endpoint(role_action),
            methods=["POST"],
            name=f"transition_governance_role_{role_action}",
        )

    @router.get(
        "/operator/api/governance/{location_id}/tactical-items",
        response_model=GovernanceTacticalItemPageResponse,
    )
    async def location_governance_tactical_items(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_tactical_items,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor=cursor,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance tactical queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            response = GovernanceTacticalItemPageResponse.model_validate(result)
            response.validate_request(location_id=location_id, limit=limit, cursor=cursor)
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance tactical page response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tactical queue unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/governance/{location_id}/tactical-sessions",
        response_model=GovernanceTacticalSessionPageResponse,
    )
    async def location_governance_tactical_sessions(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_tactical_sessions,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor=cursor,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance tactical sessions unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical sessions unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            response = GovernanceTacticalSessionPageResponse.model_validate(result)
            response.validate_request(location_id=location_id, limit=limit, cursor=cursor)
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance tactical session page response rejected (%s)",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tactical sessions unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(response.model_dump(mode="python")), headers=headers)

    @router.post("/operator/api/governance/{location_id}/tactical-sessions", status_code=201)
    async def create_governance_tactical_session_route(request: Request, location_id: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Tactical session content must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_governance_tactical_session,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceTacticalSessionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active tactical session creation grant and person binding are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "The active circle or role was not found in this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Tactical session request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Tactical session creation conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_tactical").warning(
                "Governance tactical session creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical session creation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    async def mutate_tactical_content_route(
        request: Request,
        location_id: str,
        operation: str,
        target_id: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Tactical content must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                mutate_governance_tactical_content,
                request.state.operator_session.operator.operator_id,
                location_id,
                operation,
                target_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceTacticalMutationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except GovernanceTacticalMutationConflict as exc:
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active tactical content grant and person binding are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "The linked session, role, person, or record is unavailable in this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Tactical content request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Tactical content conflicts with its current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_tactical").warning(
                "Governance tactical content mutation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical content mutation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 201 if operation == "create_item" else 200
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)

    @router.post("/operator/api/governance/{location_id}/tactical-items", status_code=201)
    async def create_governance_tactical_item(request: Request, location_id: str):
        return await mutate_tactical_content_route(request, location_id, "create_item")

    @router.patch("/operator/api/governance/{location_id}/tactical-items/{item_id}")
    async def update_governance_tactical_item(request: Request, location_id: str, item_id: str):
        return await mutate_tactical_content_route(request, location_id, "update_item", item_id)

    @router.patch("/operator/api/governance/{location_id}/tactical-sessions/{session_id}")
    async def update_governance_tactical_session(request: Request, location_id: str, session_id: str):
        return await mutate_tactical_content_route(request, location_id, "update_session", session_id)

    async def transition_tactical_route(request: Request, location_id: str, item_id: str, action: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Tactical action must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_governance_tactical_item,
                request.state.operator_session.operator.operator_id,
                location_id,
                item_id,
                action,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceTacticalActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except GovernanceTacticalActionConflict as exc:
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active tactical action grant and person binding are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Tactical item not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Tactical action request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Tactical item state has changed or this action conflicts"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_tactical").warning(
                "Governance tactical action unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical action unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/governance/{location_id}/tactical-items/{item_id}/start")
    async def start_governance_tactical_item(request: Request, location_id: str, item_id: str):
        return await transition_tactical_route(request, location_id, item_id, "start")

    @router.post("/operator/api/governance/{location_id}/tactical-items/{item_id}/dispose")
    async def dispose_governance_tactical_item(request: Request, location_id: str, item_id: str):
        return await transition_tactical_route(request, location_id, item_id, "dispose")

    @router.post("/operator/api/governance/{location_id}/tactical-items/{item_id}/cancel")
    async def cancel_governance_tactical_item(request: Request, location_id: str, item_id: str):
        return await transition_tactical_route(request, location_id, item_id, "cancel")

    @router.get(
        "/operator/api/governance/{location_id}/tensions",
        response_model=GovernanceTensionReviewQueueResponse,
    )
    async def location_governance_tensions(
        request: Request,
        location_id: str,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_tensions,
                request.state.operator_session.operator.operator_id,
                location_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        except (
            TenantContextDenied,
            GovernanceTensionReviewInvalid,
            GovernanceTensionReviewNotFound,
            psycopg2.Error,
        ) as exc:
            return error_response(exc, headers=headers)
        try:
            page = GovernanceTensionReviewQueueResponse.model_validate(result)
            from uuid import UUID

            if (
                page.location_id != UUID(location_id)
                or len(page.items) > limit
                or (page.next_cursor is not None and len(page.items) != limit)
            ):
                raise ValueError("governance tension page does not match the request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_tensions").warning(
                "Governance tension queue response rejected (%s)",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tension review unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(page.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/governance/{location_id}/tensions/{tension_id}",
        response_model=GovernanceTensionReviewDetailResponse,
    )
    async def location_governance_tension_detail(
        request: Request, location_id: str, tension_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                tension_id,
            )
        except (
            TenantContextDenied,
            GovernanceTensionReviewInvalid,
            GovernanceTensionReviewNotFound,
            psycopg2.Error,
        ) as exc:
            return error_response(exc, headers=headers)
        try:
            from uuid import UUID

            detail = GovernanceTensionReviewDetailResponse.model_validate(result)
            if (
                detail.location_id != UUID(location_id)
                or detail.tension.id != UUID(tension_id)
            ):
                raise ValueError("governance tension detail does not match request scope")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_tensions").warning(
                "Governance tension detail response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tension review unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(detail.model_dump(mode="json")), headers=headers
        )

    @router.post("/operator/api/governance/{location_id}/tensions", status_code=201)
    async def create_governance_tension(request: Request, location_id: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance tension content must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                report_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except (TenantContextDenied, GovernanceTensionInvalid, GovernanceTensionConflict, psycopg2.Error) as exc:
            return error_response(exc, headers=headers)
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.post(
        "/operator/api/governance/{location_id}/tensions/{tension_id}/submit"
    )
    async def submit_governance_tension_route(
        request: Request, location_id: str, tension_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                tension_id,
            )
        except (TenantContextDenied, GovernanceTensionInvalid, GovernanceTensionConflict, psycopg2.Error) as exc:
            return error_response(exc, headers=headers)
        return JSONResponse(jsonable_encoder(result), headers=headers)
