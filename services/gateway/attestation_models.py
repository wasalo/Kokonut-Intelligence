"""Privacy-bounded response models for the Gateway attestation read surface."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LocationAttestationRecord(BaseModel):
    """Stored Celo attestation metadata; excludes claim and private evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str
    attestation_uid: str | None
    schema_uid: str
    schema_name: str
    claim_type: str | None
    status: str | None
    chain: str
    tx_hash: str | None
    attested_at: str | None
    expiration_date: str | None
    revocation_date: str | None
    schema_version: str | None
    created_at: str | None


class LocationAttestationsResponse(BaseModel):
    """Bounded location response returned by the OIDC attestation route."""

    model_config = ConfigDict(extra="forbid")

    data: list[LocationAttestationRecord] = Field(max_length=100)
    location_id: str
