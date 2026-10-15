#!/usr/bin/env python3
"""Inventory high-confidence effect call sites in statically reachable workers.

This is a source review aid. It reports selected direct calls that can cross a
process, filesystem, network, chain, cache, notification, or object-storage
boundary. It does not infer whether branches execute, resolve arbitrary
callbacks, inspect provider internals, or establish idempotency or authority.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.worker_function_reachability import build_inventory  # noqa: E402


def _dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _imports(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{base}.{alias.name}".strip(".")
    return aliases


class _FunctionNodes(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.nodes: dict[str, ast.AST] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        key = ".".join([*self.scope, node.name])
        self.nodes[key] = node
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def _function_calls(node: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    pending = list(ast.iter_child_nodes(node))
    while pending:
        child = pending.pop()
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(child, ast.Call):
            calls.append(child)
        pending.extend(ast.iter_child_nodes(child))
    return calls


def _event_process_dispatch(graph: dict, function_nodes: dict[str, dict[str, ast.AST]]) -> list[dict]:
    """Describe the statically named EventBus child callback and allowlist path."""
    source = "services/events/bus.py"
    nodes = function_nodes.get(source, {})
    invoke = nodes.get("EventBus._invoke_handler")
    child = nodes.get("_handler_process")
    resolver = nodes.get("resolve_handler")
    if not invoke or not child or not resolver:
        return []

    invoke_calls = _function_calls(invoke)
    child_calls = _function_calls(child)
    resolver_calls = _function_calls(resolver)
    process_call = next(
        (
            call
            for call in invoke_calls
            if (_dotted(call.func) or "").split(".")[-1] == "Process"
            and any(
                keyword.arg == "target"
                and isinstance(keyword.value, ast.Name)
                and keyword.value.id == "_handler_process"
                for keyword in call.keywords
            )
        ),
        None,
    )
    resolve_call = next((call for call in child_calls if _dotted(call.func) == "resolve_handler"), None)
    validate_call = next(
        (call for call in resolver_calls if (_dotted(call.func) or "").endswith("validate_event_handler")), None
    )
    import_call = next((call for call in resolver_calls if (_dotted(call.func) or "").endswith("import_module")), None)
    handler_calls = [call for call in child_calls if _dotted(call.func) == "handler"]
    required = (process_call, resolve_call, validate_call, import_call)
    if not all(required) or not handler_calls:
        return []

    allowed_handlers = sorted(
        operation["name"] for operation in graph["operations"] if operation["kind"] == "event_handler"
    )
    return [
        {
            "dispatcher": "services.events.bus:EventBus._invoke_handler",
            "source": source,
            "process_creation_line": process_call.lineno,
            "process_callback": "services.events.bus:_handler_process",
            "callback_resolver": "services.events.bus:resolve_handler",
            "resolver_call_line": resolve_call.lineno,
            "allowlist_validator": "services.security.execution_allowlist.validate_event_handler",
            "allowlist_validation_line": validate_call.lineno,
            "dynamic_import_line": import_call.lineno,
            "dynamic_handler_invocation_lines": sorted(call.lineno for call in handler_calls),
            "allowlisted_handler_targets": allowed_handlers,
            "validation_precedes_dynamic_import": validate_call.lineno < import_call.lineno,
            "runtime_dispatch_verified": False,
        }
    ]


def _classify(call_name: str, aliases: dict[str, str], source: str) -> tuple[str, str] | None:
    parts = call_name.split(".")
    normalized = ".".join([aliases.get(parts[0], parts[0]), *parts[1:]])
    lower = normalized.lower()

    if re.match(r"^(subprocess\.(run|popen|call|check_call|check_output)|os\.(system|popen|exec[a-z]*))$", lower):
        return "process", normalized
    multiprocessing_imported = any(
        value == "multiprocessing" or value.startswith("multiprocessing.") for value in aliases.values()
    )
    if multiprocessing_imported and parts[-1].lower() in {"process", "start", "join", "terminate"}:
        return "process", normalized
    if normalized in {"importlib.import_module", "builtins.__import__", "__import__"}:
        return "dynamic_import", normalized
    if normalized == "open" or lower in {
        "builtins.open",
        "pathlib.path.open",
        "pathlib.path.read_text",
        "pathlib.path.write_text",
        "pathlib.path.unlink",
        "pathlib.path.mkdir",
        "pathlib.path.replace",
        "pathlib.path.rename",
        "os.open",
        "os.remove",
        "os.unlink",
        "os.replace",
        "os.rename",
        "os.mkdir",
        "os.makedirs",
        "shutil.copy",
        "shutil.copy2",
        "shutil.move",
        "shutil.rmtree",
        "tempfile.mkstemp",
        "tempfile.mkdtemp",
        "tempfile.namedtemporaryfile",
    }:
        return "filesystem", normalized
    if lower.startswith(("requests.", "httpx.", "urllib.request.", "aiohttp.", "services.common.http.")):
        return "http", normalized
    if lower.startswith("smtplib.") or (
        "smtplib" in aliases.values() and parts[-1].lower() in {"sendmail", "send_message"}
    ):
        return "email_delivery", normalized
    if lower.startswith(("boto3.", "botocore.", "minio.")) or lower.endswith(
        (".upload_file", ".download_file", ".put_object", ".get_object", ".delete_object")
    ):
        return "object_storage", normalized
    if lower.endswith(".eth.contract") or lower.endswith(".httpprovider"):
        return "evm_client_setup", normalized
    if re.search(r"\.eth\.(get_[a-z0-9_]+|send_[a-z0-9_]+|wait_for_[a-z0-9_]+|call|estimate_gas)$", lower):
        return "evm_rpc", normalized
    if "mqtt" in lower and parts[-1] in {"create_client", "publish", "connect"}:
        return "mqtt", normalized
    if lower.endswith((".send_email_notification", ".deliver_notification", ".send_webhook", ".send_notification")):
        return "notification_delivery", normalized
    if lower.startswith(("redis.", "services.core.cache.", "services.core.adapters.cache.")):
        return "cache_provider", normalized
    if lower in {"multiprocessing.process", "concurrent.futures.processpoolexecutor.submit", "threading.thread.start"}:
        return "concurrent_execution", normalized
    # Requests routed through an injected session are still visible in the
    # shared HTTP wrapper, whose module imports requests directly.
    if source == "services/common/http.py" and parts[-1] in {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "request",
        "send",
    }:
        return "http", normalized
    return None


def build_effect_inventory() -> dict:
    graph = build_inventory()
    trees: dict[str, ast.Module] = {}
    function_nodes: dict[str, dict[str, ast.AST]] = {}
    import_aliases: dict[str, dict[str, str]] = {}
    for operation in graph["operations"]:
        for function in operation["reachable_functions"]:
            source = function["source"]
            if source not in trees:
                tree = ast.parse((ROOT / source).read_text(encoding="utf-8"), filename=source)
                trees[source] = tree
                collector = _FunctionNodes()
                collector.visit(tree)
                function_nodes[source] = collector.nodes
                import_aliases[source] = _imports(tree)

    operations = []
    total = Counter()
    unique_sites: dict[tuple[str, int, str, str], str] = {}
    for operation in graph["operations"]:
        sites: dict[tuple[str, int, str, str, str], dict] = {}
        for function in operation["reachable_functions"]:
            source = function["source"]
            node = function_nodes[source].get(function["qualname"])
            if node is None:
                continue
            for call in _function_calls(node):
                name = _dotted(call.func)
                if not name:
                    continue
                match = _classify(name, import_aliases[source], source)
                if not match:
                    continue
                category, normalized = match
                key = (source, call.lineno, function["key"], category, normalized)
                site = {
                    "source": source,
                    "line": call.lineno,
                    "function": function["key"],
                    "category": category,
                    "call": normalized,
                }
                if name.split(".")[-1].lower() == "process":
                    target = next((keyword.value for keyword in call.keywords if keyword.arg == "target"), None)
                    if isinstance(target, ast.Name):
                        site["callback_target"] = target.id
                sites[key] = site
        ordered_sites = [sites[key] for key in sorted(sites)]
        counts = Counter(site["category"] for site in ordered_sites)
        total.update(counts)
        for site in ordered_sites:
            unique_sites[(site["source"], site["line"], site["category"], site["call"])] = site["category"]
        operations.append(
            {
                "kind": operation["kind"],
                "name": operation["name"],
                "candidate_effect_sites": ordered_sites,
                "category_counts": dict(sorted(counts.items())),
            }
        )

    callback_dispatches = _event_process_dispatch(graph, function_nodes)
    return {
        "version": 1,
        "generated_by": "scripts/worker_effect_inventory.py",
        "reviewed": "2026-10-15",
        "scope": (
            "High-confidence direct call patterns found inside the current static worker function-reachability graph. "
            "The operation graph conservatively includes some CLI branches that runtime command contracts reject. "
            "A listed call is a review candidate, not proof it executes; absence is not proof of no effect. "
            "Callbacks, arbitrary dynamic dispatch, provider internals, database-side effects, and unmodeled imports are not established. "
            "This is not an authorization, idempotency, or least-privilege policy."
        ),
        "summary": {
            "operation_roots": len(operations),
            "candidate_effect_sites": len(unique_sites),
            "operation_site_memberships": sum(total.values()),
            "unique_sites_by_category": dict(sorted(Counter(unique_sites.values()).items())),
            "operation_memberships_by_category": dict(sorted(total.items())),
        },
        "callback_dispatches": callback_dispatches,
        "operations": operations,
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write generated effect inventory")
    group.add_argument("--check", type=Path, help="Fail if saved inventory is stale")
    args = parser.parse_args(argv)
    expected = _serialize(build_effect_inventory())
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")
        return 0
    check = args.check if args.check.is_absolute() else ROOT / args.check
    try:
        actual = check.read_text(encoding="utf-8")
    except OSError:
        print(f"Missing worker effect inventory: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Worker effect inventory is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
