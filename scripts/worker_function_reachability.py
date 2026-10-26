#!/usr/bin/env python3
"""Build a conservative direct-call graph for source-registered worker operations.

The graph follows statically resolved Python function calls within each
operation's local ``services.*`` import closure. It is a review index, not a
complete runtime call graph, effect proof, authorization policy, or tenant
boundary. Dynamic dispatch, callbacks, methods on unknown instances, extension
code, and database/provider-side behavior may not be represented.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.worker_source_closure as worker_source_closure  # noqa: E402
from services.security.execution_allowlist import (  # noqa: E402
    ISOLATED_WORKER_ENTRYPOINTS,
    SIGNED_SOURCE_FUNCTIONS,
)


def _function_key(module: str, qualname: str) -> str:
    return f"{module}:{qualname}"


class _DefinitionVisitor(ast.NodeVisitor):
    def __init__(self, module: str, source: str):
        self.module = module
        self.source = source
        self.scope: list[str] = []
        self.class_scope: list[str] = []
        self.definitions: dict[str, dict] = {}
        self.classes: dict[str, dict] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = ".".join([*self.scope, node.name])
        key = _function_key(self.module, qualname)
        self.classes[key] = {
            "key": key,
            "module": self.module,
            "qualname": qualname,
            "source": self.source,
            "line": node.lineno,
            "node": node,
        }
        self.scope.append(node.name)
        self.class_scope.append(node.name)
        self.generic_visit(node)
        self.class_scope.pop()
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qualname = ".".join([*self.scope, node.name])
        key = _function_key(self.module, qualname)
        self.definitions[key] = {
            "key": key,
            "module": self.module,
            "qualname": qualname,
            "class_scope": ".".join(self.class_scope) if self.class_scope else None,
            "source": self.source,
            "line": node.lineno,
            "node": node,
        }
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


class _ImportContextVisitor(ast.NodeVisitor):
    def __init__(
        self,
        module: str,
        source: str,
        known_modules: set[str],
        definitions: dict[str, dict],
        classes: dict[str, dict],
    ):
        self.module = module
        self.source = ROOT / source
        self.known_modules = known_modules
        self.definitions = definitions
        self.classes = classes
        self.module_aliases: dict[str, str] = {}
        self.symbol_aliases: dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname:
                self.module_aliases[alias.asname] = alias.name
            else:
                self.module_aliases[alias.name.split(".", 1)[0]] = alias.name.split(".", 1)[0]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = worker_source_closure._resolve_import_from(self.module, self.source, node)
        if not base:
            return
        for alias in node.names:
            local_name = alias.asname or alias.name
            if alias.name == "*":
                continue
            imported_function = _function_key(base, alias.name)
            imported_module = f"{base}.{alias.name}"
            if imported_function in self.definitions or imported_function in self.classes:
                self.symbol_aliases[local_name] = imported_function
            elif imported_module in self.known_modules:
                self.module_aliases[local_name] = imported_module


def _collect_modules(source_files: list[str]) -> tuple[dict[str, ast.Module], dict[str, str]]:
    trees = {}
    modules_by_source = {}
    for source in source_files:
        path = ROOT / source
        module = worker_source_closure._module_for_path(path)
        modules_by_source[source] = module
        try:
            trees[module] = ast.parse(path.read_text(encoding="utf-8"), filename=source)
        except (OSError, SyntaxError) as exc:
            raise ValueError(f"Unable to parse worker source {source}") from exc
    return trees, modules_by_source


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _resolve_module_call(imported_module: str, suffix: str, definitions: dict[str, dict]) -> str | None:
    parts = suffix.split(".")
    for module_part_count in range(len(parts), 0, -1):
        module = ".".join([imported_module, *parts[:module_part_count]])
        qualname = ".".join(parts[module_part_count:])
        candidate = _function_key(module, qualname) if qualname else ""
        if candidate in definitions:
            return candidate
    candidate = _function_key(imported_module, suffix)
    return candidate if candidate in definitions else None


def _class_key(module: str, qualname: str) -> str:
    return _function_key(module, qualname)


def _resolve_module_class(imported_module: str, suffix: str, classes: dict[str, dict]) -> str | None:
    parts = suffix.split(".")
    for module_part_count in range(len(parts), 0, -1):
        module = ".".join([imported_module, *parts[:module_part_count]])
        qualname = ".".join(parts[module_part_count:])
        candidate = _class_key(module, qualname) if qualname else ""
        if candidate in classes:
            return candidate
    candidate = _class_key(imported_module, suffix)
    return candidate if candidate in classes else None


def _resolve_class_target(
    function: dict,
    call: ast.Call,
    classes: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
) -> str | None:
    module = function["module"]
    context = contexts[module]
    expression = _dotted_name(call.func)
    if not expression:
        return None
    if isinstance(call.func, ast.Name):
        imported = context.symbol_aliases.get(expression)
        if imported in classes:
            return imported
        local = _class_key(module, expression)
        return local if local in classes else None
    prefix, separator, suffix = expression.partition(".")
    if not separator:
        return None
    imported = context.symbol_aliases.get(prefix)
    if imported in classes:
        candidate = f"{imported}.{suffix}"
        return candidate if candidate in classes else None
    imported_module = context.module_aliases.get(prefix)
    if imported_module:
        return _resolve_module_class(imported_module, suffix, classes)
    candidate = _class_key(module, expression)
    return candidate if candidate in classes else None


def _nested_function_node(node: ast.AST, root: ast.AST) -> bool:
    return node is not root and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))


def _return_class_targets(
    function_key: str,
    definitions: dict[str, dict],
    classes: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
    seen: set[str] | None = None,
) -> set[str]:
    seen = set() if seen is None else seen
    if function_key in seen or function_key not in definitions:
        return set()
    seen.add(function_key)
    function = definitions[function_key]
    targets = set()
    pending = list(function["node"].body)
    while pending:
        node = pending.pop()
        if _nested_function_node(node, function["node"]):
            continue
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
            class_target = _resolve_class_target(function, node.value, classes, contexts)
            if class_target:
                targets.add(class_target)
            else:
                called = _resolve_call_target(function, node.value, definitions, contexts)
                if called:
                    targets.update(_return_class_targets(called, definitions, classes, contexts, seen))
        pending.extend(ast.iter_child_nodes(node))
    return targets


def _annotation_class_targets(
    annotation: ast.AST | None,
    function: dict,
    classes: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
) -> set[str]:
    if annotation is None or isinstance(annotation, ast.Constant):
        return set()
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _annotation_class_targets(annotation.left, function, classes, contexts) | _annotation_class_targets(
            annotation.right, function, classes, contexts
        )
    if isinstance(annotation, ast.Name):
        context = contexts[function["module"]]
        imported = context.symbol_aliases.get(annotation.id)
        if imported in classes:
            return {imported}
        local = _class_key(function["module"], annotation.id)
        return {local} if local in classes else set()
    if isinstance(annotation, ast.Attribute):
        expression = _dotted_name(annotation)
        if expression:
            prefix, separator, suffix = expression.partition(".")
            imported_module = contexts[function["module"]].module_aliases.get(prefix)
            if imported_module and separator:
                target = _resolve_module_class(imported_module, suffix, classes)
                return {target} if target else set()
        return set()
    if isinstance(annotation, ast.Subscript):
        targets = set()
        values = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
        for value in values:
            targets.update(_annotation_class_targets(value, function, classes, contexts))
        return targets
    return set()


def _expression_class_targets(
    expression: ast.AST,
    function: dict,
    definitions: dict[str, dict],
    classes: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
    local_types: dict[str, set[str]],
) -> set[str]:
    if isinstance(expression, ast.Name):
        if expression.id in local_types:
            return local_types[expression.id]
        imported = contexts[function["module"]].symbol_aliases.get(expression.id)
        return {imported} if imported in classes else set()
    if isinstance(expression, ast.IfExp):
        left = _expression_class_targets(expression.body, function, definitions, classes, contexts, local_types)
        right = _expression_class_targets(expression.orelse, function, definitions, classes, contexts, local_types)
        return left | right if left and right else set()
    if isinstance(expression, ast.Call):
        class_target = _resolve_class_target(function, expression, classes, contexts)
        if class_target:
            return {class_target}
        function_target = _resolve_call_target(function, expression, definitions, contexts)
        return _return_class_targets(function_target, definitions, classes, contexts) if function_target else set()
    return set()


def _binding_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_binding_names(item) for item in target.elts)) if target.elts else set()
    return set()


def _infer_instance_types(
    function: dict,
    definitions: dict[str, dict],
    classes: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
    injected_instance_types: dict[str, set[str]] | None = None,
) -> dict[str, set[str]]:
    function_node = function["node"]
    local_types: dict[str, set[str]] = {}
    if function.get("class_scope") and function_node.args.args:
        local_types[function_node.args.args[0].arg] = {_class_key(function["module"], function["class_scope"])}
    for argument in [*function_node.args.posonlyargs, *function_node.args.args, *function_node.args.kwonlyargs]:
        targets = _annotation_class_targets(argument.annotation, function, classes, contexts)
        if targets:
            local_types[argument.arg] = targets
    for name, targets in (injected_instance_types or {}).items():
        local_types.setdefault(name, set()).update(targets)

    assignments: dict[str, list[ast.AST]] = defaultdict(list)
    pending = list(function_node.body)
    while pending:
        node = pending.pop()
        if _nested_function_node(node, function_node):
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for name in _binding_names(target):
                    assignments[name].append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            annotation_types = _annotation_class_targets(node.annotation, function, classes, contexts)
            if annotation_types:
                local_types[node.target.id] = annotation_types
            if node.value is not None:
                assignments[node.target.id].append(node.value)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if isinstance(item.optional_vars, ast.Name):
                    assignments[item.optional_vars.id].append(item.context_expr)
        pending.extend(ast.iter_child_nodes(node))

    for _ in range(len(assignments) + 1):
        changed = False
        for name, expressions in assignments.items():
            inferred = [
                _expression_class_targets(expression, function, definitions, classes, contexts, local_types)
                for expression in expressions
            ]
            if inferred and all(inferred):
                combined = set().union(*inferred)
                if local_types.get(name) != combined:
                    local_types[name] = combined
                    changed = True
        if not changed:
            break
    return local_types


def _resolve_call_targets(
    function: dict,
    call: ast.Call,
    definitions: dict[str, dict],
    classes: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
    instance_types: dict[str, set[str]],
) -> list[str]:
    module = function["module"]
    qualname = function["qualname"]
    context = contexts[module]
    expression = _dotted_name(call.func)
    if not expression:
        return []

    if isinstance(call.func, ast.Name):
        imported = context.symbol_aliases.get(expression)
        if imported in definitions:
            return [imported]
        local = _function_key(module, expression)
        if local in definitions:
            return [local]
        parent = qualname.rpartition(".")[0]
        while parent:
            nested = _function_key(module, f"{parent}.{expression}")
            if nested in definitions:
                return [nested]
            parent = parent.rpartition(".")[0]
        return []

    prefix, separator, suffix = expression.partition(".")
    if not separator:
        return []

    if prefix in {"self", "cls"}:
        class_name = function.get("class_scope")
        candidate = _function_key(module, f"{class_name}.{suffix}") if class_name else ""
        return [candidate] if candidate in definitions else []

    if prefix in instance_types:
        candidates = [f"{class_key}.{suffix}" for class_key in sorted(instance_types[prefix])]
        if candidates and all(candidate in definitions for candidate in candidates):
            return candidates

    imported = context.symbol_aliases.get(prefix)
    if imported:
        candidate = f"{imported}.{suffix}"
        return [candidate] if candidate in definitions else []

    imported_module = context.module_aliases.get(prefix)
    if imported_module:
        candidate = _resolve_module_call(imported_module, suffix, definitions)
        return [candidate] if candidate else []

    candidate = _function_key(module, expression)
    return [candidate] if candidate in definitions else []


def _resolve_call_target(
    function: dict,
    call: ast.Call,
    definitions: dict[str, dict],
    import_contexts: dict[str, _ImportContextVisitor],
) -> str | None:
    targets = _resolve_call_targets(function, call, definitions, {}, import_contexts, {})
    return targets[0] if targets else None


class _CallVisitor(ast.NodeVisitor):
    def __init__(
        self,
        function: dict,
        definitions: dict[str, dict],
        classes: dict[str, dict],
        contexts: dict[str, _ImportContextVisitor],
        injected_instance_types: dict[str, set[str]] | None = None,
    ):
        self.function = function
        self.definitions = definitions
        self.classes = classes
        self.contexts = contexts
        self.instance_types = _infer_instance_types(
            function, definitions, classes, contexts, injected_instance_types
        )
        self.edges: list[dict] = []
        self.callback_edges: list[dict] = []
        self.parameter_bindings: list[dict] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.function["node"]:
            for statement in node.body:
                self.visit(statement)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        targets = _resolve_call_targets(
            self.function,
            node,
            self.definitions,
            self.classes,
            self.contexts,
            self.instance_types,
        )
        for target in targets:
            self.edges.append(
                {
                    "caller": self.function["key"],
                    "callee": target,
                    "source": self.function["source"],
                    "line": node.lineno,
                }
            )
            if target not in self.definitions:
                continue
            target_node = self.definitions[target]["node"]
            target_parameters = {
                argument.arg
                for argument in [
                    *target_node.args.posonlyargs,
                    *target_node.args.args,
                    *target_node.args.kwonlyargs,
                ]
            }
            for keyword in node.keywords:
                if keyword.arg not in target_parameters:
                    continue
                class_targets = _expression_class_targets(
                    keyword.value,
                    self.function,
                    self.definitions,
                    self.classes,
                    self.contexts,
                    self.instance_types,
                )
                for class_target in sorted(class_targets):
                    self.parameter_bindings.append(
                        {
                            "caller": self.function["key"],
                            "callee": target,
                            "parameter": keyword.arg,
                            "instance_class": class_target,
                            "source": self.function["source"],
                            "line": node.lineno,
                        }
                    )
        process_target = next(
            (
                keyword.value
                for keyword in node.keywords
                if keyword.arg == "target" and isinstance(keyword.value, (ast.Name, ast.Attribute))
            ),
            None,
        )
        call_name = _dotted_name(node.func)
        import_context = self.contexts[self.function["module"]]
        multiprocessing_imported = any(
            value == "multiprocessing" or value.startswith("multiprocessing.")
            for value in (*import_context.module_aliases.values(), *import_context.symbol_aliases.values())
        )
        if (
            process_target is not None
            and call_name
            and call_name.split(".")[-1] == "Process"
            and multiprocessing_imported
        ):
            target_call = ast.Call(func=process_target, args=[], keywords=[])
            callback_targets = _resolve_call_targets(
                self.function,
                target_call,
                self.definitions,
                self.classes,
                self.contexts,
                self.instance_types,
            )
            for target in callback_targets:
                self.callback_edges.append(
                    {
                        "caller": self.function["key"],
                        "callee": target,
                        "source": self.function["source"],
                        "line": node.lineno,
                        "dispatch": "multiprocessing_process_target",
                    }
                )
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        previous = self.instance_types
        narrowed = {name: set(types) for name, types in previous.items()}
        for name, targets in _positive_isinstance_narrowing(
            node.test,
            self.function,
            self.classes,
            self.contexts,
        ).items():
            narrowed.setdefault(name, set()).update(targets)
        self.instance_types = narrowed
        for statement in node.body:
            self.visit(statement)
        self.instance_types = previous
        for statement in node.orelse:
            self.visit(statement)


def _is_main_guard(test: ast.expr) -> bool:
    return isinstance(test, ast.Compare) and (
        isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and any(
            isinstance(comparator, ast.Constant) and comparator.value == "__main__" for comparator in test.comparators
        )
    )


def _positive_isinstance_narrowing(
    test: ast.expr,
    function: dict,
    classes: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
) -> dict[str, set[str]]:
    """Return safe positive type facts implied by an if-test expression."""
    calls = [test]
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        calls = list(test.values)

    narrowed: dict[str, set[str]] = defaultdict(set)
    for candidate in calls:
        if not isinstance(candidate, ast.Call) or _dotted_name(candidate.func) != "isinstance":
            continue
        if len(candidate.args) != 2 or not isinstance(candidate.args[0], ast.Name):
            continue
        narrowed[candidate.args[0].id].update(_annotation_class_targets(candidate.args[1], function, classes, contexts))
    return dict(narrowed)


class _RootCallVisitor(ast.NodeVisitor):
    def __init__(self, module: str, contexts: dict[str, _ImportContextVisitor], definitions: dict[str, dict]):
        self.module = module
        self.contexts = contexts
        self.definitions = definitions
        self.calls: list[tuple[str, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        synthetic = {"module": self.module, "qualname": ""}
        target = _resolve_call_target(synthetic, node, self.definitions, self.contexts)
        if target:
            self.calls.append((target, node.lineno))
        context = self.contexts[self.module]
        if (
            isinstance(node.func, ast.Name)
            and context.symbol_aliases.get(node.func.id) == "services.common.cli:run"
            and node.args
        ):
            callback = node.args[0]
            if isinstance(callback, (ast.Name, ast.Attribute)):
                callback_call = ast.Call(func=callback, args=[], keywords=[])
                callback_target = _resolve_call_target(
                    synthetic,
                    callback_call,
                    self.definitions,
                    self.contexts,
                )
                if callback_target:
                    self.calls.append((callback_target, node.lineno))
        self.generic_visit(node)


def _operation_roots(
    operation: dict,
    modules_by_source: dict[str, str],
    trees: dict[str, ast.Module],
    contexts: dict[str, _ImportContextVisitor],
    definitions: dict[str, dict],
) -> list[dict]:
    if operation["kind"] == "event_handler":
        module, _, function = operation["name"].rpartition(".")
        key = _function_key(module, function)
        return (
            [{"function": key, "source": definitions[key]["source"], "line": definitions[key]["line"]}]
            if key in definitions
            else []
        )

    if operation["kind"] == "isolated_worker":
        module = operation["root_modules"][0]
        function = ISOLATED_WORKER_ENTRYPOINTS.get(module)
        key = _function_key(module, function) if function else ""
        return (
            [{"function": key, "source": definitions[key]["source"], "line": definitions[key]["line"]}]
            if key in definitions
            else []
        )

    if operation["kind"] == "signed_source_function":
        module, _, function = operation["name"].rpartition(".")
        key = _function_key(module, function)
        return (
            [{"function": key, "source": definitions[key]["source"], "line": definitions[key]["line"]}]
            if (module, function) in SIGNED_SOURCE_FUNCTIONS and key in definitions
            else []
        )

    root_module = operation["root_modules"][0]
    root_paths = worker_source_closure._module_paths(root_module)
    package_main = next((path for path in root_paths if path.name == "__main__.py"), None)
    executed_path = package_main or next((path for path in root_paths if path.name != "__init__.py"), None)
    if executed_path is None:
        return []
    source = executed_path.relative_to(ROOT).as_posix()
    module = modules_by_source.get(source)
    if not module:
        return []

    roots = []
    tree = trees[module]
    for statement in tree.body:
        if isinstance(statement, ast.If) and _is_main_guard(statement.test):
            visitor = _RootCallVisitor(module, contexts, definitions)
            for guarded_statement in statement.body:
                visitor.visit(guarded_statement)
            roots.extend(
                {"function": key, "source": source, "line": line} for key, line in visitor.calls if key in definitions
            )
    unique = {(root["function"], root["source"], root["line"]): root for root in roots}
    return [unique[key] for key in sorted(unique)]


def _registered_metric_calculators(
    modules_by_source: dict[str, str],
    trees: dict[str, ast.Module],
    contexts: dict[str, _ImportContextVisitor],
    definitions: dict[str, dict],
) -> list[dict]:
    registry_source = "services/metrics/calculators/__init__.py"
    registry_module = modules_by_source.get(registry_source)
    caller_key = "services.metrics.engine:compute_metric"
    if not registry_module or caller_key not in definitions:
        return []

    registry_values: dict[str, str] = {}
    for statement in trees[registry_module].body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        value = statement.value
        if value is None or not any(isinstance(target, ast.Name) and target.id == "CALCULATORS" for target in targets):
            continue
        if not isinstance(value, ast.Dict):
            continue
        for key_node, value_node in zip(value.keys, value.values):
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                continue
            if not isinstance(value_node, ast.Name):
                continue
            target = contexts[registry_module].symbol_aliases.get(value_node.id)
            if target in definitions:
                registry_values[key_node.value] = target

    caller = definitions[caller_key]
    dispatch_line = next(
        (
            node.lineno
            for node in ast.walk(caller["node"])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "calculator"
        ),
        caller["line"],
    )
    return [
        {
            "caller": caller_key,
            "callee": callee,
            "source": caller["source"],
            "line": dispatch_line,
            "dispatch": "literal_function_registry",
            "registry": "services.metrics.calculators.CALCULATORS",
            "registry_key": key,
        }
        for key, callee in sorted(registry_values.items())
    ]


def _scheduled_sensor_driver_targets() -> list[dict[str, str]]:
    """Read the literal code-owned registry for scheduled sensor driver loads."""
    source = ROOT / "services/drivers/registry.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    registry = None
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if not any(isinstance(target, ast.Name) and target.id == "SCHEDULED_SENSOR_DRIVER_TARGETS" for target in targets):
            continue
        value = statement.value
        if isinstance(value, ast.Call):
            if _dotted_name(value.func) != "MappingProxyType" or len(value.args) != 1 or value.keywords:
                raise ValueError("scheduled sensor driver registry must use a literal immutable mapping")
            value = value.args[0]
        if isinstance(value, ast.Dict):
            registry = value
        break

    if registry is None:
        raise ValueError("scheduled sensor driver registry must remain a literal dictionary")

    targets = []
    for name_node, target_node in zip(registry.keys, registry.values):
        if (
            not isinstance(name_node, ast.Constant)
            or not isinstance(name_node.value, str)
            or not isinstance(target_node, (ast.Tuple, ast.List))
            or len(target_node.elts) != 3
            or not all(isinstance(value, ast.Constant) and isinstance(value.value, str) for value in target_node.elts)
        ):
            raise ValueError("scheduled sensor driver target must contain literal name/module/class/type values")
        module_path, class_name, driver_type = (value.value for value in target_node.elts)
        targets.append(
            {
                "driver_name": name_node.value,
                "module": module_path,
                "class_name": class_name,
                "driver_type": driver_type,
            }
        )
    return targets


def _class_method_target(
    class_key: str,
    method_name: str,
    classes: dict[str, dict],
    definitions: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
    seen: set[str] | None = None,
) -> str | None:
    """Resolve a method on a literal allowlisted class, including static bases."""
    seen = set() if seen is None else seen
    if class_key in seen or class_key not in classes:
        return None
    seen.add(class_key)
    method_key = f"{class_key}.{method_name}"
    if method_key in definitions:
        return method_key
    class_info = classes[class_key]
    synthetic_function = {"module": class_info["module"]}
    for base in class_info["node"].bases:
        for base_key in sorted(_annotation_class_targets(base, synthetic_function, classes, contexts)):
            resolved = _class_method_target(base_key, method_name, classes, definitions, contexts, seen)
            if resolved:
                return resolved
    return None


def _scheduled_sensor_driver_dispatches(
    operation: dict,
    definitions: dict[str, dict],
    classes: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
) -> list[dict]:
    """Link sensor worker dynamic class/method calls to its literal driver registry."""
    if operation["name"] != "services.ingestion.sensor_worker":
        return []

    targets = _scheduled_sensor_driver_targets()
    caller_key = "services.ingestion.sensor_worker:_prepare_records"
    caller = definitions.get(caller_key)
    if caller is None:
        return []

    function_node = caller["node"]
    calls = []
    pending = list(function_node.body)
    while pending:
        node = pending.pop()
        if _nested_function_node(node, function_node):
            continue
        if isinstance(node, ast.Call):
            calls.append(node)
        pending.extend(ast.iter_child_nodes(node))

    edges = []
    method_calls = {
        "discover": "discover",
        "fetch_scheduled": "fetch_scheduled",
        "transform": "transform",
    }
    for target in targets:
        class_key = _class_key(target["module"], target["class_name"])
        if class_key not in classes:
            raise ValueError(f"scheduled sensor driver class is not in the source import closure: {class_key}")
        for call in calls:
            expression = _dotted_name(call.func)
            method_name = None
            if expression == "driver_class":
                method_name = "__init__"
            elif expression and expression.startswith("driver."):
                method_name = method_calls.get(expression.partition(".")[2])
            if method_name is None:
                continue
            callee = _class_method_target(class_key, method_name, classes, definitions, contexts)
            if callee is None:
                raise ValueError(
                    "scheduled sensor driver target does not implement a statically resolvable "
                    f"{method_name} method: {class_key}"
                )
            edges.append(
                {
                    "caller": caller_key,
                    "callee": callee,
                    "source": caller["source"],
                    "line": call.lineno,
                    "dispatch": "literal_code_allowlisted_sensor_driver_registry",
                    "registry": "services.drivers.registry.SCHEDULED_SENSOR_DRIVER_TARGETS",
                    "registry_key": target["driver_name"],
                }
            )
    return edges


def _registered_synthesis_agent_dispatches(
    operation: dict,
    trees: dict[str, ast.Module],
    definitions: dict[str, dict],
    classes: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
) -> list[dict]:
    """Link the worker's literal task registry to each agent's source methods."""
    if operation["name"] != "services.agents.worker_cli":
        return []

    caller_key = "services.agents.worker_cli:run_worker_synthesis"
    caller = definitions.get(caller_key)
    if caller is None:
        return []

    method_calls: dict[str, int] = {}
    pending = list(caller["node"].body)
    while pending:
        node = pending.pop()
        if _nested_function_node(node, caller["node"]):
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "agent":
                if node.func.attr in {"synthesize", "collect_source_references"}:
                    method_calls[node.func.attr] = node.lineno
        pending.extend(ast.iter_child_nodes(node))

    if set(method_calls) != {"synthesize", "collect_source_references"}:
        raise ValueError("registered synthesis worker method calls changed; review its dynamic dispatch")

    edges = []
    for registered in worker_source_closure._registered_agent_task_targets():
        module = str(registered["module"])
        module_tree = trees.get(module)
        if module_tree is None:
            raise ValueError(f"registered synthesis agent is absent from the source closure: {module}")
        agent_expression = next(
            (
                node.value
                for node in module_tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "agent" for target in node.targets)
            ),
            None,
        )
        if not isinstance(agent_expression, ast.Call):
            raise ValueError(f"registered synthesis module must instantiate its literal agent: {module}")
        synthetic_function = {"module": module, "qualname": ""}
        class_key = _resolve_class_target(synthetic_function, agent_expression, classes, contexts)
        if class_key is None:
            raise ValueError(f"registered synthesis agent class is not statically resolvable: {module}")

        for method_name, line in sorted(method_calls.items()):
            callee = _class_method_target(class_key, method_name, classes, definitions, contexts)
            if callee is None:
                raise ValueError(f"registered synthesis agent has no resolvable {method_name}: {class_key}")
            edges.append(
                {
                    "caller": caller_key,
                    "callee": callee,
                    "source": caller["source"],
                    "line": line,
                    "dispatch": "literal_registered_synthesis_agent_registry",
                    "registry": "services.agents.worker_cli._SYNTHESIS_WORKERS",
                    "registry_key": str(registered["task_key"]),
                }
            )
    return edges


def _registered_deterministic_summary_dispatches(
    operation: dict,
    trees: dict[str, ast.Module],
    definitions: dict[str, dict],
    contexts: dict[str, _ImportContextVisitor],
) -> list[dict]:
    """Trace the worker's default builder and its literal summary generator map."""
    if operation["name"] != "services.agents.worker_cli":
        return []

    worker_module = "services.agents.worker_cli"
    worker_draft_module = "services.agents.worker_draft"
    summary_module = "services.agents.ai_summary"
    if not all(module in trees for module in (worker_module, worker_draft_module, summary_module)):
        raise ValueError("deterministic summary registry modules are absent from the worker source closure")

    expected_types: tuple[str, ...] | None = None
    for statement in trees[worker_draft_module].body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if not any(
            isinstance(target, ast.Name) and target.id == "DETERMINISTIC_SUMMARY_TYPES"
            for target in targets
        ):
            continue
        value = statement.value
        if not isinstance(value, (ast.Tuple, ast.List)) or not all(
            isinstance(item, ast.Constant) and isinstance(item.value, str) for item in value.elts
        ):
            raise ValueError("deterministic summary types must remain a literal sequence")
        expected_types = tuple(item.value for item in value.elts)
        break
    if not expected_types:
        raise ValueError("deterministic summary type allowlist is missing")

    registry: dict[str, str] = {}
    registry_found = False
    for statement in trees[summary_module].body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        value = statement.value
        if value is None:
            continue
        if any(isinstance(target, ast.Name) and target.id == "GENERATORS" for target in targets):
            if not isinstance(value, ast.Dict):
                raise ValueError("AI summary generator registry must start as a literal dictionary")
            registry_found = True
            for key_node, value_node in zip(value.keys, value.values):
                if (
                    not isinstance(key_node, ast.Constant)
                    or not isinstance(key_node.value, str)
                    or not isinstance(value_node, ast.Name)
                ):
                    raise ValueError("AI summary generator registry entries must be literal names")
                target = _function_key(summary_module, value_node.id)
                if target not in definitions:
                    raise ValueError(f"AI summary generator is not a local function: {target}")
                registry[key_node.value] = target
            continue

        if not registry_found:
            continue
        for target in targets:
            if not (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "GENERATORS"
                and isinstance(target.slice, ast.Constant)
                and isinstance(target.slice.value, str)
            ):
                continue
            if not isinstance(value, ast.Name):
                raise ValueError("AI summary generator extensions must name a local function")
            function_key = _function_key(summary_module, value.id)
            if function_key not in definitions:
                raise ValueError(f"AI summary generator is not a local function: {function_key}")
            registry[target.slice.value] = function_key

    if not registry_found or tuple(registry) != expected_types:
        raise ValueError("AI summary generator registry must match deterministic worker types in order")

    caller_key = f"{worker_module}:run_worker_summary"
    caller = definitions.get(caller_key)
    build_summary_key = contexts[worker_module].symbol_aliases.get("build_summary")
    if caller is None or build_summary_key not in definitions:
        raise ValueError("deterministic summary worker must use the imported build_summary default")

    has_default_builder = any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "generate" for target in node.targets)
        and isinstance(node.value, ast.BoolOp)
        and isinstance(node.value.op, ast.Or)
        and any(isinstance(value, ast.Name) and value.id == "build_summary" for value in node.value.values)
        for node in ast.walk(caller["node"])
    )
    calls_default_builder = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "generate"
        for node in ast.walk(caller["node"])
    )
    if not has_default_builder or not calls_default_builder:
        raise ValueError("deterministic summary default-builder dispatch changed; review its static edge")

    build_caller = definitions[build_summary_key]
    registry_dispatches = [
        node
        for node in ast.walk(build_caller["node"])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Subscript)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "GENERATORS"
        and isinstance(node.func.slice, ast.Name)
        and node.func.slice.id == "summary_type"
    ]
    if len(registry_dispatches) != 1:
        raise ValueError("AI summary builder must keep one exact GENERATORS[summary_type] dispatch")

    combined_key = registry["combined"]
    combined = definitions[combined_key]
    iterates_registry = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "items"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "GENERATORS"
        for node in ast.walk(combined["node"])
    )
    calls_generator = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "gen_func"
        for node in ast.walk(combined["node"])
    )
    skips_combined = any(
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "summary_type"
        and any(isinstance(item, ast.Constant) and item.value == "combined" for item in node.comparators)
        for node in ast.walk(combined["node"])
    )
    if not (iterates_registry and calls_generator and skips_combined):
        raise ValueError("combined AI summary must call each non-combined literal generator")

    edges = [
        {
            "caller": caller_key,
            "callee": build_summary_key,
            "source": caller["source"],
            "line": next(
                node.lineno
                for node in ast.walk(caller["node"])
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "generate"
            ),
            "dispatch": "default_deterministic_summary_builder",
            "registry": "services.agents.worker_cli.run_worker_summary",
            "registry_key": "build_summary_default",
        }
    ]
    dispatch_line = registry_dispatches[0].lineno
    edges.extend(
        {
            "caller": build_summary_key,
            "callee": target,
            "source": build_caller["source"],
            "line": dispatch_line,
            "dispatch": "literal_deterministic_summary_registry",
            "registry": "services.agents.ai_summary.GENERATORS",
            "registry_key": summary_type,
        }
        for summary_type, target in registry.items()
    )
    combined_call_line = next(
        node.lineno
        for node in ast.walk(combined["node"])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "gen_func"
    )
    edges.extend(
        {
            "caller": combined_key,
            "callee": target,
            "source": combined["source"],
            "line": combined_call_line,
            "dispatch": "literal_deterministic_summary_registry_iteration",
            "registry": "services.agents.worker_cli.DETERMINISTIC_SUMMARY_TYPES",
            "registry_key": summary_type,
        }
        for summary_type, target in registry.items()
        if summary_type != "combined"
    )
    return edges


def _dynamic_registry_source_files(operation: dict) -> list[str]:
    """Include the literal scheduled-driver targets in the worker's source graph."""
    if operation["name"] != "services.ingestion.sensor_worker":
        return []
    files = set()
    for target in _scheduled_sensor_driver_targets():
        closure = worker_source_closure._operation(
            "dynamic_registry_target",
            target["driver_name"],
            [target["module"]],
        )
        files.update(closure["source_files"])
    return sorted(files)


def _operation_graph(operation: dict) -> dict:
    source_files = sorted(set(operation["source_files"]) | set(_dynamic_registry_source_files(operation)))
    trees, modules_by_source = _collect_modules(source_files)
    known_modules = set(trees)
    definitions = {}
    classes = {}
    for source, module in modules_by_source.items():
        visitor = _DefinitionVisitor(module, source)
        visitor.visit(trees[module])
        definitions.update(visitor.definitions)
        classes.update(visitor.classes)

    contexts = {}
    for source, module in modules_by_source.items():
        visitor = _ImportContextVisitor(module, source, known_modules, definitions, classes)
        visitor.visit(trees[module])
        contexts[module] = visitor

    roots = _operation_roots(operation, modules_by_source, trees, contexts, definitions)
    registered_edges = _registered_metric_calculators(modules_by_source, trees, contexts, definitions)
    registered_edges.extend(
        _scheduled_sensor_driver_dispatches(operation, definitions, classes, contexts)
    )
    registered_edges.extend(
        _registered_synthesis_agent_dispatches(operation, trees, definitions, classes, contexts)
    )
    registered_edges.extend(
        _registered_deterministic_summary_dispatches(operation, trees, definitions, contexts)
    )
    registered_by_caller: dict[str, list[dict]] = defaultdict(list)
    for edge in registered_edges:
        registered_by_caller[edge["caller"]].append(edge)
    queue = deque(root["function"] for root in roots)
    visited: set[str] = set()
    processed_injection_types: dict[str, tuple] = {}
    injected_types: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    edges = set()
    callback_edges = set()
    injected_bindings = set()
    reached_registered_edges = set()
    while queue:
        key = queue.popleft()
        if key not in definitions:
            continue
        injection_signature = tuple(
            (name, tuple(sorted(targets)))
            for name, targets in sorted(injected_types.get(key, {}).items())
        )
        if processed_injection_types.get(key) == injection_signature:
            continue
        processed_injection_types[key] = injection_signature
        visited.add(key)
        function = definitions[key]
        visitor = _CallVisitor(function, definitions, classes, contexts, injected_types.get(key))
        visitor.visit(function["node"])
        for edge in visitor.edges:
            edge_key = (edge["caller"], edge["callee"], edge["source"], edge["line"])
            edges.add(edge_key)
            if edge["callee"] not in visited:
                queue.append(edge["callee"])
        for binding in visitor.parameter_bindings:
            binding_key = (
                binding["caller"],
                binding["callee"],
                binding["parameter"],
                binding["instance_class"],
                binding["source"],
                binding["line"],
            )
            injected_bindings.add(binding_key)
            target_types = injected_types[binding["callee"]][binding["parameter"]]
            if binding["instance_class"] not in target_types:
                target_types.add(binding["instance_class"])
                queue.append(binding["callee"])
        for edge in visitor.callback_edges:
            edge_key = (edge["caller"], edge["callee"], edge["source"], edge["line"], edge["dispatch"])
            callback_edges.add(edge_key)
            if edge["callee"] not in visited:
                queue.append(edge["callee"])
        for edge in registered_by_caller.get(key, []):
            edge_key = (
                edge["caller"],
                edge["callee"],
                edge["source"],
                edge["line"],
                edge["dispatch"],
                edge["registry"],
                edge["registry_key"],
            )
            reached_registered_edges.add(edge_key)
            if edge["callee"] not in visited:
                queue.append(edge["callee"])

    ordered_edges = [
        {"caller": caller, "callee": callee, "source": source, "line": line}
        for caller, callee, source, line in sorted(edges)
    ]
    ordered_registered_edges = [
        {
            "caller": caller,
            "callee": callee,
            "source": source,
            "line": line,
            "dispatch": dispatch,
            "registry": registry,
            "registry_key": registry_key,
        }
        for caller, callee, source, line, dispatch, registry, registry_key in sorted(reached_registered_edges)
    ]
    ordered_callback_edges = [
        {
            "caller": caller,
            "callee": callee,
            "source": source,
            "line": line,
            "dispatch": dispatch,
        }
        for caller, callee, source, line, dispatch in sorted(callback_edges)
    ]
    ordered_injected_bindings = [
        {
            "caller": caller,
            "callee": callee,
            "parameter": parameter,
            "instance_class": instance_class,
            "source": source,
            "line": line,
        }
        for caller, callee, parameter, instance_class, source, line in sorted(injected_bindings)
    ]
    ordered_functions = [
        {key: value for key, value in definitions[function].items() if key != "node"} for function in sorted(visited)
    ]
    return {
        "kind": operation["kind"],
        "name": operation["name"],
        "source_files": sorted(set(source_files)),
        "entry_functions": roots,
        "reachable_functions": ordered_functions,
        "direct_call_edges": ordered_edges,
        "callback_edges": ordered_callback_edges,
        "injected_instance_bindings": ordered_injected_bindings,
        "dynamic_dispatch_edges": ordered_registered_edges,
    }


def build_inventory() -> dict:
    closure = worker_source_closure.build_inventory()
    operations = [_operation_graph(operation) for operation in closure["operations"]]
    source_files = {source for operation in operations for source in operation["source_files"]}
    return {
        "version": 1,
        "generated_by": "scripts/worker_function_reachability.py",
        "scope": (
            "Direct statically resolved Python calls, exact keyword-bound class instances passed to statically resolved functions, known services.common.cli.run callbacks, multiprocessing Process(target=local_function) callback edges, and known literal metric-calculator, scheduled-driver, and registered-synthesis-agent dispatches from allowlisted operation "
            "entry functions within their local services.* import closures. Instance method calls are included only when local type "
            "inference resolves every candidate class. This graph remains incomplete: other dynamic dispatch, callbacks, methods on "
            "unknown instances, extension code, and database/provider behavior are not established. It is not an authorization policy "
            "or least-privilege grant list."
        ),
        "summary": {
            "operation_roots": len(operations),
            "source_files": len(source_files),
            "operations_without_resolved_entry_functions": sum(not item["entry_functions"] for item in operations),
            "function_memberships": sum(len(item["reachable_functions"]) for item in operations),
            "direct_call_edges": sum(len(item["direct_call_edges"]) for item in operations),
            "callback_edges": sum(len(item["callback_edges"]) for item in operations),
            "dynamic_dispatch_edges": sum(len(item["dynamic_dispatch_edges"]) for item in operations),
        },
        "operations": operations,
    }


def _serialize(value: dict) -> str:
    return json.dumps(value, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the generated graph")
    group.add_argument("--check", type=Path, help="Fail if the saved graph is stale")
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
        print(f"Missing worker function reachability graph: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Worker function reachability graph is stale: {check}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
