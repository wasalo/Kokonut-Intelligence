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
