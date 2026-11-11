"""Regressions for conservative API SQL-site attribution."""

import ast
from pathlib import Path

import scripts.worker_source_closure as worker_source_closure
from scripts import runtime_role_attribution


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_only_verified_starlette_injection_marks_route_threadpool_parameter():
    auth_tree = ast.parse(
        """
def create_auth_router():
    from starlette.concurrency import run_in_threadpool as dispatch
    from services.gateway.sample_routes import register_routes as register
    register(router, provider, dispatch)
"""
    )
    route_tree = ast.parse(
        """
def register_routes(router, provider, run_in_threadpool):
    pass
"""
    )

    verified = runtime_role_attribution._verified_route_threadpool_parameters_from_router(
        "services.gateway.operator_auth",
        Path("services/gateway/operator_auth.py"),
        _function(auth_tree, "create_auth_router"),
        {"services.gateway.sample_routes": route_tree},
    )

    assert verified == {
        ("services.gateway.operator_auth", "create_auth_router"): "dispatch",
        ("services.gateway.sample_routes", "register_routes"): "run_in_threadpool"
    }

    untrusted_auth_tree = ast.parse(
        """
def create_auth_router():
    from starlette.concurrency import run_in_threadpool
    from services.gateway.sample_routes import register_routes
    register_routes(router, provider, custom_executor)
"""
    )
    unverified = runtime_role_attribution._verified_route_threadpool_parameters_from_router(
        "services.gateway.operator_auth",
        Path("services/gateway/operator_auth.py"),
        _function(untrusted_auth_tree, "create_auth_router"),
        {"services.gateway.sample_routes": route_tree},
    )
    assert unverified == {
        ("services.gateway.operator_auth", "create_auth_router"): "run_in_threadpool"
    }
    assert ("services.gateway.sample_routes", "register_routes") not in unverified


def test_gateway_threadpool_callbacks_reach_known_sql_service_helpers():
    api = worker_source_closure._operation(
        "api_gateway", "services.gateway.app", ["services.gateway.app"]
    )
    roots, _ = runtime_role_attribution._gateway_route_roots(api["source_files"])
    callback_roots, callback_edges = runtime_role_attribution._api_threadpool_callback_roots(
        api["source_files"], roots
    )

    assert len(callback_roots) >= 200
    assert all(
        edge["dispatch"] == "verified_starlette_run_in_threadpool_callback"
        for edge in callback_edges
    )
    assert any(
        edge["caller"].startswith(
            "services.gateway.solution_lifecycle_routes:register_solution_lifecycle_routes."
        )
        and edge["callee"].startswith("services.gateway.solution_lifecycle_actions:")
        for edge in callback_edges
    )
    assert any(
        edge["caller"].startswith(
            "services.gateway.operating_pilot_routes:register_operating_pilot_routes."
        )
        and edge["callee"].startswith("services.gateway.operating_pilot_writes:")
        for edge in callback_edges
    )
    expected_helper_callbacks = {
        (
            "services.gateway.business_planning_routes:"
            "register_business_planning_routes._create_canvas_response",
            "services.gateway.business_planning_writes:create_location_business_model_canvas",
        ),
        (
            "services.gateway.business_planning_routes:"
            "register_business_planning_routes._create_canvas_response",
            "services.gateway.business_planning_writes:create_location_business_model_canvas_from_data",
        ),
        (
            "services.gateway.farm_activity_routes:"
            "register_farm_activity_record_routes._invoke",
            "services.gateway.farm_activity_records:create_farm_activity_record",
        ),
        (
            "services.gateway.farm_activity_routes:"
            "register_farm_activity_record_routes._invoke",
            "services.gateway.farm_activity_records:edit_farm_activity_record_draft",
        ),
        (
            "services.gateway.farm_activity_routes:"
            "register_farm_activity_record_routes._invoke",
            "services.gateway.farm_activity_records:get_farm_activity_record",
        ),
        (
            "services.gateway.farm_activity_routes:"
            "register_farm_activity_record_routes._invoke",
            "services.gateway.farm_activity_records:list_farm_activity_records",
        ),
        (
            "services.gateway.farm_activity_routes:"
            "register_farm_activity_record_routes._invoke",
            "services.gateway.farm_activity_records:list_farm_activity_relation_choices",
        ),
        (
            "services.gateway.farm_activity_routes:"
            "register_farm_activity_record_routes._invoke",
            "services.gateway.farm_activity_records:transition_farm_activity_record",
        ),
    }
    observed_helper_callbacks = {
        (edge["caller"], edge["callee"])
        for edge in callback_edges
        if edge["caller"].endswith("._create_canvas_response")
        or edge["caller"].endswith("._invoke")
    }
    assert observed_helper_callbacks == expected_helper_callbacks

    expanded = runtime_role_attribution.worker_function_reachability._operation_graph(
        {
            **api,
            "kind": "api_gateway_routes",
            "name": "services.gateway.app",
            "root_modules": ["services.gateway.app"],
        },
        entry_functions=[*roots, *callback_roots],
    )
    reachable = {
        (function["source"], function["qualname"])
        for function in expanded["reachable_functions"]
    }
    assert (
        "services/gateway/solution_lifecycle_actions.py",
        "create_location_solution",
    ) in reachable
    assert (
        "services/gateway/operating_pilot_writes.py",
        "create_location_operating_pilot_capacity_draft",
    ) in reachable
    assert (
        "services/gateway/business_planning_writes.py",
        "create_location_business_model_canvas_from_data",
    ) in reachable
    assert (
        "services/analytics/business_model_canvas.py",
        "suggest",
    ) in reachable
    assert (
        "services/analytics/business_model_canvas.py",
        "_suggestion_rows",
    ) in reachable


def test_local_endpoint_factories_resolve_only_with_literal_string_arguments():
    literal_tree = ast.parse(
        """
def create_routes():
    def endpoint_factory(entity_type):
        async def endpoint(request):
            return entity_type
        return endpoint
    for entity_type in ("circle", "role"):
        router.add_api_route("/", endpoint_factory(entity_type))
"""
    )
    collector = runtime_role_attribution._RouteRootCollector(
        "services.gateway.sample_routes", "services/gateway/sample_routes.py"
    )
    collector.visit(literal_tree)
    roots, unresolved = collector.roots()

    assert [root["function"] for root in roots] == [
        "services.gateway.sample_routes:create_routes.endpoint_factory.endpoint"
    ]
    assert unresolved == []

    dynamic_tree = ast.parse(
        """
def create_routes(entity_type):
    def endpoint_factory(value):
        async def endpoint(request):
            return value
        return endpoint
    router.add_api_route("/", endpoint_factory(entity_type))
"""
    )
    dynamic_collector = runtime_role_attribution._RouteRootCollector(
        "services.gateway.dynamic_routes", "services/gateway/dynamic_routes.py"
    )
    dynamic_collector.visit(dynamic_tree)
    dynamic_roots, dynamic_unresolved = dynamic_collector.roots()

    assert dynamic_roots == []
    assert [item["status"] for item in dynamic_unresolved] == ["dynamic_endpoint_factory"]


def test_standard_role_contract_records_route_specific_operator_database_identities():
    contract = runtime_role_attribution._standard_role_contract()

    assert contract["standard_api"]["database_login"].startswith("kokonut_runtime")
    assert contract["standard_general_worker"]["database_login"].startswith(
        "kokonut_runtime by default"
    )
    profiles = {
        profile["selection"]: profile
        for profile in contract["api_worker_login_profiles"]
    }
    split_profile = profiles["Standard --separate-api-worker-logins --scheduler-role"]
    assert split_profile["api_database_login"] == "kokonut_runtime"
    assert split_profile["general_worker_database_login"] == "kokonut_worker_runtime"
    assert split_profile["scheduler_database_login"] == "kokonut_scheduler_login"
    assert "not close C1" in contract["role_bootstrap"]["api_worker_identity_split"]
    assert contract["api_route_specific_database_identities"] == [
        {
            "database_login": "kokonut_operator_auth",
            "source": "services.gateway.operator_auth._get_operator_auth_db",
            "credential_environment_variables": [
                "KOKONUT_OPERATOR_AUTH_USER",
                "KOKONUT_OPERATOR_AUTH_PASSWORD",
            ],
            "purpose": "OIDC session operations and global capability checks through bounded functions; location-scope reads still use the shared runtime connection",
            "child_environment": "explicit operator_auth allowlist on the API child only",
            "direct_table_access": False,
        },
        {
            "database_login": "kokonut_clickhouse_outbox_operator_login",
            "source": "services.gateway.clickhouse_outbox_operator._operator_action_connection",
            "credential_environment_variable": "KOKONUT_CLICKHOUSE_OUTBOX_OPERATOR_PASSWORD",
            "route_prefix": "/operator/api/clickhouse-outbox/dead-letters",
            "purpose": "global-capability-gated dead-letter reads and transitions through bounded functions",
            "child_environment": "explicit clickhouse_outbox_operator allowlist on the API child only",
            "direct_table_access": False,
            "activation": "credential is optional and absent by default; runtime-role bootstrap enables the login only when configured",
        },
    ]


def test_governance_role_route_factories_are_resolved_as_local_api_roots():
    source = "services/gateway/governance_role_routes.py"
    module = worker_source_closure._module_for_path(runtime_role_attribution.ROOT / source)
    tree = ast.parse((runtime_role_attribution.ROOT / source).read_text(encoding="utf-8"))
    collector = runtime_role_attribution._RouteRootCollector(module, source)
    collector.visit(tree)
    roots, unresolved = collector.roots()

    root_names = {root["function"].partition(":")[2] for root in roots}
    expected_suffixes = {
        "create_definition_endpoint.endpoint",
        "update_definition_endpoint.endpoint",
        "circle_action_endpoint.endpoint",
        "role_action_endpoint.endpoint",
    }
    resolved_suffixes = {
        suffix
        for name in root_names
        for suffix in expected_suffixes
        if name.endswith(suffix)
    }
    assert resolved_suffixes == expected_suffixes
    assert not any(item["status"] == "dynamic_endpoint_factory" for item in unresolved)
