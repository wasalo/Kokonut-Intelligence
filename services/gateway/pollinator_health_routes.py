"""OIDC route registration for location-scoped pollinator reads and capture."""

import json


def register_pollinator_health_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.pollinator_health_reads import (
        get_location_pollinator_habitat_details,
        get_location_pollinator_summary,
    )
    from services.gateway.pollinator_health_writes import (
        PollinatorObservationInvalid,
        create_location_pesticide_impact,
        create_location_pollinator_habitat,
        create_location_pollinator_hive,
        create_location_pollinator_observation,
        record_location_pollinator_hive_inspection,
        update_location_pollinator_habitat,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    async def bounded_payload(request: Request, *, max_bytes: int = 12 * 1024):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    return None, JSONResponse(
                        status_code=413,
                        content={"error": "Pollinator request body exceeds 12 KB"},
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
            if len(body) > max_bytes:
                return None, JSONResponse(
                    status_code=413,
                    content={"error": "Pollinator request body exceeds 12 KB"},
                    headers=headers,
                )
        try:
            payload = json.loads(body)
        except (ValueError, RecursionError):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Pollinator request body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Pollinator request body must be an object"},
                headers=headers,
            )
        return payload, None

    @router.get("/operator/api/pollinators/{location_id}/summary")
    async def pollinator_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_pollinator_summary,
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

            get_logger("gateway.pollinators").warning(
                "Pollinator summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pollinator summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/pollinators/{location_id}/habitats")
    async def pollinator_habitat_details(
        request: Request, location_id: str, limit: int = 50, offset: int = 0
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_pollinator_habitat_details,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified habitat detail access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-detail grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator habitat details unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pollinator habitat details unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/pollinators/{location_id}/observations")
    async def create_pollinator_observation(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_pollinator_observation,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified pollinator capture access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Pollinator observation input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pollinator capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/operator/api/pollinators/{location_id}/pesticide-impacts")
    async def create_pesticide_impact(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_pesticide_impact,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified pesticide-report capture access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Pesticide report input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pesticide report capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pesticide report capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/operator/api/pollinators/{location_id}/habitats")
    async def create_pollinator_habitat(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_pollinator_habitat,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified habitat capture access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Habitat report input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Habitat capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Habitat capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.patch("/operator/api/pollinators/{location_id}/habitats/{habitat_id}")
    async def update_pollinator_habitat(request: Request, location_id: str, habitat_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                update_location_pollinator_habitat,
                request.state.operator_session.operator.operator_id,
                location_id,
                habitat_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified habitat update access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-edit grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Habitat update input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different habitat input"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The habitat changed; reload it before applying this update"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Habitat not found in this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator habitat update unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pollinator habitat update unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200,
            headers=headers,
        )

    @router.post("/operator/api/pollinators/{location_id}/hives")
    async def create_pollinator_hive(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_pollinator_hive,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified hive capture access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Managed-hive input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The hive identifier exists or the request ID was reused with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Managed-hive capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Managed-hive capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/operator/api/pollinators/{location_id}/hives/inspections")
    async def record_pollinator_hive_inspection(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                record_location_pollinator_hive_inspection,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified hive inspection access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Hive inspection input or location-scoped hive identifier is invalid"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different inspection input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Hive inspection capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Hive inspection capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )
