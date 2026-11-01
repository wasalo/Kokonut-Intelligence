#!/usr/bin/env python3
"""Build a conservative API/general-worker SQL-site attribution review map.

This source report joins the all-service SQL inventory to the Gateway's
source-registered route handlers and the existing supervisor-worker call
graphs. It is a capability-map starting point, not a proof of runtime reach,
database effects, ACLs, tenant isolation, or schedule activation.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.runtime_sql_inventory as runtime_sql_inventory  # noqa: E402
import scripts.worker_function_reachability as worker_function_reachability  # noqa: E402
import scripts.worker_source_closure as worker_source_closure  # noqa: E402
import scripts.worker_sql_reachability as worker_sql_reachability  # noqa: E402
from services.common.worker_environment import (  # noqa: E402
    _EVENT_HANDLER_ISOLATION_FEATURES,
    EVENT_HANDLER_WORKERS,
    event_dispatch_worker_keys,
    scheduled_module_worker_key,
)

_HTTP_ROUTE_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "trace", "api_route", "websocket"}
)


class _RouteRootCollector(ast.NodeVisitor):
    """Find literal route-handler roots without importing the Gateway app."""

    def __init__(self, module: str, source: str):
        self.module = module
        self.source = source
        self.scope: list[str] = []
        self.functions: set[str] = set()
        self.decorated_roots: set[tuple[str, int]] = set()
        self.registrations: list[tuple[str, int, ast.AST | None, tuple[str, ...]]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qualname = ".".join([*self.scope, node.name])
        self.functions.add(qualname)
        if any(self._is_route_decorator(decorator) for decorator in node.decorator_list):
            self.decorated_roots.add((qualname, node.lineno))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    @staticmethod
    def _is_route_decorator(node: ast.AST) -> bool:
        target = node.func if isinstance(node, ast.Call) else node
        return (
            isinstance(target, ast.Attribute)
            and target.attr.lower() in _HTTP_ROUTE_METHODS
        )

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr == "add_api_route":
            endpoint = node.args[1] if len(node.args) > 1 else next(
                (keyword.value for keyword in node.keywords if keyword.arg == "endpoint"),
                None,
            )
            self.registrations.append((self.source, node.lineno, endpoint, tuple(self.scope)))
        self.generic_visit(node)

    def roots(self) -> tuple[list[dict], list[dict]]:
        roots: dict[str, dict] = {}
        for qualname, line in self.decorated_roots:
            key = f"{self.module}:{qualname}"
            roots[key] = {"function": key, "source": self.source, "line": line}

        unresolved = []
        for source, line, endpoint, scope in self.registrations:
            qualname = None
            if isinstance(endpoint, ast.Name):
                for depth in range(len(scope), -1, -1):
                    candidate = ".".join([*scope[:depth], endpoint.id])
                    if candidate in self.functions:
                        qualname = candidate
                        break
            elif isinstance(endpoint, ast.Attribute) and isinstance(endpoint.value, ast.Name):
                # ``self.handler`` or a module-local router object is not
                # enough to resolve the endpoint target safely.
                unresolved.append(
                    {"source": source, "line": line, "status": "dynamic_endpoint_reference"}
                )
            elif isinstance(endpoint, ast.Call):
                unresolved.append(
                    {"source": source, "line": line, "status": "dynamic_endpoint_factory"}
                )
            else:
                unresolved.append(
                    {"source": source, "line": line, "status": "dynamic_endpoint_reference"}
                )
            if qualname:
                key = f"{self.module}:{qualname}"
                roots[key] = {"function": key, "source": source, "line": line}
            elif not isinstance(endpoint, (ast.Attribute, ast.Call)):
                unresolved.append(
                    {"source": source, "line": line, "status": "unresolved_endpoint_reference"}
                )
        return [roots[key] for key in sorted(roots)], sorted(
            {(item["source"], item["line"], item["status"]): item for item in unresolved}.values(),
            key=lambda item: (item["source"], item["line"], item["status"]),
        )


def _gateway_route_roots(source_files: list[str]) -> tuple[list[dict], list[dict]]:
    collectors = []
    for source in source_files:
        if not source.startswith(("services/gateway/", "services/mobile/")):
            continue
        path = ROOT / source
        module = worker_source_closure._module_for_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=source)
        collector = _RouteRootCollector(module, source)
        collector.visit(tree)
        collectors.append(collector)

    roots: dict[str, dict] = {}
    unresolved = []
    for collector in collectors:
        found_roots, found_unresolved = collector.roots()
        roots.update({root["function"]: root for root in found_roots})
        unresolved.extend(found_unresolved)
    return (
        [roots[key] for key in sorted(roots)],
        sorted(unresolved, key=lambda item: (item["source"], item["line"], item["status"])),
    )


def _standard_role_contract() -> dict:
    standard_path = ROOT / "docker-compose.kernel-standard.yml"
    role_path = ROOT / "docker-compose.kernel-runtime-role.yml"
    features_path = ROOT / "services/core/features.py"
    readiness_path = ROOT / "services/core/schema_readiness.py"
    worker_environment_path = ROOT / "services/common/worker_environment.py"
    features_source = features_path.read_text(encoding="utf-8")
    standard_compose = (ROOT / "docker-compose.kernel-standard.yml").read_text(encoding="utf-8")

    compose_lines = {line.split(":", 1)[0].strip(): line for line in standard_compose.splitlines()}
    feature_tree = ast.parse(features_source, filename="services/core/features.py")
    isolation_flags = {}
    for node in ast.walk(feature_tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "getenv" or not node.args:
            continue
        name = node.args[0]
        if not isinstance(name, ast.Constant) or not isinstance(name.value, str):
            continue
        if not name.value.startswith(("KOKONUT_FEATURE_ISOLATED_", "KOKONUT_FEATURE_SIGNED_")):
            continue
        code_default = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else None
        compose_line = compose_lines.get(name.value)
        compose_default = None
        if compose_line:
            default_start = compose_line.find(": ${")
            default_end = compose_line.find("}", default_start + 4) if default_start >= 0 else -1
            if default_end >= 0:
                compose_default = compose_line[default_start + 4:default_end].split(":-", 1)[-1]
        isolation_flags[name.value] = {
            "code_default": code_default,
            "standard_compose_default": compose_default,
            "explicitly_passed_by_standard_compose": compose_line is not None,
        }
    worker_secret_names = sorted({
        line.split(":", 1)[0].strip()
        for line in standard_compose.splitlines()
        if line.startswith("      KOKONUT_") and any(
            suffix in line.split(":", 1)[0]
            for suffix in ("_DATABASE_URL", "_WORKER_CREDENTIAL", "_RPC_ENDPOINT", "_RPC_ENDPOINTS", "_API_KEY", "_SERVICE_ACCOUNT_KEY", "_PASSWORD", "_EMAIL", "_CLIENT_ID", "_CLIENT_SECRET")
        )
    })
    return {
        "standard_api": {
            "process": "services.core.runtime API child -> services.gateway.cli --serve -> services.gateway.app:create_app",
            "started_by_default": True,
            "database_login": "kokonut_runtime via PG_USER/PG_PASSWORD from docker-compose.kernel-runtime-role.yml",
            "startup_check": "generic non-owner/non-privileged current_user==session_user; no API-role identity assertion",
            "credential_scope": "shared runtime login; worker-specific KOKONUT_* secrets are removed from the API child environment",
            "notification_provider_environment": "ALERT_WEBHOOK_URL is cleared after deriving a non-secret configured flag; ALERT_SMTP_USER/PASSWORD are explicitly blanked; non-secret SMTP routing fields may remain",
        },
        "standard_general_worker": {
            "process": "services.core.runtime --workers-only supervisor",
            "database_login": "kokonut_runtime via PG_USER/PG_PASSWORD from docker-compose.kernel-standard.yml and docker-compose.kernel-runtime-role.yml",
            "startup_check": "same generic non-owner/non-privileged check as API; no worker-role identity assertion",
            "container_secret_environment_variable_names": worker_secret_names,
            "container_secret_environment_variable_count": len(worker_secret_names),
            "child_filter": "worker_subprocess_environment filters named KOKONUT_<WORKER> secrets per exact operation allowlists; isolated children additionally remove shared PG_* and global provider secrets",
            "notification_provider_environment": "worker receives ALERT_WEBHOOK_URL and ALERT_SMTP_USER/PASSWORD; these non-KOKONUT variables survive child filtering so the delivery child can use them",
        },
        "default_on_children": [
            {
                "name": "scheduler",
                "enabled_by": "KOKONUT_FEATURE_SCHEDULER defaults true in services/core/features.py; Standard Compose does not override it",
                "shared_login_by_default": True,
                "activation_limit": "source-allowlisted modules do not prove a persisted task is active; live schedule state is unassessed",
            },
            {
                "name": "event_bus_dispatch",
                "capability_enabled_by": "KOKONUT_FEATURE_EVENT_BUS defaults true in Standard Compose",
                "worker_enabled_by": "KOKONUT_FEATURE_ISOLATED_EVENT_DISPATCH defaults false; dispatcher uses its migration-648 dedicated login when enabled",
                "shared_login_by_default": False,
                "database_activity_when_isolation_is_off": "paused by services.events.cli without opening the shared database",
                "activation_limit": "handler allowlist does not prove registered event traffic or runtime event state",
            },
            {
                "name": "notification_delivery",
                "capability_enabled_by": "KOKONUT_FEATURE_NOTIFICATION_DELIVERY defaults to KOKONUT_FEATURE_EVENT_BUS (true) in Standard Compose",
                "worker_enabled_by": "KOKONUT_FEATURE_ISOLATED_NOTIFICATION_DELIVERY defaults false; delivery uses its migration-647 dedicated login when enabled",
                "shared_pg_credentials_in_child_environment": False,
                "database_activity_when_isolation_is_off": "paused by services.events.cli without opening the shared database",
                "activation_limit": "a configured provider and isolated database identity are required; a supervised child does not prove successful delivery",
            },
        ],
        "isolated_mode_defaults": {
            "feature_variables": {name: isolation_flags[name] for name in sorted(isolation_flags)},
            "meaning": "Dedicated worker logins/functions are opt-in per operation; source availability is not evidence that an isolated path is active.",
        },
        "role_bootstrap": {
            "source": "docker-compose.kernel-runtime-role.yml runtime-role-bootstrap",
            "purpose": "provisions shared kokonut_runtime and dedicated operation logins",
            "initial_runtime_compatibility_grant": "existing public table/sequence DML compatibility grants are not removed by later reprovisioning; exact relation ACLs require separate cohort review",
            "api_worker_identity_split": "not implemented",
        },
        "source_inputs": [
            "docker-compose.kernel-standard.yml",
            "docker-compose.kernel-runtime-role.yml",
            "services/core/features.py",
            "services/core/schema_readiness.py",
            "services/common/worker_environment.py",
        ],
        "source_digests_sha256": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (standard_path, role_path, features_path, readiness_path, worker_environment_path)
        },
    }


def _worker_operation_credential_path(operation: dict, isolation_flags: dict) -> dict:
    kind = operation["kind"]
    name = operation["name"]
    if kind == "scheduled_module":
        key = scheduled_module_worker_key(name)
        if name == "services.events":
            return {
                "mode": "command_argument_selected_isolated_identity",
                "named_secret_keys": {
                    "event_dispatch": list(event_dispatch_worker_keys()),
                    "notification_delivery": ["notification_delivery"],
                },
                "detail": "validated --process selects event_dispatch plus only enabled handler identities; --notification-process selects notification_delivery; no event operation uses the shared database, and persisted command arguments are unassessed",
            }
        return {
            "mode": "isolated_named_worker_by_exact_module" if key else "shared_runtime_pg_by_default",
            "named_secret_key": key,
            "detail": "scheduler subprocess receives a named worker secret only for an exact mapped module; that allowlist is not proof of a dedicated login or an active persisted schedule",
        }
    if kind == "event_handler":
        module, _, function = name.rpartition(".")
        key = (module, function)
        worker_keys = list(EVENT_HANDLER_WORKERS.get(key, ()))
        feature = _EVENT_HANDLER_ISOLATION_FEATURES.get(key)
        if feature is None and worker_keys:
            return {
                "mode": "per_handler_isolated_database_credentials",
                "named_secret_keys": worker_keys,
                "detail": "handler child removes shared PG_* credentials and requires its dedicated worker connection",
            }
        if feature:
            flag = isolation_flags.get(feature, {})
            return {
                "mode": "feature_gated_isolation_without_shared_fallback",
                "named_secret_keys": worker_keys,
                "feature_variable": feature,
                "code_default": flag.get("code_default"),
                "detail": "handler children always lose shared PostgreSQL credentials; the feature flag controls whether its mapped worker secret is passed, so disabled handlers can use only non-database behavior or fail closed",
            }
        return {
            "mode": "isolated_dispatch_without_handler_database_identity",
            "named_secret_keys": worker_keys,
            "detail": "the shared EventStore no longer exposes event processing; unmapped event handlers run without shared PostgreSQL credentials and need an explicit source-owned worker mapping before database access",
        }
    if kind == "signed_source_function":
        return {
            "mode": "signed_worker_source_function",
            "detail": "function establishes its signed source scope; caller selection, feature flag, and live invocation remain unassessed",
        }
    return {
        "mode": "isolated_worker_entrypoint",
        "detail": "source registers a dedicated worker entrypoint; live invocation and environment selection remain unassessed",
    }


def build_inventory() -> dict:
    sql_inventory = runtime_sql_inventory.build_inventory()
    worker_functions = worker_function_reachability.build_inventory()
    worker_sql = worker_sql_reachability.build_inventory(
        function_graph=worker_functions,
        sql_inventory=sql_inventory,
    )

    api_closure = worker_source_closure._operation(
        "api_gateway", "services.gateway.app", ["services.gateway.app"]
    )
    api_roots, unresolved_registrations = _gateway_route_roots(
        api_closure["source_files"]
    )
    dynamic_import_count = len(api_closure["dynamic_import_sites"])
    api_operation = {
        **api_closure,
        "kind": "api_gateway_routes",
        "name": "services.gateway.app",
        "root_modules": ["services.gateway.app"],
    }
    api_graph = worker_function_reachability._operation_graph(
        api_operation,
        entry_functions=api_roots,
    )
    api_functions = {
        (function["source"], function["qualname"])
        for function in api_graph["reachable_functions"]
    }
    api_function_sources = {
        f"{function['module']}:{function['qualname']}": function["source"]
        for function in api_graph["reachable_functions"]
    }
    api_dynamic_targets = {
        (api_function_sources[edge["callee"]], edge["callee"].partition(":")[2])
        for edge in api_graph["dynamic_dispatch_edges"]
        if edge["callee"] in api_function_sources
    }

    worker_sites = {site["id"]: site for site in worker_sql["execution_sites"]}
    worker_function_operations = {
        f"{operation['kind']}:{operation['name']}": operation
        for operation in worker_functions["operations"]
    }
    gateway_files = set(api_closure["source_files"])
    records = []
    attribution_counts = Counter()
    for site in sql_inventory["execution_sites"]:
        site_id = site["id"]
        source_scope = (site["source"], site["scope"])
        api_reached = source_scope in api_functions
        worker_site = worker_sites.get(site_id)
        worker_refs = worker_site["statically_reachable_operations"] if worker_site else []
        if api_reached and worker_refs:
            attribution = "shared_candidate"
        elif api_reached:
            attribution = "api_candidate"
        elif worker_refs:
            attribution = "worker_candidate"
        else:
            attribution = "unresolved"
        attribution_counts[attribution] += 1

        labels = []
        if api_reached:
            labels.append("gateway_route_static_call_path")
            if source_scope in api_dynamic_targets:
                labels.append("gateway_path_includes_registered_dynamic_dispatch")
        else:
            labels.append("no_static_gateway_route_path_dynamic_or_non_api_possible")
        if worker_refs:
            labels.append("supervisor_worker_static_operation_path")
        elif worker_site and worker_site["function_in_any_worker_graph"]:
            labels.append("worker_function_in_graph_without_operation_edge")
        elif worker_site:
            labels.append("worker_sql_site_not_statically_reached_dynamic_or_unresolved_possible")
        else:
            labels.append("not_in_static_worker_sql_inventory")
        if source_scope[0] in gateway_files and not api_reached:
            labels.append("gateway_import_closure_but_route_reachability_unresolved")

        records.append({
            "id": site_id,
            "source": site["source"],
            "line": site["line"],
            "scope": site["scope"],
            "method": site["method"],
            "expression_kind": site["expression_kind"],
            "statement_kind": site["statement_kind"],
            "static_sql_sha256": site["static_sql_sha256"],
            "candidate_relations": site["candidate_relations"],
            "write_target_relations": site["write_target_relations"],
            "api_static_reachability": "linked" if api_reached else "no_static_route_path",
            "worker_static_operations": worker_refs,
            "worker_static_review_status": (
                worker_site["review_status"] if worker_site
                else "not_in_worker_sql_inventory_source_snapshot_mismatch_or_non_worker"
            ),
            "attribution": attribution,
            "review_labels": labels,
        })

    summary = {
        "sql_execution_sites": len(records),
        "attribution_counts": {name: attribution_counts[name] for name in (
            "api_candidate", "worker_candidate", "shared_candidate", "unresolved"
        )},
        "api_route_root_count": len(api_roots),
        "api_static_function_count": len(api_functions),
        "api_static_sql_site_count": sum(record["api_static_reachability"] == "linked" for record in records),
        "api_dynamic_dispatch_edge_count": len(api_graph["dynamic_dispatch_edges"]),
        "api_unresolved_route_registration_count": len(unresolved_registrations),
        "api_dynamic_import_site_count": dynamic_import_count,
        "worker_operation_root_count": worker_sql["summary"]["operation_roots"],
        "worker_dynamic_dispatch_edge_count": worker_functions["summary"]["dynamic_dispatch_edges"],
        "worker_static_sql_site_count": worker_sql["summary"]["unique_sites_with_static_operation_path"],
        "worker_sites_without_static_function_match": worker_sql["summary"]["sites_without_static_function_match"],
        "sites_in_both_api_and_worker_graphs": attribution_counts["shared_candidate"],
        "unresolved_site_count": attribution_counts["unresolved"],
    }
    role_contract = _standard_role_contract()
    isolation_flags = role_contract["isolated_mode_defaults"]["feature_variables"]

    return {
        "version": 1,
        "generated_by": "scripts/runtime_role_attribution.py",
        "scope": (
            "Conservative static attribution of direct Python SQL execution sites to source-registered Gateway route handlers and the existing supervisor worker operation graphs. "
            "Gateway route roots are collected from the Gateway app's local import closure; this does not prove every dynamically registered route is mounted. Worker roots are allowlisted modules/handlers, not proof of a live schedule or event. "
            "A site without a static path may be dynamic, callback-driven, imported, CLI-driven, or otherwise unresolved; it is not evidence that a site is dead. Relation names remain heuristic candidates. "
            "This report contains no SQL text, parameter values, secrets, live role grants, tenant policy, or ACL authorization and must not be used by itself to revoke privileges."
        ),
        "summary": summary,
        "process_and_credential_policy": role_contract,
        "api_roots": api_roots,
        "api_dynamic_dispatch_edges": api_graph["dynamic_dispatch_edges"],
        "api_import_closure_review": {
            "source_file_count": len(api_closure["source_files"]),
            "unresolved_local_modules": api_closure["unresolved_local_modules"],
            "dynamic_import_sites": api_closure["dynamic_import_sites"],
        },
        "unresolved_api_route_registrations": unresolved_registrations,
        "worker_operation_roots": [
            {
                "operation_ref": operation["operation_ref"],
                "kind": operation["kind"],
                "name": operation["name"],
                "statically_reachable_sql_site_count": operation["statically_reachable_sql_site_count"],
                "credential_path": _worker_operation_credential_path(operation, isolation_flags),
                "dynamic_dispatch_edges": worker_function_operations.get(
                    operation["operation_ref"], {}
                ).get("dynamic_dispatch_edges", []),
                "activation": (
                    "allowlisted_not_proven_active_persisted_schedule_unknown"
                    if operation["kind"] == "scheduled_module"
                    else "handler_allowlisted_event_traffic_and_registration_unassessed"
                    if operation["kind"] == "event_handler"
                    else "isolated_operation_feature_and_runtime_invocation_unassessed"
                ),
            }
            for operation in worker_sql["operations"]
        ],
        "execution_sites": records,
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the generated attribution inventory")
    group.add_argument("--check", type=Path, help="Fail if the saved inventory is stale")
    args = parser.parse_args(argv)
    expected = _serialize(build_inventory())

    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")
        return 0

    check = args.check if args.check.is_absolute() else ROOT / args.check
    try:
        actual = check.read_text(encoding="utf-8")
    except OSError:
        print(f"Missing runtime role attribution inventory: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Runtime role attribution inventory is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
