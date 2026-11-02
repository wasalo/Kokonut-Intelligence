"""Strict response models for the private mobile operations inventory."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, model_validator


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
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("timestamp value is invalid") from exc
    raise ValueError("timestamp value is invalid")


_MobileInventoryUUID = Annotated[UUID, BeforeValidator(_response_uuid)]
_MobileInventoryTimestamp = Annotated[AwareDatetime, BeforeValidator(_response_datetime)]


class MobileOperationsDeviceSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    device_id: str = Field(max_length=200)
    status: str = Field(max_length=50)
    last_seen_at: _MobileInventoryTimestamp | None
    last_sync_at: _MobileInventoryTimestamp | None


class MobileOperationsQueueSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    device_count: int = Field(ge=0, strict=True)
    active_device_count: int = Field(ge=0, strict=True)
    pending_sync_count: int = Field(ge=0, strict=True)
    synced_record_count: int = Field(ge=0, strict=True)
    form_review_required_count: int = Field(ge=0, strict=True)
    ineligible_synced_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_count_relationships(self):
        if self.active_device_count > self.device_count:
            raise ValueError("active device count exceeds total device count")
        if self.ineligible_synced_count > self.synced_record_count:
            raise ValueError("ineligible count exceeds synced record count")
        return self


class MobileOperationsEmptyQueueSummaryResponse(BaseModel):
    """Preserve the service's explicit empty fallback for missing result rows."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class MobileOperationsInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _MobileInventoryUUID
    devices: list[MobileOperationsDeviceSummaryResponse] = Field(max_length=100)
    queue_summary: (
        MobileOperationsQueueSummaryResponse | MobileOperationsEmptyQueueSummaryResponse
    )

    @model_validator(mode="after")
    def validate_device_summary(self):
        if isinstance(self.queue_summary, MobileOperationsQueueSummaryResponse):
            if len(self.devices) > self.queue_summary.device_count:
                raise ValueError("returned device page exceeds total device count")
        return self
