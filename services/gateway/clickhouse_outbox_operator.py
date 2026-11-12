from __future__ import annotations

import os
import re
from contextlib import closing
from typing import Any
from uuid import UUID

import psycopg2
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from services.common.db import PG_DB, PG_HOST, PG_PORT

_OPERATOR_LOGIN = "kokonut_clickhouse_outbox_operator_login"
_SESSION_TOKEN_HASH = re.compile(r"[0-9a-f]{64}")
_NO_STORE_HEADERS = {"Cache-Control": "no-store", "Vary": "Cookie"}


class OperatorOutboxError(Exception):
    pass


class OperatorOutboxConfigurationError(OperatorOutboxError):
    pass


class OperatorOutboxForbidden(OperatorOutboxError):
    pass


class OperatorOutboxNotFound(OperatorOutboxError):
    pass


class OperatorOutboxInvalidRequest(OperatorOutboxError):
    pass


class OperatorOutboxReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2000)


def _operator_action_connection():
    password = os.environ.get("KOKONUT_CLICKHOUSE_OUTBOX_OPERATOR_PASSWORD", "")
    if not password:
        raise OperatorOutboxConfigurationError
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=_OPERATOR_LOGIN,
        password=password,
        connect_timeout=5,
        application_name="kokonut-clickhouse-outbox-operator",
    )


def _call_operator_function(statement: str, parameters: tuple[Any, ...]) -> Any:
    try:
        with closing(_operator_action_connection()) as connection:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(statement, parameters)
                    row = cursor.fetchone()
                    if row is None:
                        raise OperatorOutboxNotFound
                    return row[0]
    except psycopg2.Error as exc:
        if exc.pgcode == "42501":
            raise OperatorOutboxForbidden from exc
        if exc.pgcode == "P0002":
            raise OperatorOutboxNotFound from exc
        if exc.pgcode == "22023":
            raise OperatorOutboxInvalidRequest from exc
        raise


def list_dead_letters(session_token_hash: str, limit: int) -> dict[str, Any]:
    if not _SESSION_TOKEN_HASH.fullmatch(session_token_hash) or not 1 <= limit <= 100:
        raise OperatorOutboxInvalidRequest
    return _call_operator_function(
        "SELECT kokonut_security.list_clickhouse_outbox_operator_dead_letters(%s, %s)",
        (session_token_hash, limit),
    )


def transition_dead_letter(
    session_token_hash: str,
    outbox_id: UUID,
    action: str,
    reason: str,
) -> dict[str, Any]:
    if not _SESSION_TOKEN_HASH.fullmatch(session_token_hash):
        raise OperatorOutboxInvalidRequest
    normalized_reason = reason.strip()
    if action not in {"replay", "resolve", "discard"} or not normalized_reason:
        raise OperatorOutboxInvalidRequest
    return _call_operator_function(
        "SELECT kokonut_security.transition_clickhouse_outbox_operator_dead_letter(%s, %s, %s, %s)",
        (session_token_hash, outbox_id, action, normalized_reason),
    )


def _error_response(error: OperatorOutboxError) -> JSONResponse:
    if isinstance(error, OperatorOutboxConfigurationError):
        return JSONResponse(
            status_code=503,
            content={"error": "operator_outbox_unavailable"},
            headers={**_NO_STORE_HEADERS, "Retry-After": "30"},
        )
    if isinstance(error, OperatorOutboxForbidden):
        return JSONResponse(
            status_code=403,
            content={"error": "operator_outbox_capability_required"},
            headers=_NO_STORE_HEADERS,
        )
    if isinstance(error, OperatorOutboxNotFound):
        return JSONResponse(
            status_code=404,
            content={"error": "operator_outbox_item_not_found"},
            headers=_NO_STORE_HEADERS,
        )
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_operator_outbox_request"},
        headers=_NO_STORE_HEADERS,
    )


def create_clickhouse_outbox_router() -> APIRouter:
    router = APIRouter()

    @router.get("/operator/api/clickhouse-outbox/dead-letters")
    def get_dead_letters(request: Request, limit: int = Query(default=50, ge=1, le=100)):
        operator_session = getattr(request.state, "operator_session", None)
        if operator_session is None:
            raise HTTPException(status_code=401, detail="operator session required")
        try:
            result = list_dead_letters(operator_session.session_token_hash, limit)
        except OperatorOutboxError as exc:
            return _error_response(exc)
        except Exception as exc:
            from services.common.logging import get_logger

            get_logger("gateway.clickhouse_outbox").warning(
                "Operator outbox list failed (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "operator_outbox_unavailable"},
                headers={**_NO_STORE_HEADERS, "Retry-After": "30"},
            )
        return JSONResponse(content=result, headers=_NO_STORE_HEADERS)

    @router.post("/operator/api/clickhouse-outbox/dead-letters/{outbox_id}/replay")
    def replay_dead_letter(
        outbox_id: UUID, body: OperatorOutboxReason, request: Request
    ):
        operator_session = getattr(request.state, "operator_session", None)
        if operator_session is None:
            raise HTTPException(status_code=401, detail="operator session required")
        try:
            result = transition_dead_letter(
                operator_session.session_token_hash, outbox_id, "replay", body.reason
            )
        except OperatorOutboxError as exc:
            return _error_response(exc)
        except Exception as exc:
            from services.common.logging import get_logger

            get_logger("gateway.clickhouse_outbox").warning(
                "Operator outbox replay failed (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "operator_outbox_unavailable"},
                headers={**_NO_STORE_HEADERS, "Retry-After": "30"},
            )
        return JSONResponse(content=result, headers=_NO_STORE_HEADERS)

    @router.post("/operator/api/clickhouse-outbox/dead-letters/{outbox_id}/resolve")
    def resolve_dead_letter(
        outbox_id: UUID, body: OperatorOutboxReason, request: Request
    ):
        operator_session = getattr(request.state, "operator_session", None)
        if operator_session is None:
            raise HTTPException(status_code=401, detail="operator session required")
        try:
            result = transition_dead_letter(
                operator_session.session_token_hash, outbox_id, "resolve", body.reason
            )
        except OperatorOutboxError as exc:
            return _error_response(exc)
        except Exception as exc:
            from services.common.logging import get_logger

            get_logger("gateway.clickhouse_outbox").warning(
                "Operator outbox resolve failed (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "operator_outbox_unavailable"},
                headers={**_NO_STORE_HEADERS, "Retry-After": "30"},
            )
        return JSONResponse(content=result, headers=_NO_STORE_HEADERS)

    @router.post("/operator/api/clickhouse-outbox/dead-letters/{outbox_id}/discard")
    def discard_dead_letter(
        outbox_id: UUID, body: OperatorOutboxReason, request: Request
    ):
        operator_session = getattr(request.state, "operator_session", None)
        if operator_session is None:
            raise HTTPException(status_code=401, detail="operator session required")
        try:
            result = transition_dead_letter(
                operator_session.session_token_hash, outbox_id, "discard", body.reason
            )
        except OperatorOutboxError as exc:
            return _error_response(exc)
        except Exception as exc:
            from services.common.logging import get_logger

            get_logger("gateway.clickhouse_outbox").warning(
                "Operator outbox discard failed (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "operator_outbox_unavailable"},
                headers={**_NO_STORE_HEADERS, "Retry-After": "30"},
            )
        return JSONResponse(content=result, headers=_NO_STORE_HEADERS)

    return router
