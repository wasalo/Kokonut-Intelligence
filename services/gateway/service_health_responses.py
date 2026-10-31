"""Strict response contract for the authenticated dependency-health route."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)


def _health_timestamp(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("health timestamp is invalid") from exc
    raise ValueError("health timestamp is invalid")


HealthTimestamp = Annotated[AwareDatetime, BeforeValidator(_health_timestamp)]


class ServiceHealthStatusResponse(BaseModel):
    """One configured optional or critical dependency probe result."""

    model_config = ConfigDict(extra="forbid", strict=True)

    service: Annotated[StrictStr, Field(min_length=1, max_length=128)]
    healthy: StrictBool
    critical: StrictBool
    message: Annotated[StrictStr, Field(min_length=1, max_length=512)]
    latency_ms: Annotated[StrictInt, Field(ge=0, le=600_000)]
    checked_at: HealthTimestamp
    state: Literal["checked", "disabled", "unmonitored"]


class ServiceHealthResponse(BaseModel):
    """Exact dependency-health summary with internally consistent aggregates."""

    model_config = ConfigDict(extra="forbid", strict=True)

    healthy: StrictBool
    ready: StrictBool
    version: Annotated[StrictStr, Field(min_length=1, max_length=128)]
    git_sha: Annotated[StrictStr, Field(min_length=1, max_length=128)]
    critical_failures: Annotated[StrictInt, Field(ge=0, le=256)]
    services: Annotated[list[ServiceHealthStatusResponse], Field(max_length=256)]

    @model_validator(mode="after")
    def validate_aggregates(self):
        names = [item.service for item in self.services]
        if len(names) != len(set(names)):
            raise ValueError("service names must be unique")

        expected_healthy = all(item.healthy for item in self.services)
        expected_critical_failures = sum(
            item.critical and not item.healthy for item in self.services
        )
        if self.healthy != expected_healthy:
            raise ValueError("overall health does not match service results")
        if self.ready != (expected_critical_failures == 0):
            raise ValueError("readiness does not match critical service results")
        if self.critical_failures != expected_critical_failures:
            raise ValueError("critical failure count does not match service results")
        return self
