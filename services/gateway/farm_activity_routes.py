"""FastAPI route registration for Gateway-operated farm activity records."""

def register_farm_activity_record_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.farm_activity_records import (
        FarmActivityRecordConflict,
        FarmActivityRecordInvalid,
        create_farm_activity_record,
        edit_farm_activity_record_draft,
        get_farm_activity_record,
        list_farm_activity_records,
        transition_farm_activity_record,
    )

    def _unavailable(exc):
        from services.common.logging import get_logger

        get_logger("gateway.farm_activity_records").warning(
            "Farm activity record operation unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Farm activity operation unavailable"},
            headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
        )

    def _disabled():
        return JSONResponse(
            status_code=404,
            content={"error": "Operator OIDC is disabled"},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    async def _invoke(function, *args, **kwargs):
        try:
            return await run_in_threadpool(function, *args, **kwargs)
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except FarmActivityRecordInvalid as exc:
            return JSONResponse(
                status_code=422,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except FarmActivityRecordConflict as exc:
            return JSONResponse(
                status_code=409,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "P0001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Farm activity state or review requirements prevent this operation"},
                    headers={"Cache-Control": "no-store", "Vary": "Cookie"},
                )
            return _unavailable(exc)

    @router.get("/operator/api/farm-activity-records")
    async def farm_activity_records(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
    ):
        if provider is None:
            return _disabled()
        result = await _invoke(
            list_farm_activity_records,
            request.state.operator_session.operator.operator_id,
            location_id,
            limit,
        )
        if isinstance(result, JSONResponse):
            return result
        return JSONResponse(
            {"data": jsonable_encoder(result), "location_id": location_id},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/farm-activity-records/published")
    async def published_farm_activity_records(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
    ):
        if provider is None:
            return _disabled()
        result = await _invoke(
            list_farm_activity_records,
            request.state.operator_session.operator.operator_id,
            location_id,
            limit,
            published_only=True,
        )
        if isinstance(result, JSONResponse):
            return result
        return JSONResponse(
            {"data": jsonable_encoder(result), "location_id": location_id},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/farm-activity-records/published/{activity_id}")
    async def published_farm_activity_record(
        request: Request, activity_id: str, location_id: str
    ):
        if provider is None:
            return _disabled()
        result = await _invoke(
            get_farm_activity_record,
            request.state.operator_session.operator.operator_id,
            activity_id,
            location_id,
            published_only=True,
        )
        if isinstance(result, JSONResponse):
            return result
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Published farm activity record not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            {"data": jsonable_encoder(result)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/farm-activity-records/{activity_id}")
    async def farm_activity_record(request: Request, activity_id: str, location_id: str):
        if provider is None:
            return _disabled()
        result = await _invoke(
            get_farm_activity_record,
            request.state.operator_session.operator.operator_id,
            activity_id,
            location_id,
        )
        if isinstance(result, JSONResponse):
            return result
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Farm activity record not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            {"data": jsonable_encoder(result)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.post("/operator/api/farm-activity-records")
    async def create_farm_activity_record_route(
        request: Request, location_id: str, body: dict
    ):
        if provider is None:
            return _disabled()
        if set(body) != {"content"} or not isinstance(body.get("content"), dict):
            return JSONResponse(
                status_code=422,
                content={"error": "Create body must contain only a content object"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        result = await _invoke(
            create_farm_activity_record,
            request.state.operator_session.operator.operator_id,
            location_id,
            body["content"],
        )
        if isinstance(result, JSONResponse):
            return result
        return JSONResponse(
            {"data": jsonable_encoder(result)},
            status_code=201,
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.patch("/operator/api/farm-activity-records/{activity_id}/draft")
    async def edit_farm_activity_record_route(
        request: Request, activity_id: str, location_id: str, body: dict
    ):
        if provider is None:
            return _disabled()
        if set(body) != {"content", "reason"} or not isinstance(body.get("content"), dict):
            return JSONResponse(
                status_code=422,
                content={"error": "Draft edit body requires content and a correction reason"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        result = await _invoke(
            edit_farm_activity_record_draft,
            request.state.operator_session.operator.operator_id,
            activity_id,
            location_id,
            body["content"],
            body["reason"],
        )
        if isinstance(result, JSONResponse):
            return result
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Editable draft farm activity record not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            {"data": jsonable_encoder(result)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.post("/operator/api/farm-activity-records/{activity_id}/{action}")
    async def transition_farm_activity_record_route(
        request: Request, activity_id: str, action: str, location_id: str, body: dict | None = None
    ):
        if provider is None:
            return _disabled()
        body = body or {}
        if set(body) - {"reason"}:
            return JSONResponse(
                status_code=422,
                content={"error": "Transition body accepts only a reason"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        result = await _invoke(
            transition_farm_activity_record,
            request.state.operator_session.operator.operator_id,
            activity_id,
            location_id,
            action,
            body.get("reason"),
        )
        if isinstance(result, JSONResponse):
            return result
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Farm activity record not found or transition grant unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            {"data": jsonable_encoder(result)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
