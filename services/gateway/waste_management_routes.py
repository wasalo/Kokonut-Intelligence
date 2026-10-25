"""OIDC routes for location-scoped waste summaries and capture."""

import json


def register_waste_management_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.waste_management_reads import get_location_waste_summary
    from services.gateway.waste_management_writes import (
        WasteManagementWriteInvalid,
        create_location_composting_record,
        create_location_recycling_record,
        create_location_waste_stream_record,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    async def bounded_payload(request: Request):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 4096:
                    return None, JSONResponse(
                        status_code=413,
                        content={"error": "Waste capture body exceeds 4 KB"},
                        headers=headers,
                    )
            except ValueError:
                return None, JSONResponse(
                    status_code=400,
                    content={"error": "Invalid content length"},
                    headers=headers,
                )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                return None, JSONResponse(
                    status_code=413,
                    content={"error": "Waste capture body exceeds 4 KB"},
                    headers=headers,
                )
        try:
            payload = json.loads(body)
        except (ValueError, RecursionError):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Waste capture body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Waste capture body must be an object"},
                headers=headers,
            )
        return payload, None

    @router.get("/operator/api/waste/{location_id}/summary")
    async def waste_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_waste_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Waste summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Waste summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/waste/{location_id}/records")
    async def create_waste_record(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_waste_stream_record,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified waste capture access is required"},
                headers=headers,
            )
        except WasteManagementWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location waste-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Waste capture input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Waste capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Waste capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/operator/api/waste/{location_id}/composting")
    async def create_composting_record(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_composting_record,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified composting capture access is required"},
                headers=headers,
            )
        except WasteManagementWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location waste-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Composting input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Composting capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Composting capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/operator/api/waste/{location_id}/recycling")
    async def create_recycling_record(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_recycling_record,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified recycling capture access is required"},
                headers=headers,
            )
        except WasteManagementWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location waste-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Recycling input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.waste").warning(
                "Recycling capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Recycling capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )
