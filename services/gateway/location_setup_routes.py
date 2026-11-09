"""Authenticated Control Plane APIs for setting up a farm location."""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

_LOGGER = logging.getLogger("gateway.location_setup")
_NO_STORE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache", "Vary": "Cookie"}
_SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_MAX_REQUEST_BODY_BYTES = 600_000


def _validate_polygon(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {"type", "coordinates"} or value.get("type") != "Polygon":
        raise ValueError("boundary must be a GeoJSON Polygon with only type and coordinates")
    rings = value.get("coordinates")
    if not isinstance(rings, list) or not rings:
        raise ValueError("boundary must include at least one closed ring")
    if len(json.dumps(value, separators=(",", ":"))) > 262_144:
        raise ValueError("boundary GeoJSON must be 256 KB or smaller")
    for ring in rings:
        if not isinstance(ring, list) or len(ring) < 4:
            raise ValueError("each polygon ring must include at least four coordinates")
        points: list[list[float]] = []
        for point in ring:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in point)
            ):
                raise ValueError("polygon coordinates must be two-dimensional numeric longitude/latitude pairs")
            longitude, latitude = float(point[0]), float(point[1])
            if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                raise ValueError("polygon coordinates must be valid WGS84 longitude/latitude values")
            points.append([longitude, latitude])
        if points[0] != points[-1]:
            raise ValueError("each polygon ring must be closed")
    return value


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LocationSetupOrganization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    org_key: str
    name: str


class LocationSetupOrganizationsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[LocationSetupOrganization] = Field(max_length=200)


class LocationSetupLocation(_StrictRequest):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    country: str = Field(min_length=1, max_length=100)
    region: str = Field(min_length=1, max_length=255)
    sub_region: str | None = Field(default=None, max_length=255)
    timezone: str = Field(min_length=1, max_length=50)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    boundary_geojson: dict[str, Any]

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if not _SLUG_PATTERN.fullmatch(value):
            raise ValueError("use lowercase letters, numbers, and single hyphens in the slug")
        return value

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def validate_coordinate_value(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("latitude and longitude must be numeric")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA time zone") from exc
        return value

    @field_validator("boundary_geojson")
    @classmethod
    def validate_boundary(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_polygon(value)

class LocationSetupFarm(_StrictRequest):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    farm_type: Literal["conventional", "organic", "syntropic", "agroforestry", "hybrid"]
    total_area: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    area_unit: Literal["hectares", "acres", "square_meters"]
    boundary_geojson: dict[str, Any]

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if not _SLUG_PATTERN.fullmatch(value):
            raise ValueError("use lowercase letters, numbers, and single hyphens in the slug")
        return value

    @field_validator("boundary_geojson")
    @classmethod
    def validate_boundary(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_polygon(value)

    @field_validator("total_area", mode="before")
    @classmethod
    def validate_area_value(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError("farm area must be numeric")
        return Decimal(str(value))


class LocationSetupCreateRequest(_StrictRequest):
    organization_id: UUID
    owner_decision_reference: str = Field(min_length=3, max_length=2000)
    owner_decision_confirmed: Literal[True]
    location: LocationSetupLocation
    farm: LocationSetupFarm


class LocationSetupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    location_created: bool
    location_name: str
    farm_id: UUID
    farm_created: bool
    farm_name: str
    organization_id: UUID
    organization_name: str
    starter_scopes: list[dict[str, str]] = Field(min_length=1, max_length=10)


class LocationSetupCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: LocationSetupResult


def _error(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": message, "code": code},
        headers=_NO_STORE_HEADERS,
    )


def register_location_setup_routes(router: APIRouter, provider, run_in_threadpool, psycopg2) -> None:
    """Register routes; middleware requires the location_setup:create capability."""

    if provider is None:
        return

    from services.gateway.location_setup import (
        create_operator_location_setup,
        list_location_setup_organizations,
    )
    from services.gateway.operator_auth import _get_operator_auth_db

    def connection_factory():
        return _get_operator_auth_db(provider.settings)

    @router.get(
        "/operator/api/location-setup/organizations",
        response_model=LocationSetupOrganizationsResponse,
    )
    async def location_setup_organizations(request: Request):
        session = getattr(request.state, "operator_session", None)
        if session is None:
            return _error(401, "Sign in to continue.", "operator_session_required")
        try:
            organizations = await run_in_threadpool(
                list_location_setup_organizations,
                session.operator.operator_id,
                connection_factory=connection_factory,
            )
            response = LocationSetupOrganizationsResponse.model_validate({"data": organizations})
        except psycopg2.Error as exc:
            _LOGGER.warning("Organization choices unavailable (%s)", type(exc).__name__)
            return _error(503, "Organization choices are temporarily unavailable.", "location_setup_unavailable")
        except Exception as exc:
            _LOGGER.warning("Organization choices rejected (%s)", type(exc).__name__)
            return _error(503, "Organization choices are temporarily unavailable.", "location_setup_unavailable")
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="json")),
            headers=_NO_STORE_HEADERS,
        )

    @router.post(
        "/operator/api/location-setup",
        response_model=LocationSetupCreateResponse,
        status_code=201,
    )
    async def create_location_setup(request: Request):
        session = getattr(request.state, "operator_session", None)
        if session is None:
            return _error(401, "Sign in to continue.", "operator_session_required")
        try:
            content_length = request.headers.get("content-length")
            if content_length is not None and int(content_length) > _MAX_REQUEST_BODY_BYTES:
                return _error(413, "Boundary data exceeds the 600 KB request limit.", "location_setup_too_large")
            body_bytes = bytearray()
            async for chunk in request.stream():
                if len(body_bytes) + len(chunk) > _MAX_REQUEST_BODY_BYTES:
                    return _error(413, "Boundary data exceeds the 600 KB request limit.", "location_setup_too_large")
                body_bytes.extend(chunk)
            raw_body = json.loads(body_bytes)
            body = LocationSetupCreateRequest.model_validate(raw_body)
        except Exception:
            return _error(400, "Review the required location, farm, and ownership fields.", "invalid_location_setup")
        try:
            farm_payload = body.farm.model_dump(mode="json")
            farm_payload["total_area"] = float(body.farm.total_area)
            result = await run_in_threadpool(
                create_operator_location_setup,
                session.operator.operator_id,
                str(body.organization_id),
                body.location.model_dump(mode="json"),
                farm_payload,
                body.owner_decision_reference,
                connection_factory=connection_factory,
            )
            response = LocationSetupCreateResponse.model_validate({"data": result})
        except psycopg2.Error as exc:
            sqlstate = getattr(exc, "pgcode", None)
            if sqlstate == "42501":
                return _error(403, "Your location setup capability is no longer active.", "location_setup_forbidden")
            if sqlstate == "23505":
                return _error(409, "A location slug, farm slug, or decision reference is already in use.", "location_setup_conflict")
            if sqlstate == "55000":
                return _error(409, "The requested location has an existing tenant or farm assignment that needs review.", "location_setup_conflict")
            if isinstance(sqlstate, str) and sqlstate.startswith("22"):
                return _error(400, "The location or farm details are invalid. Check the boundary and coordinates.", "invalid_location_setup")
            if sqlstate == "23514":
                return _error(400, "The location or farm details do not satisfy the database constraints.", "invalid_location_setup")
            _LOGGER.warning("Location setup transaction unavailable (%s)", type(exc).__name__)
            return _error(503, "Location setup is temporarily unavailable.", "location_setup_unavailable")
        except Exception as exc:
            _LOGGER.warning("Location setup response rejected (%s)", type(exc).__name__)
            return _error(503, "Location setup is temporarily unavailable.", "location_setup_unavailable")
        return JSONResponse(
            status_code=201 if response.data.location_created and response.data.farm_created else 200,
            content=jsonable_encoder(response.model_dump(mode="json")),
            headers=_NO_STORE_HEADERS,
        )
