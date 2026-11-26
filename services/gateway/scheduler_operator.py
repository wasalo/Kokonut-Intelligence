"""Authenticated, audited Gateway controls for durable scheduler definitions."""

from __future__ import annotations

import re
from contextlib import closing
from typing import Any
from uuid import UUID

import psycopg2
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ConfigDict, Field

from services.common.database import get_db

_SESSION_TOKEN_HASH = re.compile(r"[0-9a-f]{64}")
_NO_STORE_HEADERS = {"Cache-Control": "no-store", "Vary": "Cookie"}


class SchedulerOperatorReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2000)


class SchedulerOperatorEnableRequest(SchedulerOperatorReason):
    include_dependencies: bool = False


class SchedulerOperatorConflict(Exception):
    pass


def _connection():
    return get_db(connect_timeout=5)


def _list_tasks(limit: int) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    with closing(_connection()) as connection:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """SELECT id, name, module_path, cron_expression, depends_on,
                              dependency_mode, is_enabled, next_run_at, last_status,
                              retry_at
                         FROM public.scheduled_task
                        ORDER BY name, id
                        LIMIT %s""",
                    (limit,),
                )
                items = [dict(row) for row in cursor.fetchall()]
    return {"items": jsonable_encoder(items), "returned": len(items)}


def _task_rows(cursor) -> list[dict[str, Any]]:
    cursor.execute(
        """SELECT id, name, module_path, command_args, cron_expression,
                  depends_on, dependency_mode, is_enabled, next_run_at,
                  retry_at, last_status
             FROM public.scheduled_task
            ORDER BY name, id"""
    )
    return [dict(row) for row in cursor.fetchall()]


def _enabled_dependents(task_id: str, tasks: list[dict[str, Any]]) -> list[str]:
    by_id = {str(task["id"]): task for task in tasks}
    dependents = []
    for task in tasks:
        if not task["is_enabled"] or str(task["id"]) == task_id:
            continue
        pending = [str(value) for value in (task.get("depends_on") or [])]
        visited = set()
        while pending:
            dependency_id = pending.pop()
            if dependency_id == task_id:
                dependents.append(task["name"])
                break
            if dependency_id in visited:
                continue
            visited.add(dependency_id)
            dependency = by_id.get(dependency_id)
            if dependency is not None:
                pending.extend(str(value) for value in (dependency.get("depends_on") or []))
    return sorted(dependents)


def _set_task_enabled(
    session_token_hash: str,
    task_id: UUID,
    action: str,
    reason: str,
    *,
    include_dependencies: bool = False,
) -> dict[str, Any]:
    if not isinstance(session_token_hash, str) or not _SESSION_TOKEN_HASH.fullmatch(session_token_hash):
        raise ValueError("operator session proof is invalid")
    normalized_reason = reason.strip()
    if action not in {"enable", "disable"} or not 1 <= len(normalized_reason) <= 2000:
        raise ValueError("a valid scheduler action and reason are required")

    with closing(_connection()) as connection:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SET LOCAL lock_timeout = '5s'")
                # Match scheduler activation's lock: validation, mutation and audit
                # must observe one definition snapshot and commit as one unit.
                cursor.execute("LOCK TABLE public.scheduled_task IN EXCLUSIVE MODE")
                tasks = _task_rows(cursor)
                by_id = {str(task["id"]): task for task in tasks}
                target = by_id.get(str(task_id))
                if target is None:
                    raise LookupError("scheduled task not found")

                changed: list[dict[str, Any]] = []
                if action == "enable":
                    from services.common.database import DatabaseConnection
                    from services.scheduler.activation import enable_schedule

                    try:
                        enabled_names = enable_schedule(
                            DatabaseConnection(connection=connection),
                            target["name"],
                            include_dependencies=include_dependencies,
                        )
                    except ValueError as exc:
                        raise SchedulerOperatorConflict(str(exc)) from exc
                    enabled_names = set(enabled_names)
                    changed = [task for task in tasks if task["name"] in enabled_names]
                else:
                    if target["is_enabled"]:
                        if target.get("retry_at") is not None or target.get("last_status") == "running":
                            raise SchedulerOperatorConflict(
                                "reconcile running or retrying work before disabling this task"
                            )
                        dependents = _enabled_dependents(str(task_id), tasks)
                        if dependents:
                            raise SchedulerOperatorConflict(
                                "disable enabled dependent tasks first: " + ", ".join(dependents)
                            )
                        cursor.execute(
                            """UPDATE public.scheduled_task
                                  SET is_enabled = FALSE, updated_at = pg_catalog.clock_timestamp()
                                WHERE id = %s AND is_enabled
                                RETURNING id, name""",
                            (task_id,),
                        )
                        row = cursor.fetchone()
                        if row is not None:
                            changed = [dict(row)]

                audit_ids = []
                for task in changed:
                    cursor.execute(
                        """SELECT kokonut_security.audit_scheduler_operator_action(
                                   %s, %s, %s, %s
                               ) AS id""",
                        (session_token_hash, task["id"], action, normalized_reason),
                    )
                    audit_ids.append(str(cursor.fetchone()["id"]))

    return {
        "action": action,
        "task_id": str(task_id),
        "changed": [task["name"] for task in changed],
        "already_applied": not changed,
        "audit_ids": audit_ids,
    }


def _error_response(error: Exception) -> JSONResponse:
    if isinstance(error, SchedulerOperatorConflict):
        return JSONResponse(
            status_code=409,
            content={"error": "scheduler_action_conflict", "detail": str(error)},
            headers=_NO_STORE_HEADERS,
        )
    if isinstance(error, LookupError):
        return JSONResponse(
            status_code=404,
            content={"error": "scheduler_task_not_found"},
            headers=_NO_STORE_HEADERS,
        )
    if isinstance(error, ValueError) or (
        isinstance(error, psycopg2.Error) and error.pgcode == "22023"
    ):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_scheduler_operator_request"},
            headers=_NO_STORE_HEADERS,
        )
    if isinstance(error, psycopg2.Error) and error.pgcode == "42501":
        return JSONResponse(
            status_code=403,
            content={"error": "scheduler_operator_capability_required"},
            headers=_NO_STORE_HEADERS,
        )
    if isinstance(error, psycopg2.Error) and error.pgcode == "P0002":
        return JSONResponse(
            status_code=404,
            content={"error": "scheduler_task_not_found"},
            headers=_NO_STORE_HEADERS,
        )
    from services.common.logging import get_logger

    get_logger("gateway.scheduler_operator").warning(
        "Scheduler operator request failed (%s)", type(error).__name__
    )
    return JSONResponse(
        status_code=503,
        content={"error": "scheduler_operator_unavailable"},
        headers={**_NO_STORE_HEADERS, "Retry-After": "30"},
    )


def create_scheduler_operator_router() -> APIRouter:
    router = APIRouter()

    @router.get("/operator/api/scheduler/tasks")
    def get_tasks(request: Request, limit: int = Query(default=50, ge=1, le=100)):
        if getattr(request.state, "operator_session", None) is None:
            raise HTTPException(status_code=401, detail="operator session required")
        try:
            result = _list_tasks(limit)
        except Exception as exc:
            return _error_response(exc)
        return JSONResponse(content=result, headers=_NO_STORE_HEADERS)

    @router.post("/operator/api/scheduler/tasks/{task_id}/enable")
    def enable_task(task_id: UUID, body: SchedulerOperatorEnableRequest, request: Request):
        operator_session = getattr(request.state, "operator_session", None)
        if operator_session is None:
            raise HTTPException(status_code=401, detail="operator session required")
        try:
            result = _set_task_enabled(
                operator_session.session_token_hash,
                task_id,
                "enable",
                body.reason,
                include_dependencies=body.include_dependencies,
            )
        except Exception as exc:
            return _error_response(exc)
        return JSONResponse(content=result, headers=_NO_STORE_HEADERS)

    @router.post("/operator/api/scheduler/tasks/{task_id}/disable")
    def disable_task(task_id: UUID, body: SchedulerOperatorReason, request: Request):
        operator_session = getattr(request.state, "operator_session", None)
        if operator_session is None:
            raise HTTPException(status_code=401, detail="operator session required")
        try:
            result = _set_task_enabled(
                operator_session.session_token_hash,
                task_id,
                "disable",
                body.reason,
            )
        except Exception as exc:
            return _error_response(exc)
        return JSONResponse(content=result, headers=_NO_STORE_HEADERS)

    return router
