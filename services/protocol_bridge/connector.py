"""Idempotent connector port for approved KI execution envelopes."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .execution import (
    BridgeConflictError,
    BridgeValidationError,
    build_dispatch_envelope,
    canonical_request_hash,
    validate_execution_request,
)


class ProtocolExecutionClient(Protocol):
    """Minimal contract-facing port; signing and transport stay injected."""

    def get_execution_request(self, request_id: str) -> Mapping[str, Any] | None:
        """Return the NEAR view record, or None if the request is absent."""
        ...

    def propose_execution(self, request: Mapping[str, Any]) -> Any:
        """Submit the request and return only after the client observes finality."""
        ...


class ProtocolSubmissionError(RuntimeError):
    """The client returned without a matching Protocol request becoming visible."""


def _require_matching_request(record: Mapping[str, Any], envelope: Mapping[str, Any]) -> None:
    stored = record.get("request")
    request = envelope["request"]
    if not isinstance(stored, Mapping):
        raise BridgeConflictError("Protocol returned a request record without its request snapshot")
    if str(stored.get("request_id")) != str(envelope["request_id"]):
        raise BridgeConflictError("Protocol returned a different request ID")
    if dict(stored) != dict(request) or canonical_request_hash(stored) != envelope["request_hash"]:
        raise BridgeConflictError("Protocol already contains this request ID with a different request")


def _validate_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(envelope, Mapping):
        raise BridgeValidationError("Protocol submission envelope must be an object")
    try:
        raw_request = envelope["request"]
        request = validate_execution_request(
            raw_request,
            protocol_project_id=str(raw_request["project_id"]),
        )
        normalized = build_dispatch_envelope(
            str(envelope["intent_id"]),
            request,
            str(envelope["request_hash"]),
            approval_threshold=envelope["approval_threshold"],
            approved_by_party_ids=envelope["approved_by_party_ids"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, BridgeValidationError):
            raise
        raise BridgeValidationError("Protocol submission envelope is malformed") from exc
    if dict(envelope) != normalized:
        raise BridgeValidationError("Protocol submission envelope differs from its approved snapshot")
    return normalized


def submit_execution_envelope(
    envelope: Mapping[str, Any],
    client: ProtocolExecutionClient,
) -> dict[str, str]:
    """Ensure the exact approved request exists in Protocol, safely retrying ambiguity.

    The injected client owns NEAR transaction signing, transport, and finality
    observation. This function never handles keys or makes network calls itself.
    A retry first reads by request ID, so a lost response after successful
    submission does not create a second proposal or silently change the payload.
    """
    approved = _validate_envelope(envelope)
    request_id = approved["request_id"]
    existing = client.get_execution_request(request_id)
    if existing is not None:
        if not isinstance(existing, Mapping):
            raise BridgeConflictError("Protocol returned a malformed execution request record")
        _require_matching_request(existing, approved)
        return {"request_id": request_id, "request_hash": approved["request_hash"], "status": "already_present"}

    try:
        client.propose_execution(approved["request"])
    except Exception:
        # The transport may have lost the response after chain acceptance. A
        # fresh view distinguishes that case from a safe-to-retry failure.
        try:
            existing = client.get_execution_request(request_id)
        except Exception:
            raise
        if existing is None:
            raise
        if not isinstance(existing, Mapping):
            raise BridgeConflictError("Protocol returned a malformed execution request record")
        _require_matching_request(existing, approved)
        return {"request_id": request_id, "request_hash": approved["request_hash"], "status": "already_present"}

    existing = client.get_execution_request(request_id)
    if existing is None:
        raise ProtocolSubmissionError("Protocol proposal returned without a matching request visible at finality")
    if not isinstance(existing, Mapping):
        raise BridgeConflictError("Protocol returned a malformed execution request record")
    _require_matching_request(existing, approved)
    return {"request_id": request_id, "request_hash": approved["request_hash"], "status": "submitted"}
