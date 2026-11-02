"""OIDC route registration for tenant-scoped true-cost summaries."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_CapitalType = Literal["natural", "human", "social", "produced", "financial"]


class _TrueCostResponseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, populate_by_name=True
    )


class TrueCostStatementResponse(_TrueCostResponseModel):
    location_id: UUID
    market_costs_usd: float
    market_revenue_usd: float
    market_profit_usd: float
    hidden_costs_usd: float
    natural_capital_value_usd: float
    social_capital_value_usd: float
    true_profit_usd: float
    true_profit_margin_pct: float
    hidden_cost_ratio_pct: float


class HiddenCostCategoryResponse(_TrueCostResponseModel):
    category: Literal[
        "pollution", "health", "social", "environmental", "knowledge",
        "intergenerational", "other",
    ]
    total_usd: float


class HiddenCostDetailResponse(_TrueCostResponseModel):
    category: Literal[
        "pollution", "health", "social", "environmental", "knowledge",
        "intergenerational", "other",
    ]
    subcategory: Literal[
        "water_pollution", "soil_degradation", "pesticide_exposure",
        "cultural_erosion", "biodiversity_loss", "habitat_fragmentation",
        "air_pollution", "noise_pollution", "waste_disposal",
        "healthcare_cost", "lost_labor_days", "social_displacement",
        "knowledge_loss", "resource_depletion", "climate_damage", "other",
    ]
    count: int = Field(ge=0, strict=True)
    total_usd: float
    avg_usd: float


class HiddenCostSummaryResponse(_TrueCostResponseModel):
    location_id: UUID
    total_hidden_costs_usd: float
    total_observations: int = Field(ge=0, strict=True)
    by_category: list[HiddenCostCategoryResponse]
    details: list[HiddenCostDetailResponse]


class NaturalCapitalTypeResponse(_TrueCostResponseModel):
    capital_type: Literal[
        "carbon", "biodiversity", "water", "soil", "pollination",
        "watershed", "air_quality", "other",
    ]
    count: int = Field(ge=0, strict=True)
    total_quantity: float
    avg_price_per_unit: float
    total_value_usd: float


class NaturalCapitalSummaryResponse(_TrueCostResponseModel):
    location_id: UUID
    total_natural_capital_value_usd: float
    by_type: list[NaturalCapitalTypeResponse]


class SocialImpactCategoryResponse(_TrueCostResponseModel):
    category: Literal[
        "training", "governance", "cultural_preservation", "health",
        "community", "gender_equity", "education", "other",
    ]
    count: int = Field(ge=0, strict=True)
    total_beneficiaries: int = Field(ge=0, strict=True)
    total_value_usd: float
    avg_value_per_intervention: float


class SocialImpactSummaryResponse(_TrueCostResponseModel):
    location_id: UUID
    total_social_impact_value_usd: float
    total_beneficiaries: int = Field(ge=0, strict=True)
    by_category: list[SocialImpactCategoryResponse]


class CapitalFlowResponse(_TrueCostResponseModel):
    from_capital: _CapitalType
    to_capital: _CapitalType
    flow_type: Literal["investment", "depletion", "regeneration", "transfer"]
    count: int = Field(ge=0, strict=True)
    total_value_usd: float


class CapitalFlowSummaryResponse(_TrueCostResponseModel):
    location_id: UUID
    total_flows: int = Field(ge=0, strict=True)
    total_flow_value_usd: float
    flows: list[CapitalFlowResponse]
    investments_by_capital: dict[_CapitalType, float]
    returns_by_capital: dict[_CapitalType, float]


class CrossCapitalDependencyResponse(_TrueCostResponseModel):
    from_capital: _CapitalType = Field(alias="from")
    to_capital: _CapitalType = Field(alias="to")
    value_usd: float


class CrossCapitalDependenciesResponse(_TrueCostResponseModel):
    location_id: UUID
    dependency_matrix: dict[_CapitalType, dict[_CapitalType, float]]
    cross_capital_value_usd: float
    interdependency_ratio: float
    key_dependencies: list[CrossCapitalDependencyResponse]
    interdependency_score: float


class TrueCostSummaryResponse(_TrueCostResponseModel):
    location_id: UUID
    true_cost_statement: TrueCostStatementResponse
    hidden_costs: HiddenCostSummaryResponse
    natural_capital: NaturalCapitalSummaryResponse
    social_impact: SocialImpactSummaryResponse
    capital_flows: CapitalFlowSummaryResponse
    cross_capital_dependencies: CrossCapitalDependenciesResponse


def register_true_cost_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.true_cost import get_true_cost_summary

    @router.get(
        "/operator/api/true-cost/{location_id}/summary",
        response_model=TrueCostSummaryResponse,
    )
    async def true_cost_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            summary = await run_in_threadpool(
                get_true_cost_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.true_cost").warning(
                "True-cost summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "True-cost summary unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )

        try:
            validated = TrueCostSummaryResponse.model_validate(summary)
            if validated.location_id != UUID(location_id):
                raise ValueError("True-cost summary location does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.true_cost").warning(
                "True-cost summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "True-cost summary unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json", by_alias=True)),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
