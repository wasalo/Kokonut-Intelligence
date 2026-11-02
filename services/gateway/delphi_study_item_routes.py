"""OIDC route for adding questionnaire items to Delphi study drafts."""


def register_delphi_study_item_routes(router, provider, run_in_threadpool, psycopg2):
    import json
    from uuid import UUID

    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from pydantic import ValidationError
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_study_item_responses import (
        DelphiStudyItemCreateResponse,
    )
    from services.gateway.delphi_study_items import (
        DelphiStudyItemInvalid,
        create_location_delphi_study_item,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.post(
        "/operator/api/delphi/{location_id}/studies/{study_id}/items",
        status_code=201,
        response_model=DelphiStudyItemCreateResponse,
        responses={200: {"model": DelphiStudyItemCreateResponse}},
    )
    async def create_study_item(request: Request, location_id: str, study_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "A Delphi study item object is required"},
                headers=headers,
            )
        allowed_fields = {
            "request_id",
            "item_type",
            "label",
            "description",
            "scale",
            "min_value",
            "max_value",
        }
        if not isinstance(payload, dict) or set(payload) - allowed_fields:
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi study item fields are invalid"},
                headers=headers,
            )
        if not {"request_id", "label"} <= set(payload):
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi study item requires request_id and label"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_location_delphi_study_item,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
                request_id=payload["request_id"],
                item_type=payload.get("item_type", "option"),
                label=payload["label"],
                description=payload.get("description"),
                scale=payload.get("scale", "desirability"),
                min_value=payload.get("min_value", -1),
                max_value=payload.get("max_value", 1),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi draft access is required"},
                headers=headers,
            )
        except DelphiStudyItemInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location Delphi draft grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The study is not an eligible draft or the request conflicts"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.delphi_study_item").warning(
                "Delphi study item unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Delphi study item unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            response = DelphiStudyItemCreateResponse.model_validate(result)
            if (
                response.location_id != UUID(location_id)
                or response.study_id != UUID(study_id)
            ):
                raise ValueError("Delphi study item response does not match requested scope")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.delphi_study_item").warning(
                "Delphi study item response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Delphi study item unavailable"},
                headers=headers,
            )

        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="python")),
            status_code=200 if response.replayed else 201,
            headers=headers,
        )
