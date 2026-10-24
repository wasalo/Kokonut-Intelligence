"""Keep registered operator routes aligned with their OIDC auth policies."""

from functools import reduce
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.operator_auth import (  # noqa: E402
    auth_route_policy,
    create_auth_router,
)

_LOCATION_ID = "11111111-1111-4111-8111-111111111111"
_PARAMETER_SAMPLES = {
    "location_id": _LOCATION_ID,
    "batch_id": "33333333-3333-4333-8333-333333333333",
    "prediction_id": "55555555-5555-4555-8555-555555555555",
    "realization_id": "33333333-3333-4333-8333-333333333333",
    "run_id": "44444444-4444-4444-8444-444444444444",
    "canvas_id": "22222222-2222-4222-8222-222222222222",
    "block_name": "key_partners",
    "enrollment_id": "22222222-2222-4222-8222-222222222222",
    "report_id": "33333333-3333-4333-8333-333333333333",
    "collection_id": "44444444-4444-4444-8444-444444444444",
    "activity_id": "55555555-5555-4555-8555-555555555555",
    "signal_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "claim_id": "e5000000-0000-4000-8000-000000000001",
    "tension_id": "66666666-6666-4666-8666-666666666666",
    "role_id": "77777777-7777-4777-8777-777777777777",
    "circle_id": "77777777-7777-4777-8777-777777777777",
    "definition_id": "77777777-7777-4777-8777-777777777777",
    "assignment_id": "88888888-8888-4888-8888-888888888888",
    "item_id": "99999999-9999-4999-8999-999999999999",
    "work_item_id": "e5000000-0000-4000-8000-000000000001",
    "session_id": "99999999-9999-4999-8999-999999999998",
    "device_id": "collector-1",
    "plan_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "case_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "retirement_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "solution_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "gate_id": "dddddddd-dddd-4ddd-8ddd-ddddddddddde",
    "assessment_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    "configuration_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    "experiment_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddf",
    "funding_case_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeed",
    "learning_record_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeec",
    "tranche_id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
    "proposal_id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
    "program_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    "replication_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    "party_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "profile_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddc",
    "resource_request_id": "dddddddd-dddd-4ddd-8ddd-ddddddddddcb",
    "draft_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "source_profile_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "recommendation_id": "99999999-9999-4999-8999-999999999997",
    "summary_id": "99999999-9999-4999-8999-999999999996",
    "study_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
}
_TRANSITION_ACTIONS = {
    "submit": "submit",
    "verify": "verify",
    "reject": "reject",
    "request-rework": "rework",
    "publish": "publish",
    "close-exception": "close_exception",
}


def _expected(
    resource,
    action,
    *,
    public=False,
    scoped=False,
    location_id=None,
    additional=(),
):
    return resource, action, public, scoped, location_id, tuple(sorted(additional))


_EXPECTED_OPERATOR_POLICIES = {
    ("GET", "/operator/"): _expected("operator_auth", "console", public=True),
    ("GET", "/operator/auth/login"): _expected("operator_auth", "login", public=True),
    ("GET", "/operator/auth/callback"): _expected("operator_auth", "callback", public=True),
    ("GET", "/operator/auth/session"): _expected("operator_auth", "read"),
    ("POST", "/operator/auth/logout"): _expected("operator_auth", "logout"),
    (
        "GET",
        "/operator/api/delphi/11111111-1111-4111-8111-111111111111/studies",
    ): _expected("delphi", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/delphi/11111111-1111-4111-8111-111111111111/recommendations",
    ): _expected("delphi", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/delphi/11111111-1111-4111-8111-111111111111/recommendations/99999999-9999-4999-8999-999999999997/decision",
    ): _expected("delphi", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/ai-summaries/11111111-1111-4111-8111-111111111111/reviews",
    ): _expected("ai_summary", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/ai-summaries/11111111-1111-4111-8111-111111111111/reviews/99999999-9999-4999-8999-999999999996/decision",
    ): _expected("ai_summary", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/ai-summaries/11111111-1111-4111-8111-111111111111/drafts",
    ): _expected("ai_summary", "draft", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/delphi/11111111-1111-4111-8111-111111111111/draft-studies",
    ): _expected("delphi", "draft", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/delphi/11111111-1111-4111-8111-111111111111/studies/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/recommendation-drafts",
    ): _expected("delphi", "draft", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/credit-custody/11111111-1111-4111-8111-111111111111/summary",
    ): _expected(
        "carbon_credit",
        "read",
        scoped=True,
        location_id=_LOCATION_ID,
        additional=(("credit_retirement", "read"),),
    ),
    (
        "GET",
        "/operator/api/ecocredits/11111111-1111-4111-8111-111111111111/batches",
    ): _expected("ecocredit", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/true-cost/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("true_cost_accounting", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/emergency-response/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("emergency_response", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/threatcasting/11111111-1111-4111-8111-111111111111/backcast-plans",
    ): _expected("threatcasting", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/threatcasting/11111111-1111-4111-8111-111111111111/backcast-plans/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    ): _expected("threatcasting", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/strategy/11111111-1111-4111-8111-111111111111/plans",
    ): _expected("strategy", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/competitive-landscape/11111111-1111-4111-8111-111111111111/summaries",
    ): _expected("competitive_landscape", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/management/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("management_workflow", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/planning/11111111-1111-4111-8111-111111111111/budgets",
    ): _expected("planning_budget", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/business-architecture/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("business_architecture", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/comprehensive-status/11111111-1111-4111-8111-111111111111",
    ): _expected("comprehensive_status", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/business-planning/11111111-1111-4111-8111-111111111111/canvases",
    ): _expected("business_planning", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/business-planning/11111111-1111-4111-8111-111111111111/canvases",
    ): _expected("business_planning", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/business-planning/11111111-1111-4111-8111-111111111111/canvases/from-data",
    ): _expected("business_planning", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "PATCH",
        "/operator/api/business-planning/11111111-1111-4111-8111-111111111111/canvases/22222222-2222-4222-8222-222222222222/blocks/key_partners",
    ): _expected("business_planning", "update", scoped=True, location_id=_LOCATION_ID),
    (
        "PATCH",
        "/operator/api/business-planning/11111111-1111-4111-8111-111111111111/canvases/22222222-2222-4222-8222-222222222222/metadata",
    ): _expected("business_planning", "update", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/business-planning/11111111-1111-4111-8111-111111111111/canvases/22222222-2222-4222-8222-222222222222/versions",
    ): _expected("business_planning", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/coordination/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("coordination", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/extension-learning/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("extension_learning", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/extension-learning/11111111-1111-4111-8111-111111111111/modules",
    ): _expected("extension_learning", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/cooperatives/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("cooperative_management", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/trends/11111111-1111-4111-8111-111111111111/estimates",
    ): _expected("trend_analysis", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/trends/11111111-1111-4111-8111-111111111111/smoothing",
    ): _expected("trend_analysis", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/trends/11111111-1111-4111-8111-111111111111/change-points",
    ): _expected("trend_analysis", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/trends/11111111-1111-4111-8111-111111111111/decomposition",
    ): _expected("trend_analysis", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/trends/11111111-1111-4111-8111-111111111111/forecast",
    ): _expected("trend_analysis", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/trends/11111111-1111-4111-8111-111111111111/forecast",
    ): _expected("trend_analysis", "compute", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/geostatistics/11111111-1111-4111-8111-111111111111/autocorrelation",
    ): _expected("geostatistics", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/geostatistics/11111111-1111-4111-8111-111111111111/cross-validation",
    ): _expected("geostatistics", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/geostatistics/11111111-1111-4111-8111-111111111111/variogram-models",
    ): _expected("geostatistics", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/geostatistics/11111111-1111-4111-8111-111111111111/sensor-network-designs",
    ): _expected("geostatistics", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/geostatistics/11111111-1111-4111-8111-111111111111/kriging-summaries",
    ): _expected("geostatistics", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/geostatistics/11111111-1111-4111-8111-111111111111/kriging/55555555-5555-4555-8555-555555555555/points",
    ): _expected("geostatistics", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/geostatistics/11111111-1111-4111-8111-111111111111/realization-summaries",
    ): _expected("geostatistics", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/geostatistics/11111111-1111-4111-8111-111111111111/realizations/33333333-3333-4333-8333-333333333333/points",
    ): _expected("geostatistics", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/energy/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("energy_monitoring", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/waste/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("waste_management", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/landscape/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("landscape_conservation", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/pollinators/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("pollinator_health", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/traceability/11111111-1111-4111-8111-111111111111/batches",
    ): _expected("traceability", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/traceability/11111111-1111-4111-8111-111111111111/batches/33333333-3333-4333-8333-333333333333",
    ): _expected("traceability", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/yield-monitoring/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("yield_monitoring", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/irrigation/11111111-1111-4111-8111-111111111111/status",
    ): _expected("precision_irrigation", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/crop-simulations/11111111-1111-4111-8111-111111111111/runs",
    ): _expected("digital_twin", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/crop-simulations/11111111-1111-4111-8111-111111111111/runs/44444444-4444-4444-8444-444444444444",
    ): _expected("digital_twin", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/nutrients/11111111-1111-4111-8111-111111111111/balances",
    ): _expected("nutrient_budget", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/nutrients/11111111-1111-4111-8111-111111111111/soil-tests",
    ): _expected("nutrient_budget", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/nutrients/11111111-1111-4111-8111-111111111111/events/inputs",
    ): _expected("nutrient_budget", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/nutrients/11111111-1111-4111-8111-111111111111/events/removals",
    ): _expected("nutrient_budget", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/gates",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/solutions",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/solutions/dddddddd-dddd-4ddd-8ddd-dddddddddddd/gates",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/gates/dddddddd-dddd-4ddd-8ddd-ddddddddddde/evaluations",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/gates/dddddddd-dddd-4ddd-8ddd-ddddddddddde/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/gates/dddddddd-dddd-4ddd-8ddd-ddddddddddde/approve",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/gates/dddddddd-dddd-4ddd-8ddd-ddddddddddde/transition",
    ): _expected("solution_lifecycle", "transition", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/stage-transition-targets",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/solutions/dddddddd-dddd-4ddd-8ddd-dddddddddddd/stage-transition",
    ): _expected("solution_lifecycle", "transition", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/solutions/dddddddd-dddd-4ddd-8ddd-dddddddddddd/experiments",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/experiments/dddddddd-dddd-4ddd-8ddd-dddddddddddf/submit",
    ): _expected("solution_lifecycle", "submit", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/experiments/dddddddd-dddd-4ddd-8ddd-dddddddddddf/protocol-review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/experiments/dddddddd-dddd-4ddd-8ddd-dddddddddddf/protocol-review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/experiments/dddddddd-dddd-4ddd-8ddd-dddddddddddf/start",
    ): _expected("solution_lifecycle", "transition", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/experiments/dddddddd-dddd-4ddd-8ddd-dddddddddddf/observations",
    ): _expected("solution_lifecycle", "collect", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/experiments/dddddddd-dddd-4ddd-8ddd-dddddddddddf/analyze",
    ): _expected("solution_lifecycle", "analyze", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/experiments/dddddddd-dddd-4ddd-8ddd-dddddddddddf/complete",
    ): _expected("solution_lifecycle", "transition", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/experiments",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/experiments/dddddddd-dddd-4ddd-8ddd-dddddddddddf/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/experiments/dddddddd-dddd-4ddd-8ddd-dddddddddddf/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/funding",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/funding/targets",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/funding/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/funding/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeed/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/funding/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeed/approve",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/funding/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeed/tranches/ffffffff-ffff-4fff-8fff-ffffffffffff/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/funding/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeed/tranches/ffffffff-ffff-4fff-8fff-ffffffffffff/approve",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/solutions/dddddddd-dddd-4ddd-8ddd-dddddddddddd/funding",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/funding/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeed/submit",
    ): _expected("solution_lifecycle", "submit", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/programs",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/programs/redesigns",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/programs/drafts",
    ): _expected("solution_lifecycle", "submit", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/programs/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/submit",
    ): _expected("solution_lifecycle", "submit", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/programs/review-queue",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/programs/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/programs/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/revise",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/programs/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/consent-policy",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/programs/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/events",
    ): _expected("solution_lifecycle", "collect", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/configurations",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/configurations/drafts",
    ): _expected("solution_lifecycle", "submit", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/configurations/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/submit",
    ): _expected("solution_lifecycle", "submit", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/configurations/review-queue",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/configurations/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/readiness",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/readiness/review-queue",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/readiness/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/adoption/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/events",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/scale-gates",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/scale-gates/assessment-targets",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/scale-gates/dddddddd-dddd-4ddd-8ddd-ddddddddddde/evaluations",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/scale-gates/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/scale-gates/review/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/scale-gates/review/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/start",
    ): _expected("solution_lifecycle", "transition", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/completion-proposals",
    ): _expected("solution_lifecycle", "submit", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications/completion-review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/completion-proposals/ffffffff-ffff-4fff-8fff-ffffffffffff/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/completion-proposals/ffffffff-ffff-4fff-8fff-ffffffffffff/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/learning",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/replications/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee/learning",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/learning/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/learning/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeec/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/learning/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeec/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/learning/application",
    ): _expected("solution_lifecycle", "apply", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/learning/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeec/apply",
    ): _expected("solution_lifecycle", "apply", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/retirements",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/retirement-candidates",
    ): _expected("solution_lifecycle", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/retirements/review",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/retirements/review/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/retirements/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb/approve",
    ): _expected("solution_lifecycle", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/solution-lifecycle/11111111-1111-4111-8111-111111111111/solutions/dddddddd-dddd-4ddd-8ddd-dddddddddddd/retirements",
    ): _expected("solution_lifecycle", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/sequential-evidence/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("sequential_evidence", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/sequential-evidence/11111111-1111-4111-8111-111111111111/events",
    ): _expected("sequential_evidence", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("operating_pilot", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/demand-signals",
    ): _expected("operating_pilot", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/demand-signals",
    ): _expected("operating_pilot", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/learning-plans",
    ): _expected("operating_pilot", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/demand-signals/dddddddd-dddd-4ddd-8ddd-dddddddddddd/submit",
    ): _expected("operating_pilot", "submit_own", scoped=True, location_id=_LOCATION_ID),
    (
        "PUT",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/demand-signals/dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    ): _expected("operating_pilot", "edit_own", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/capacity-periods",
    ): _expected("operating_pilot", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/capacity-profiles",
    ): _expected("operating_pilot", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "PUT",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/capacity-profiles/dddddddd-dddd-4ddd-8ddd-dddddddddddc",
    ): _expected("operating_pilot", "edit_own", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/capacity-profiles/dddddddd-dddd-4ddd-8ddd-dddddddddddc/submit",
    ): _expected("operating_pilot", "submit_own", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/my-capacity-profiles",
    ): _expected("operating_pilot", "read_own", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/my-demand-signals",
    ): _expected("operating_pilot", "read_own", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/my-learning-plans",
    ): _expected("operating_pilot", "read_own", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/my-resource-requests",
    ): _expected("operating_pilot", "read_own", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/capacity-review-queue",
    ): _expected("operating_pilot", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/demand-review-queue",
    ): _expected("operating_pilot", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/resource-review-queue",
    ): _expected("operating_pilot", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/capacity-profiles/dddddddd-dddd-4ddd-8ddd-dddddddddddc/review",
    ): _expected("operating_pilot", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/demand-signals/dddddddd-dddd-4ddd-8ddd-dddddddddddd/review",
    ): _expected("operating_pilot", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/work-claims",
    ): _expected("operating_pilot", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/work-opportunities",
    ): _expected("operating_pilot", "claim_own", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/work-claim-review-queue",
    ): _expected("operating_pilot", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/work-claims/e5000000-0000-4000-8000-000000000001/review",
    ): _expected("operating_pilot", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/work-claim-allocation-queue",
    ): _expected("operating_pilot", "allocate", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/work-claims/e5000000-0000-4000-8000-000000000001/allocate",
    ): _expected("operating_pilot", "allocate", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/work-opportunities/e5000000-0000-4000-8000-000000000001/claims",
    ): _expected("operating_pilot", "claim_own", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/resource-categories",
    ): _expected("operating_pilot", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/resource-requests",
    ): _expected("operating_pilot", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "PUT",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/resource-requests/dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    ): _expected("operating_pilot", "edit_own", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/operating-pilot/11111111-1111-4111-8111-111111111111/resource-requests/dddddddd-dddd-4ddd-8ddd-dddddddddddd/submit",
    ): _expected("operating_pilot", "submit_own", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/stakeholder-identity/11111111-1111-4111-8111-111111111111/cases",
    ): _expected("stakeholder_identity", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/stakeholder-identity/11111111-1111-4111-8111-111111111111/cases",
    ): _expected("stakeholder_identity", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/stakeholder-identity/11111111-1111-4111-8111-111111111111/cases/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb/decision",
    ): _expected("stakeholder_identity", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/stakeholder-trust/11111111-1111-4111-8111-111111111111/parties/cccccccc-cccc-4ccc-8ccc-cccccccccccc/identity-evidence",
    ): _expected("stakeholder_trust", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/stakeholder-identity/11111111-1111-4111-8111-111111111111/resolve/dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    ): _expected("stakeholder_identity", "resolve", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/summary",
    ): _expected("governance_roles", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tensions",
    ): _expected("governance_tension", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tensions",
    ): _expected("governance_tension", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tensions/66666666-6666-4666-8666-666666666666",
    ): _expected("governance_tension", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles",
    ): _expected("governance_roles", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/circles",
    ): _expected("governance_roles", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles",
    ): _expected("governance_roles", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/circles/77777777-7777-4777-8777-777777777777",
    ): _expected(
        "governance_roles",
        "read",
        scoped=True,
        location_id=_LOCATION_ID,
        additional=(("governance_roles", "update"),),
    ),
    (
        "PATCH",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/circles/77777777-7777-4777-8777-777777777777",
    ): _expected("governance_roles", "update", scoped=True, location_id=_LOCATION_ID),
    (
        "PATCH",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles/77777777-7777-4777-8777-777777777777",
    ): _expected("governance_roles", "update", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles/77777777-7777-4777-8777-777777777777",
    ): _expected("governance_roles", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/circles/77777777-7777-4777-8777-777777777777/submit",
    ): _expected("governance_roles", "submit", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/circles/77777777-7777-4777-8777-777777777777/activate",
    ): _expected("governance_roles", "activate", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/circles/77777777-7777-4777-8777-777777777777/suspend",
    ): _expected("governance_roles", "suspend", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles/77777777-7777-4777-8777-777777777777/submit",
    ): _expected("governance_roles", "submit", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles/77777777-7777-4777-8777-777777777777/approve",
    ): _expected("governance_roles", "approve", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles/77777777-7777-4777-8777-777777777777/activate",
    ): _expected("governance_roles", "activate", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles/77777777-7777-4777-8777-777777777777/retire",
    ): _expected("governance_roles", "retire", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles/77777777-7777-4777-8777-777777777777/assignments",
    ): _expected("governance_roles", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/assignment-proposals",
    ): _expected("governance_roles", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/assignment-review-queue",
    ): _expected("governance_roles", "review", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles/77777777-7777-4777-8777-777777777777/assignments/88888888-8888-4888-8888-888888888888/approve",
    ): _expected("governance_roles", "approve", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/roles/77777777-7777-4777-8777-777777777777/assignments/88888888-8888-4888-8888-888888888888/reject",
    ): _expected("governance_roles", "reject", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tactical-items",
    ): _expected("governance_tactical", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tactical-items",
    ): _expected("governance_tactical", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "PATCH",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tactical-items/99999999-9999-4999-8999-999999999999",
    ): _expected("governance_tactical", "update", scoped=True, location_id=_LOCATION_ID),
    (
        "PATCH",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tactical-sessions/99999999-9999-4999-8999-999999999998",
    ): _expected("governance_tactical", "update", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tactical-sessions",
    ): _expected("governance_tactical", "read", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tactical-sessions",
    ): _expected("governance_tactical", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tactical-items/99999999-9999-4999-8999-999999999999/start",
    ): _expected("governance_tactical", "start", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tactical-items/99999999-9999-4999-8999-999999999999/dispose",
    ): _expected("governance_tactical", "dispose", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tactical-items/99999999-9999-4999-8999-999999999999/cancel",
    ): _expected("governance_tactical", "cancel", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/governance/11111111-1111-4111-8111-111111111111/tensions/66666666-6666-4666-8666-666666666666/submit",
    ): _expected("governance_tension", "submit", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/attestations/11111111-1111-4111-8111-111111111111",
    ): _expected("attestation", "read", scoped=True, location_id=_LOCATION_ID),
    ("GET", "/operator/api/report-review-queue"): _expected("report_snapshot_review", "read", scoped=True),
    (
        "GET",
        "/operator/api/report-review-queue/33333333-3333-4333-8333-333333333333",
    ): _expected("report_snapshot_review", "read", scoped=True),
    ("GET", "/operator/api/mobile-collection-review-queue"): _expected("mobile_collection_review", "read", scoped=True),
    (
        "GET",
        "/operator/api/mobile-collection-review-queue/44444444-4444-4444-8444-444444444444",
    ): _expected("mobile_collection_review", "read_detail", scoped=True),
    (
        "GET",
        "/operator/api/mobile-collection-review-queue/44444444-4444-4444-8444-444444444444/disposition-inventory",
    ): _expected(
        "mobile_collection_retention",
        "inventory",
        scoped=True,
        additional=(("mobile_collection_review", "read"),),
    ),
    (
        "POST",
        "/operator/api/mobile-collection-review-queue/44444444-4444-4444-8444-444444444444/events",
    ): _expected(
        "mobile_collection_review",
        "review",
        scoped=True,
        additional=(("mobile_collection_review", "read_detail"),),
    ),
    ("GET", "/operator/api/farm-activity-intake-queue"): _expected("farm_activity", "read", scoped=True),
    (
        "GET",
        "/operator/api/farm-activity-intake-queue/44444444-4444-4444-8444-444444444444",
    ): _expected(
        "farm_activity",
        "read_detail",
        scoped=True,
        additional=(("mobile_collection_review", "read_detail"),),
    ),
    (
        "POST",
        "/operator/api/farm-activity-intake-queue/44444444-4444-4444-8444-444444444444/draft",
    ): _expected(
        "farm_activity",
        "create_draft",
        scoped=True,
        additional=(
            ("farm_activity", "read_detail"),
            ("mobile_collection_review", "read_detail"),
        ),
    ),
    ("GET", "/operator/api/farm-activities"): _expected("farm_activity", "read", scoped=True),
    ("GET", "/operator/api/farm-activity-records"): _expected("farm_activity", "read", scoped=True),
    (
        "GET",
        "/operator/api/farm-activity-records/55555555-5555-4555-8555-555555555555",
    ): _expected("farm_activity", "read_detail", scoped=True),
    ("POST", "/operator/api/farm-activity-records"): _expected(
        "farm_activity",
        "create_draft",
        scoped=True,
        additional=(("farm_activity", "read_detail"),),
    ),
    (
        "PATCH",
        "/operator/api/farm-activity-records/55555555-5555-4555-8555-555555555555/draft",
    ): _expected(
        "farm_activity",
        "edit_draft",
        scoped=True,
        additional=(("farm_activity", "read_detail"),),
    ),
    ("GET", "/operator/api/farm-activity-records/published"): _expected(
        "farm_activity", "read_published", scoped=True
    ),
    (
        "GET",
        "/operator/api/farm-activity-records/published/55555555-5555-4555-8555-555555555555",
    ): _expected("farm_activity", "read_published_detail", scoped=True),
    (
        "GET",
        "/operator/api/farm-activities/55555555-5555-4555-8555-555555555555",
    ): _expected(
        "farm_activity",
        "read_detail",
        scoped=True,
    ),
    ("GET", "/operator/api/farm-activities/published"): _expected(
        "farm_activity", "read_published", scoped=True
    ),
    (
        "GET",
        "/operator/api/farm-activities/published/55555555-5555-4555-8555-555555555555",
    ): _expected("farm_activity", "read_published_detail", scoped=True),
    (
        "PATCH",
        "/operator/api/farm-activities/55555555-5555-4555-8555-555555555555/draft",
    ): _expected(
        "farm_activity",
        "edit_draft",
        scoped=True,
        additional=(
            ("farm_activity", "read_detail"),
            ("mobile_collection_review", "read_detail"),
        ),
    ),
    (
        "POST",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/participants",
    ): _expected("mobile_participant", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/participants/revoke",
    ): _expected("mobile_participant", "revoke", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/enrollments",
    ): _expected("mobile_device", "enroll", scoped=True, location_id=_LOCATION_ID),
    (
        "DELETE",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/enrollments/22222222-2222-4222-8222-222222222222",
    ): _expected("mobile_device", "revoke", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/devices/collector-1/revoke",
    ): _expected("mobile_device", "revoke", scoped=True, location_id=_LOCATION_ID),
    (
        "GET",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/inventory",
    ): _expected(
        "mobile_device",
        "read",
        scoped=True,
        location_id=_LOCATION_ID,
        additional=(("mobile_collection_review", "read"),),
    ),
}
for _action in ("submit", "reject", "activate", "suspend", "retire"):
    _EXPECTED_OPERATOR_POLICIES[(
        "POST",
        f"/operator/api/governance/{_LOCATION_ID}/circles/77777777-7777-4777-8777-777777777777/{_action}",
    )] = _expected("governance_roles", _action, scoped=True, location_id=_LOCATION_ID)
for _action in ("submit", "approve", "reject", "activate", "suspend", "retire"):
    _EXPECTED_OPERATOR_POLICIES[(
        "POST",
        f"/operator/api/governance/{_LOCATION_ID}/roles/77777777-7777-4777-8777-777777777777/{_action}",
    )] = _expected("governance_roles", _action, scoped=True, location_id=_LOCATION_ID)
for _route_action, _policy_action in _TRANSITION_ACTIONS.items():
    _EXPECTED_OPERATOR_POLICIES[
        (
            "POST",
            f"/operator/api/farm-activities/55555555-5555-4555-8555-555555555555/{_route_action}",
        )
    ] = _expected("farm_activity", _policy_action, scoped=True)
    _EXPECTED_OPERATOR_POLICIES[
        (
            "POST",
            f"/operator/api/farm-activity-records/55555555-5555-4555-8555-555555555555/{_route_action}",
        )
    ] = _expected("farm_activity", _policy_action, scoped=True)

for _retirement_route_action, _retirement_policy_action in {
    "migration": "transition",
    "sunset": "transition",
    "post-retirement-review": "review",
}.items():
    _EXPECTED_OPERATOR_POLICIES[(
        "POST",
        f"/operator/api/solution-lifecycle/{_LOCATION_ID}/retirements/"
        f"{_PARAMETER_SAMPLES['retirement_id']}/{_retirement_route_action}",
    )] = _expected(
        "solution_lifecycle",
        _retirement_policy_action,
        scoped=True,
        location_id=_LOCATION_ID,
    )

_EXPECTED_OPERATOR_POLICIES[(
    "POST",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/resource-requests/"
    f"{_PARAMETER_SAMPLES['resource_request_id']}/review",
)] = _expected("operating_pilot", "review", scoped=True, location_id=_LOCATION_ID)
_EXPECTED_OPERATOR_POLICIES[(
    "GET",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/resource-fulfillment-queue",
)] = _expected("operating_pilot", "fulfill", scoped=True, location_id=_LOCATION_ID)
_EXPECTED_OPERATOR_POLICIES[(
    "POST",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/resource-requests/"
    f"{_PARAMETER_SAMPLES['resource_request_id']}/fulfill",
)] = _expected("operating_pilot", "fulfill", scoped=True, location_id=_LOCATION_ID)
_EXPECTED_OPERATOR_POLICIES[(
    "POST",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/competency-assessments",
)] = _expected("operating_pilot", "create", scoped=True, location_id=_LOCATION_ID)
_EXPECTED_OPERATOR_POLICIES[(
    "POST",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/learning-plans",
)] = _expected("operating_pilot", "create", scoped=True, location_id=_LOCATION_ID)
_EXPECTED_OPERATOR_POLICIES[(
    "PUT",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/competency-assessments/"
    f"{_PARAMETER_SAMPLES['draft_id']}",
)] = _expected("operating_pilot", "edit_own", scoped=True, location_id=_LOCATION_ID)
_EXPECTED_OPERATOR_POLICIES[(
    "POST",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/competency-assessments/"
    f"{_PARAMETER_SAMPLES['draft_id']}/submit",
)] = _expected("operating_pilot", "submit_own", scoped=True, location_id=_LOCATION_ID)
_EXPECTED_OPERATOR_POLICIES[(
    "GET",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/my-competency-assessments",
)] = _expected("operating_pilot", "read_own", scoped=True, location_id=_LOCATION_ID)
_EXPECTED_OPERATOR_POLICIES[(
    "GET",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/my-learning-plans",
)] = _expected("operating_pilot", "read_own", scoped=True, location_id=_LOCATION_ID)
_EXPECTED_OPERATOR_POLICIES[(
    "GET",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/competency-review-queue",
)] = _expected("operating_pilot", "review", scoped=True, location_id=_LOCATION_ID)
_EXPECTED_OPERATOR_POLICIES[(
    "POST",
    f"/operator/api/operating-pilot/{_LOCATION_ID}/competency-assessments/"
    f"{_PARAMETER_SAMPLES['draft_id']}/review",
)] = _expected("operating_pilot", "review", scoped=True, location_id=_LOCATION_ID)


def _concrete_paths(route_path):
    path = reduce(
        lambda current, item: current.replace("{" + item[0] + "}", item[1]),
        _PARAMETER_SAMPLES.items(),
        route_path,
    )
    if "{action}" in path:
        return [path.replace("{action}", action) for action in _TRANSITION_ACTIONS]
    if "{event_type}" in path:
        return [path.replace("{event_type}", event_type) for event_type in ("inputs", "removals")]
    return [path]


def test_registered_operator_routes_have_exact_reviewed_policy_coverage():
    provider = SimpleNamespace(settings=SimpleNamespace(state_secret="test-state-secret-with-at-least-32-bytes"))
    router = create_auth_router(provider)
    actual = {}

    for route in router.routes:
        for method in route.methods or ():
            for path in _concrete_paths(route.path):
                policy = auth_route_policy(method, path, enabled=True)
                assert policy is not None, (method, route.path, path)
                assert policy["operator_auth"] is True
                additional = tuple(
                    sorted((scope["resource"], scope["action"]) for scope in policy.get("additional_scopes", ()))
                )
                actual[(method, path)] = (
                    policy["resource"],
                    policy["action"],
                    policy["public"],
                    policy["scope_required"],
                    policy["location_id"],
                    additional,
                )

    assert actual == _EXPECTED_OPERATOR_POLICIES


def test_unknown_operator_path_and_method_are_protected(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_PATH", str(tmp_path / "gateway-audit.sqlite3"))
    monkeypatch.setenv("KOKONUT_API_KEYS", "")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "")
    monkeypatch.setenv("KOKONUT_OPERATOR_OIDC_ENABLED", "false")

    with TestClient(create_app()) as client:
        unknown = client.get("/operator/api/not-registered")
        wrong_method = client.post("/operator/")

    assert unknown.status_code == 401
    assert wrong_method.status_code == 401


def test_business_canvas_from_data_policy_is_post_create_only():
    path = f"/operator/api/business-planning/{_LOCATION_ID}/canvases/from-data"

    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "business_planning",
        "action": "create",
        "public": False,
        "location_id": _LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("PATCH", path, enabled=True) is None
