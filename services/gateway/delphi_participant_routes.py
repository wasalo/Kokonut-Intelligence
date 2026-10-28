"""Public capability-token routes for pseudonymous Delphi participants."""

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


def _strict_uuid(value):
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise ValueError("UUID values must be strings")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError("UUID value is invalid") from exc


_StrictUuid = Annotated[UUID, BeforeValidator(_strict_uuid)]


class _DelphiParticipantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class _DelphiParticipantWorkspaceStudy(_DelphiParticipantResponse):
    study_id: _StrictUuid
    title: str = Field(max_length=255)
    status: Literal["draft", "open", "closed"]
    opened_at: AwareDatetime | None
    closed_at: AwareDatetime | None


class _DelphiParticipantWorkspaceItem(_DelphiParticipantResponse):
    item_id: _StrictUuid
    label: str = Field(max_length=255)
    description: str | None
    item_type: Literal["issue", "goal", "option"]
    scale: Literal[
        "desirability",
        "feasibility_technical",
        "feasibility_political",
        "probability",
    ]
    minimum: float | None = Field(strict=True)
    maximum: float | None = Field(strict=True)
    my_score: float | None = Field(strict=True, ge=-9999.9999, le=9999.9999)
    my_reasoning: str | None
    my_updated_at: AwareDatetime | None

    @model_validator(mode="after")
    def validate_scale_bounds(self):
        if self.minimum is not None and self.maximum is not None:
            if self.minimum >= self.maximum:
                raise ValueError("Delphi item minimum must be less than maximum")
        return self


class _DelphiParticipantWorkspaceResponse(_DelphiParticipantResponse):
    study: _DelphiParticipantWorkspaceStudy
    items: list[_DelphiParticipantWorkspaceItem] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    collection_scopes: list[Literal["questionnaire_responses", "minority_reports"]] = Field(
        max_length=2
    )

    @model_validator(mode="after")
    def validate_page(self):
        if len(set(self.collection_scopes)) != len(self.collection_scopes):
            raise ValueError("Delphi participant collection scopes must be unique")
        if len(self.items) > self.limit:
            raise ValueError("Delphi participant page exceeds its requested limit")
        if self.has_more and len(self.items) != self.limit:
            raise ValueError("Delphi participant continuation requires a full page")
        return self

    def validate_request(self, *, limit: int, offset: int):
        if self.limit != limit or self.offset != offset:
            raise ValueError("Delphi participant page does not match the request")
        if self.has_more and offset + limit > 10_000:
            # The next offset must remain within the database function's accepted
            # range. The current page remains available at the terminal boundary.
            return self.model_copy(update={"has_more": False})
        return self


def register_delphi_participant_routes(router, run_in_threadpool, psycopg2):
    import hmac
    import json
    from pathlib import Path

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import FileResponse, JSONResponse
    from starlette.requests import Request

    from services.gateway.delphi_participant_acceptance import (
        DelphiParticipantAcceptanceInvalid,
        accept_location_delphi_participant_invite,
        preview_location_delphi_participant_invite,
        withdraw_location_delphi_participant,
    )
    from services.gateway.delphi_participant_minority_reports import (
        DelphiParticipantMinorityReportInvalid,
        submit_location_delphi_participant_minority_report,
    )
    from services.gateway.delphi_participant_workspace import (
        DelphiParticipantWorkspaceInvalid,
        get_location_delphi_participant_workspace,
        submit_location_delphi_participant_contribution,
    )

    session_cookie = "kokonut_delphi_participant_session"
    csrf_cookie = "kokonut_delphi_participant_csrf"
    app_dir = Path(__file__).resolve().parents[2] / "apps" / "delphi-participant"
    headers = {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "Vary": "Cookie",
    }
    page_headers = {
        **headers,
        "Content-Security-Policy": (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; base-uri 'none'; form-action 'self'; "
            "frame-ancestors 'none'; object-src 'none'"
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }

    @router.get("/participation/delphi")
    async def participant_page():
        return FileResponse(
            app_dir / "index.html",
            media_type="text/html",
            headers=page_headers,
        )

    @router.get("/participation/delphi/app.js")
    async def participant_script():
        return FileResponse(
            app_dir / "app.js",
            media_type="application/javascript",
            headers={**headers, "X-Content-Type-Options": "nosniff"},
        )

    @router.get("/participation/delphi/styles.css")
    async def participant_styles():
        return FileResponse(
            app_dir / "styles.css",
            media_type="text/css",
            headers={**headers, "X-Content-Type-Options": "nosniff"},
        )

    async def read_json_object(request: Request):
        body = await request.body()
        if len(body) > 16384:
            return None, JSONResponse(
                status_code=413,
                content={"error": "Delphi participant request is too large"},
                headers=headers,
            )
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "A JSON Delphi participant object is required"},
                headers=headers,
            )
        return payload, None

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=401,
                content={"error": "Delphi participant access is invalid or unavailable"},
                headers=headers,
            )
        if code in {"55000", "23505", "23514"}:
            return JSONResponse(
                status_code=409,
                content={"error": "Delphi participant state changed; reload and try again"},
                headers=headers,
            )
        if code in {"22023", "22P02"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi participant request is invalid"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.delphi_participant").warning(
            "Delphi participant request unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Delphi participant service unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    @router.post("/participation/delphi/preview")
    async def preview_invite(request: Request):
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        if set(payload) != {"invite_token"} or not isinstance(payload.get("invite_token"), str):
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi invite preview fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                preview_location_delphi_participant_invite,
                payload["invite_token"],
            )
        except DelphiParticipantAcceptanceInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/participation/delphi/accept")
    async def accept_invite(request: Request):
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        expected = {
            "invite_token",
            "notice_digest",
            "session_token",
            "csrf_token",
            "request_id",
            "accepted",
        }
        if (
            set(payload) != expected
            or not all(isinstance(payload.get(key), str) for key in expected - {"accepted"})
            or not isinstance(payload.get("accepted"), bool)
            or payload.get("accepted") is not True
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Explicit Delphi consent acceptance is required"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                accept_location_delphi_participant_invite,
                payload["invite_token"],
                payload["notice_digest"],
                payload["session_token"],
                payload["csrf_token"],
                payload["request_id"],
                accepted=payload["accepted"],
            )
        except DelphiParticipantAcceptanceInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        response = JSONResponse(
            jsonable_encoder({
                "status": result["status"],
                "notice_version": result["notice_version"],
                "accepted_at": result["accepted_at"],
                "session_expires_at": result["session_expires_at"],
                "replayed": result["replayed"],
            }),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )
        # The browser creates both random values before submitting consent, so it
        # can repeat a lost response exactly. They are never echoed in JSON.
        response.set_cookie(
            session_cookie,
            payload["session_token"],
            max_age=30 * 24 * 60 * 60,
            path="/api/participation/delphi",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        response.set_cookie(
            csrf_cookie,
            payload["csrf_token"],
            max_age=30 * 24 * 60 * 60,
            path="/api/participation/delphi",
            secure=True,
            httponly=False,
            samesite="strict",
        )
        return response

    @router.post("/participation/delphi/withdraw")
    async def withdraw(request: Request):
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        if set(payload) != {"request_id"} or not isinstance(payload.get("request_id"), str):
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi withdrawal request fields are invalid"},
                headers=headers,
            )
        session_token = request.cookies.get(session_cookie, "")
        csrf_cookie_value = request.cookies.get(csrf_cookie, "")
        csrf_header_value = request.headers.get("x-kokonut-csrf", "")
        if (
            not csrf_cookie_value
            or not csrf_header_value
            or not hmac.compare_digest(csrf_cookie_value, csrf_header_value)
        ):
            return JSONResponse(
                status_code=403,
                content={"error": "Delphi withdrawal CSRF validation failed"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                withdraw_location_delphi_participant,
                session_token,
                csrf_header_value,
                payload["request_id"],
            )
        except DelphiParticipantAcceptanceInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        response = JSONResponse(jsonable_encoder(result), headers=headers)
        response.delete_cookie(
            session_cookie,
            path="/api/participation/delphi",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        response.delete_cookie(
            csrf_cookie,
            path="/api/participation/delphi",
            secure=True,
            httponly=False,
            samesite="strict",
        )
        return response

    @router.get(
        "/participation/delphi/workspace",
        response_model=_DelphiParticipantWorkspaceResponse,
    )
    async def participant_workspace(
        request: Request,
        limit: int = Query(default=50, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        session_token = request.cookies.get(session_cookie, "")
        if not session_token:
            return JSONResponse(
                status_code=401,
                content={"error": "A valid Delphi participant session is required"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_delphi_participant_workspace,
                session_token,
                limit=limit,
                offset=offset,
            )
        except DelphiParticipantWorkspaceInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        try:
            response_payload = jsonable_encoder(result)
            validated = _DelphiParticipantWorkspaceResponse.model_validate_json(
                json.dumps(response_payload), strict=True
            ).validate_request(limit=limit, offset=offset)
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.delphi_participant").warning(
                "Delphi participant workspace response violated its contract (%s)",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Delphi participant service unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        if not validated.has_more and response_payload.get("has_more") is True:
            response_payload["has_more"] = False
        return JSONResponse(response_payload, headers=headers)

    @router.post("/participation/delphi/contributions")
    async def submit_contribution(request: Request):
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        expected = {"item_id", "score", "reasoning", "request_id"}
        if (
            set(payload) != expected
            or not isinstance(payload.get("item_id"), str)
            or isinstance(payload.get("score"), bool)
            or not isinstance(payload.get("score"), (int, float))
            or payload.get("reasoning") is not None
               and not isinstance(payload.get("reasoning"), str)
            or not isinstance(payload.get("request_id"), str)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi contribution fields are invalid"},
                headers=headers,
            )
        session_token = request.cookies.get(session_cookie, "")
        if not session_token:
            return JSONResponse(
                status_code=401,
                content={"error": "A valid Delphi participant session is required"},
                headers=headers,
            )
        csrf_cookie_value = request.cookies.get(csrf_cookie, "")
        csrf_header_value = request.headers.get("x-kokonut-csrf", "")
        if (
            not csrf_cookie_value
            or not csrf_header_value
            or not hmac.compare_digest(csrf_cookie_value, csrf_header_value)
        ):
            return JSONResponse(
                status_code=403,
                content={"error": "Delphi contribution CSRF validation failed"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_delphi_participant_contribution,
                session_token,
                csrf_header_value,
                payload["item_id"],
                payload["score"],
                payload["reasoning"],
                payload["request_id"],
            )
        except DelphiParticipantWorkspaceInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/participation/delphi/minority-reports")
    async def submit_minority_report(request: Request):
        payload, error = await read_json_object(request)
        if error is not None:
            return error
        expected = {
            "item_id",
            "title",
            "position_summary",
            "rationale",
            "implications",
            "request_id",
        }
        if (
            set(payload) != expected
            or (payload.get("item_id") is not None and not isinstance(payload.get("item_id"), str))
            or not all(
                isinstance(payload.get(key), str)
                for key in ("title", "position_summary", "rationale", "request_id")
            )
            or (payload.get("implications") is not None
                and not isinstance(payload.get("implications"), str))
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi minority-report fields are invalid"},
                headers=headers,
            )
        session_token = request.cookies.get(session_cookie, "")
        if not session_token:
            return JSONResponse(
                status_code=401,
                content={"error": "A valid Delphi participant session is required"},
                headers=headers,
            )
        csrf_cookie_value = request.cookies.get(csrf_cookie, "")
        csrf_header_value = request.headers.get("x-kokonut-csrf", "")
        if (
            not csrf_cookie_value
            or not csrf_header_value
            or not hmac.compare_digest(csrf_cookie_value, csrf_header_value)
        ):
            return JSONResponse(
                status_code=403,
                content={"error": "Delphi minority-report CSRF validation failed"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_delphi_participant_minority_report,
                session_token,
                csrf_header_value,
                item_id=payload["item_id"],
                title=payload["title"],
                position_summary=payload["position_summary"],
                rationale=payload["rationale"],
                implications=payload["implications"],
                request_id=payload["request_id"],
            )
        except DelphiParticipantMinorityReportInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )
