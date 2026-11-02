"""OIDC route for location-scoped approved identity resolution."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, ValidationError


def _response_uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("UUID value is invalid") from exc
    raise ValueError("UUID value is invalid")


def _response_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp value is invalid") from exc
    raise ValueError("timestamp value is invalid")


_ResponseUUID = Annotated[UUID, BeforeValidator(_response_uuid)]
_ResponseDatetime = Annotated[AwareDatetime, BeforeValidator(_response_datetime)]


class StakeholderIdentityResolutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _ResponseUUID
    party_id: _ResponseUUID
    resolved_at: _ResponseDatetime


def register_stakeholder_identity_resolution_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.stakeholder_identity_resolution import (
        StakeholderIdentityResolutionInvalid,
        resolve_location_farmer_party_identity,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/stakeholder-identity/{location_id}/resolve/{source_profile_id}",
        response_model=StakeholderIdentityResolutionResponse,
    )
    async def resolve_identity(request: Request, location_id: str, source_profile_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                resolve_location_farmer_party_identity,
                request.state.operator_session.operator.operator_id,
                location_id,
                source_profile_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified identity access is required"},
                headers=headers,
            )
        except StakeholderIdentityResolutionInvalid as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers=headers,
            )
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location resolution grant is required"},
                    headers=headers,
                )
            if getattr(exc, "pgcode", None) == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Identity resolution request is invalid"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.stakeholder_identity_resolution").warning(
                "Stakeholder identity resolution unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Stakeholder identity resolution unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Identity mapping is not available"},
                headers=headers,
            )
        try:
            if not isinstance(result, dict) or set(result) != {"party_id", "resolved_at"}:
                raise ValueError("identity response projection is invalid")
            response = StakeholderIdentityResolutionResponse.model_validate(
                {"location_id": location_id, **result}
            )
            if response.location_id != UUID(location_id):
                raise ValueError("identity response does not match the requested location")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.stakeholder_identity_resolution").warning(
                "Stakeholder identity response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Stakeholder identity resolution unavailable"},
                headers=headers,
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            jsonable_encoder(response.model_dump()), headers=headers
        )
