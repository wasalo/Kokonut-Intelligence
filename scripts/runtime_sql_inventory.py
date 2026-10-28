#!/usr/bin/env python3
"""Inventory direct SQL execution calls across Kokonut service modules.

This report supports review of the shared PostgreSQL runtime role. It records
source locations, statement categories, regex-derived relation candidates, and
hashes for static SQL. It never stores SQL text or runtime parameter values and
must not be treated as an ACL or proof of complete database effects.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.worker_source_closure import build_inventory as build_worker_closure  # noqa: E402
from scripts.worker_sql_inventory import (  # noqa: E402
    EXECUTE_FUNCTIONS,
    EXECUTE_METHODS,
    _query_template,
    _SQLCallVisitor,
    _statement_kind,
    _write_target_relations,
)

_STATEMENT_GROUPS = {
    "read_candidate": {"SELECT"},
    "write_candidate": {"INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE"},
    "schema_change": {"CREATE", "ALTER", "DROP"},
    "transaction_or_session": {"SET", "SAVEPOINT", "ROLLBACK", "RELEASE"},
    "procedure_or_bulk": {"CALL", "COPY", "DO"},
}
_UNRESOLVED_WRITE_KINDS = {"INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "WITH"}
_UNRESOLVED_WRITE_REVIEW_PATH = (
    ROOT / "docs/refactor/runtime-sql-unresolved-write-review.json"
)
# Digest of the grandfathered unresolved-site fingerprint set. The entries are
# tracking exceptions only, not runtime grants or ACL approval. Adding a new
# site to this legacy set requires an intentional source change as well as a
# ledger edit; new reviewed sites belong in the explicit reviewed list.
_LEGACY_UNRESOLVED_WRITE_FINGERPRINTS_SHA256 = (
    "b09fe6be4fb098529d04432be6d0aa12071c3c1dd75423f90e77cde3017b95cf"
)


def _statement_group(statement_kind: str) -> str:
    for group, kinds in _STATEMENT_GROUPS.items():
        if statement_kind in kinds:
            return group
    if statement_kind == "WITH":
        return "with_requires_manual_review"
    return "unknown_requires_manual_review"


def _target_binds_name(target: ast.expr, name: str) -> bool:
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_target_binds_name(element, name) for element in target.elts)
    return False


def _single_local_sql_assignment(
    function: ast.FunctionDef | ast.AsyncFunctionDef | ast.Module,
    name: str,
) -> ast.AST | None:
    """Return one unambiguous local SQL assignment, or leave it unresolved.

    This deliberately does not follow helper calls, parameters, mutations,
    reassignment, loop bindings, or values selected from branches. The value
    itself can contain f-string substitutions; its literal SQL fragments are
    only candidates and dynamic relation identifiers are filtered later.
    """
    if not isinstance(function, ast.Module):
        parameters = [
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        ]
        if function.args.vararg:
            parameters.append(function.args.vararg)
        if function.args.kwarg:
            parameters.append(function.args.kwarg)
        if any(parameter.arg == name for parameter in parameters):
            return None

    assignments: list[ast.AST] = []
    pending = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            return None
        if isinstance(node, ast.Assign) and any(
            _target_binds_name(target, name) for target in node.targets
        ):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                return None
            assignments.append(node.value)
        elif isinstance(node, ast.AnnAssign) and _target_binds_name(node.target, name):
            if not isinstance(node.target, ast.Name) or node.value is None:
                return None
            assignments.append(node.value)
        elif isinstance(node, ast.NamedExpr) and _target_binds_name(node.target, name):
            if not isinstance(node.target, ast.Name):
                return None
            assignments.append(node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)) and _target_binds_name(node.target, name):
            return None
        elif isinstance(node, (ast.With, ast.AsyncWith)) and any(
            item.optional_vars and _target_binds_name(item.optional_vars, name)
            for item in node.items
        ):
            return None
        elif isinstance(node, ast.AugAssign) and _target_binds_name(node.target, name):
            return None
        elif isinstance(node, ast.ExceptHandler) and node.name == name:
            return None
        elif isinstance(node, ast.Delete) and any(
            _target_binds_name(target, name) for target in node.targets
        ):
            return None
        pending.extend(ast.iter_child_nodes(node))

    return assignments[0] if len(assignments) == 1 else None


class _ExecutionQueryContextVisitor(ast.NodeVisitor):
    """Keep local function and query-expression context for execution calls."""

    def __init__(self) -> None:
        self.functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.contexts: dict[tuple[int, int], tuple[ast.FunctionDef | ast.AsyncFunctionDef | None, ast.AST]] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node)
        self.generic_visit(node)
        self.functions.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        method = None
        if isinstance(node.func, ast.Attribute) and node.func.attr in EXECUTE_METHODS:
            method = node.func.attr
        elif isinstance(node.func, ast.Name) and node.func.id in EXECUTE_FUNCTIONS:
            method = node.func.id
        if method:
            if method in EXECUTE_FUNCTIONS and len(node.args) >= 2:
                query_node = node.args[1]
            elif node.args:
                query_node = node.args[0]
            else:
                query_node = ast.Constant(value="")
            function = self.functions[-1] if self.functions else None
            self.contexts[(node.lineno, node.col_offset)] = (function, query_node)
        self.generic_visit(node)


def _candidate_relations_from_template(query: str) -> list[str]:
    """Do not report a truncated identifier next to an f-string placeholder."""
    candidates = []
    for match in re.finditer(
        r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE|REFERENCES|COPY)\s+"
        r'((?:"[^"\n]+"|[A-Za-z_][\w$]*)(?:\s*\.\s*(?:"[^"\n]+"|[A-Za-z_][\w$]*))?)',
        query,
        re.IGNORECASE,
    ):
        # `_query_template` marks each interpolation as `<dynamic>`. If it
        # touches the parsed identifier, the table name may be incomplete
        # (for example `public.{table}` or `{prefix}_event`). Keep the site
        # unresolved rather than inventing a relation candidate.
        suffix = query[match.end():]
        if re.match(r"\s*(?:\.\s*)?<dynamic>", suffix):
            continue
        raw_relation = match.group(1)
        relation = re.sub(r"\s*\.\s*", ".", raw_relation).replace('"', "")
        if '"' not in raw_relation and relation.upper() == "SET":
            # `ON CONFLICT ... DO UPDATE SET` must not be mistaken for the
            # relation following the UPDATE keyword.
            continue
        candidates.append(relation)
    return sorted(set(candidates))


def _stable_ast_dump(node: ast.AST) -> str:
    """Dump an AST without fields added by newer Python grammar versions.

    Python 3.12 added ``type_params`` to function and class AST nodes. The
    empty list changed every unresolved-write fingerprint even though source
    semantics were unchanged. Match Python 3.11's ``ast.dump`` representation
    by omitting only empty ``type_params`` fields while preserving non-empty
    type declarations and the standard dump format.
    """
    def has_empty_type_params(child: ast.AST) -> bool:
        return (
            "type_params" in getattr(child, "_fields", ())
            and getattr(child, "type_params", None) == []
        )

    if (
        "type_params" not in getattr(ast.FunctionDef, "_fields", ())
        and "type_params" not in getattr(node, "_fields", ())
    ):
        return ast.dump(node, annotate_fields=True, include_attributes=False)
    if not any(has_empty_type_params(child) for child in ast.walk(node)):
        return ast.dump(node, annotate_fields=True, include_attributes=False)

    # Work on a copy so the parser tree remains untouched for the scanner.
    stable_node = copy.deepcopy(node)
    for child in ast.walk(stable_node):
        if has_empty_type_params(child):
            delattr(child, "type_params")
    return ast.dump(stable_node, annotate_fields=True, include_attributes=False)


def _write_review_fingerprint(
    source: str,
    site: dict,
    query_expression: ast.AST,
    scope_node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Module,
    occurrence_ordinal: int,
) -> str:
    """Hash source-level SQL identity without storing SQL or runtime values.

    The complete lexical scope AST catches source-level bindings that feed a
    query expression. The ordinal distinguishes repeated calls with identical
    expressions in the same named scope. AST locations are excluded, so line
    moves alone do not change the fingerprint. This cannot capture runtime
    values supplied through parameters, imports, mutable globals, or helpers.
    """
    identity = {
        "source": source,
        "scope": site["scope"],
        "method": site["method"],
        "statement_kind": site["statement_kind"],
        "scope_ast": _stable_ast_dump(scope_node),
        "occurrence_ordinal": occurrence_ordinal,
        "query_expression_ast": _stable_ast_dump(query_expression),
    }
    serialized = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _is_unresolved_write_candidate(site: dict) -> bool:
    """Return true for a direct write or WITH site with no resolved target.

    WITH statements are included conservatively because data-modifying CTEs
    begin with WITH. Read-only CTEs may therefore require a one-time explicit
    review entry. UNKNOWN statements are already grouped for manual review,
    but cannot safely be classified as SQL writes by this narrow gate.
    """
    return (
        site.get("statement_kind") in _UNRESOLVED_WRITE_KINDS
        and not site.get("write_target_relations")
    )


def _scan_source(
    source: str,
    path: Path,
    operation_refs: list[str],
    *,
    include_review_fingerprints: bool = False,
) -> list[dict]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=source)
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise ValueError(f"Unable to parse runtime SQL source {source}") from exc
    visitor = _SQLCallVisitor(
        source, operation_refs, tree, include_write_targets=True
    )
    visitor.visit(tree)
    contexts = _ExecutionQueryContextVisitor()
    contexts.visit(tree)
    occurrence_by_scope: dict[str, int] = defaultdict(int)
    for site in visitor.sites:
        context = contexts.contexts.get((site["line"], site["column"]))
        fingerprint_expression = context[1] if context is not None else None
        scope_node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Module = (
            context[0] if context is not None and context[0] is not None else tree
        )
        if (
            context is not None
            and isinstance(context[1], ast.Name)
        ):
            assignment_scope = context[0] if context[0] is not None else tree
            assigned = _single_local_sql_assignment(assignment_scope, context[1].id)
            if assigned is not None:
                fingerprint_expression = assigned
                query, query_kind = _query_template(assigned)
                # `_query_template` leaves a hole blank for arbitrary string
                # concatenation. Parsing that partial text could mistake a
                # schema prefix for a complete table name, so only literal
                # strings and f-strings with explicit placeholders are safe.
                if query_kind not in {"literal", "fstring"}:
                    site["statement_group"] = _statement_group(site["statement_kind"])
                else:
                    relations = _candidate_relations_from_template(query)
                    statement_kind = _statement_kind(query)
                    if relations or statement_kind != "UNKNOWN":
                        site["candidate_relations"] = sorted(
                            set(site["candidate_relations"]) | set(relations)
                        )
                        if site["statement_kind"] == "UNKNOWN" and statement_kind != "UNKNOWN":
                            site["statement_kind"] = statement_kind
                        write_targets = _write_target_relations(query, site["statement_kind"])
                        site["write_target_relations"] = [
                            relation for relation in write_targets if relation in relations
                        ]
                        site["local_query_resolution"] = "single_local_assignment_template"
        site["statement_group"] = _statement_group(site["statement_kind"])
        if (
            include_review_fingerprints
            and _is_unresolved_write_candidate(site)
            and fingerprint_expression is not None
        ):
            occurrence_by_scope[site["scope"]] += 1
            site["write_review_fingerprint"] = _write_review_fingerprint(
                source,
                site,
                fingerprint_expression,
                scope_node,
                occurrence_by_scope[site["scope"]],
            )
    return visitor.sites


def _review_candidates_from_inventory_source() -> list[dict]:
    """Return unresolved write candidates with stable hashes, no SQL text."""
    return _build_inventory_with_review_candidates()[1]


def _fingerprint_digest(fingerprints: list[str]) -> str:
    serialized = "\n".join(sorted(fingerprints))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _validate_write_review_ledger(
    current_candidates: list[dict],
    ledger: dict,
) -> list[str]:
    """Require every unresolved write candidate to be legacy-tracked or reviewed.

    The legacy fingerprint digest is deliberately pinned in this source file;
    it prevents a new unresolved site from being silently added as a baseline
    exception. Newly accepted entries must carry review status, reviewer, date,
    and rationale in the separate ledger.
    """
    errors: list[str] = []
    if ledger.get("version") != 1:
        return ["unresolved-write review ledger version must be 1"]

    legacy_entries = ledger.get("legacy_unreviewed")
    reviewed_entries = ledger.get("reviewed_sites")
    if not isinstance(legacy_entries, list) or not isinstance(reviewed_entries, list):
        return ["unresolved-write ledger requires legacy_unreviewed and reviewed_sites lists"]

    legacy_fingerprints = [
        entry.get("fingerprint")
        for entry in legacy_entries
        if isinstance(entry, dict)
    ]
    valid_legacy_fingerprints = [
        value
        for value in legacy_fingerprints
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
    ]
    if len(legacy_fingerprints) != len(legacy_entries) or len(
        valid_legacy_fingerprints
    ) != len(legacy_fingerprints):
        errors.append("legacy unresolved-write entries require SHA-256 fingerprints")
    if len(set(valid_legacy_fingerprints)) != len(valid_legacy_fingerprints):
        errors.append("legacy unresolved-write fingerprints must be unique")
    legacy_digest = _fingerprint_digest(valid_legacy_fingerprints)
    if ledger.get("legacy_fingerprint_sha256") != legacy_digest:
        errors.append("legacy unresolved-write manifest fingerprint digest is stale")
    if not _LEGACY_UNRESOLVED_WRITE_FINGERPRINTS_SHA256:
        errors.append("legacy unresolved-write baseline digest must be pinned in source")
    elif (
        legacy_digest != _LEGACY_UNRESOLVED_WRITE_FINGERPRINTS_SHA256
    ):
        errors.append(
            "legacy unresolved-write baseline changed; review the new baseline and update its pinned digest intentionally"
        )
    for index, entry in enumerate(legacy_entries):
        if not isinstance(entry, dict):
            continue
        fingerprint = entry.get("fingerprint")
        if entry.get("review_status") != "preexisting_unreviewed":
            errors.append(
                f"legacy site {fingerprint} must use review_status=preexisting_unreviewed"
            )
        reason = entry.get("reason")
        if not isinstance(reason, str) or "not an acl approval" not in reason.lower():
            errors.append(
                f"legacy site {fingerprint} reason must state that it is not an ACL approval"
            )

    reviewed_fingerprints: list[str] = []
    for index, entry in enumerate(reviewed_entries):
        if not isinstance(entry, dict):
            errors.append(f"reviewed_sites[{index}] must be an object")
            continue
        fingerprint = entry.get("fingerprint")
        if not isinstance(fingerprint, str) or not re.fullmatch(
            r"[0-9a-f]{64}", fingerprint
        ):
            errors.append(f"reviewed_sites[{index}] requires a SHA-256 fingerprint")
            continue
        reviewed_fingerprints.append(fingerprint)
        if entry.get("review_status") != "reviewed_unresolved":
            errors.append(
                f"reviewed site {fingerprint} must use review_status=reviewed_unresolved"
            )
        for field in ("reviewed_by", "reviewed_on", "reason"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"reviewed site {fingerprint} requires {field}")
        if isinstance(entry.get("reviewed_on"), str) and not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", entry["reviewed_on"]
        ):
            errors.append(f"reviewed site {fingerprint} reviewed_on must be YYYY-MM-DD")
        if isinstance(entry.get("reason"), str) and "not an acl approval" not in entry["reason"].lower():
            errors.append(
                f"reviewed site {fingerprint} reason must state that review is not an ACL approval"
            )
    if len(set(reviewed_fingerprints)) != len(reviewed_fingerprints):
        errors.append("reviewed unresolved-write fingerprints must be unique")

    legacy_set = set(valid_legacy_fingerprints)
    reviewed_set = set(reviewed_fingerprints)
    if legacy_set & reviewed_set:
        errors.append("a fingerprint cannot be both legacy-unreviewed and reviewed")
    current_fingerprints = [site["fingerprint"] for site in current_candidates]
    if len(set(current_fingerprints)) != len(current_fingerprints):
        errors.append("current unresolved-write fingerprints must be unique")
    current_by_fingerprint = {
        site["fingerprint"]: site for site in current_candidates
    }
    current_set = set(current_by_fingerprint)
    tracked_set = legacy_set | reviewed_set
    for fingerprint in sorted(current_set - tracked_set):
        site = current_by_fingerprint[fingerprint]
        errors.append(
            "new unresolved SQL write candidate requires explicit review: "
            f"{site['source']}:{site['line']} {site['scope']} "
            f"({site['statement_kind']}, {fingerprint})"
        )
    for fingerprint in sorted(tracked_set - current_set):
        errors.append(
            "tracked unresolved SQL write candidate is stale and must be reconciled: "
            f"{fingerprint}"
        )
    return errors


def check_write_review_ledger(
    current_candidates: list[dict],
    path: Path = _UNRESOLVED_WRITE_REVIEW_PATH,
) -> list[str]:
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [f"unable to read unresolved-write review ledger: {path}"]
    if not isinstance(ledger, dict):
        return ["unresolved-write review ledger must be a JSON object"]
    return _validate_write_review_ledger(current_candidates, ledger)


def _service_package(source: str) -> str:
    parts = source.split("/")
    return parts[1] if len(parts) > 2 and parts[0] == "services" else "<root>"


def _build_inventory_with_review_candidates() -> tuple[dict, list[dict]]:
    services_root = ROOT / "services"
    sources = sorted(services_root.rglob("*.py"))
    closure = build_worker_closure()
    operations_by_source: dict[str, set[str]] = defaultdict(set)
    for operation in closure["operations"]:
        operation_ref = f"{operation['kind']}:{operation['name']}"
        for source in operation["source_files"]:
            operations_by_source[source].add(operation_ref)

    sites = []
    review_candidates = []
    for path in sources:
        source = path.relative_to(ROOT).as_posix()
        source_sites = _scan_source(
            source,
            path,
            sorted(operations_by_source[source]),
            include_review_fingerprints=True,
        )
        for site in source_sites:
            fingerprint = site.pop("write_review_fingerprint", None)
            if fingerprint:
                review_candidates.append(
                    {
                        "fingerprint": fingerprint,
                        "source": site["source"],
                        "line": site["line"],
                        "scope": site["scope"],
                        "method": site["method"],
                        "statement_kind": site["statement_kind"],
                        "expression_kind": site["expression_kind"],
                    }
                )
        sites.extend(source_sites)
    sites.sort(key=lambda item: (item["source"], item["line"], item["column"], item["method"]))

    statement_kinds = Counter(site["statement_kind"] for site in sites)
    expression_kinds = Counter(site["expression_kind"] for site in sites)
    package_sources: dict[str, set[str]] = defaultdict(set)
    for path in sources:
        source = path.relative_to(ROOT).as_posix()
        package_sources[_service_package(source)].add(source)
    package_sites: dict[str, list[dict]] = defaultdict(list)
    for site in sites:
        package_sites[_service_package(site["source"])].append(site)
    service_packages = {}
    for package in sorted(package_sources):
        package_rows = package_sites[package]
        service_packages[package] = {
            "source_files": len(package_sources[package]),
            "execution_sites": len(package_rows),
            "statement_groups": dict(sorted(Counter(
                row["statement_group"] for row in package_rows
            ).items())),
            "candidate_relation_names": len({
                relation for row in package_rows for relation in row["candidate_relations"]
            }),
            "sites_without_relation_candidates": sum(
                not row["candidate_relations"] for row in package_rows
            ),
            "non_literal_sites": sum(row["expression_kind"] != "literal" for row in package_rows),
            "sites_with_worker_operation_refs": sum(bool(row["operation_refs"]) for row in package_rows),
        }

    relations: dict[str, dict] = {}
    relation_sites: dict[str, list[dict]] = defaultdict(list)
    for site in sites:
        for relation in site["candidate_relations"]:
            relation_sites[relation].append(site)
    for relation, relation_rows in sorted(relation_sites.items()):
        relations[relation] = {
            "execution_site_count": len(relation_rows),
            "statement_kinds": sorted({row["statement_kind"] for row in relation_rows}),
            "statement_groups": sorted({row["statement_group"] for row in relation_rows}),
            "source_files": sorted({row["source"] for row in relation_rows}),
        }

    inventory = {
        "version": 2,
        "generated_by": "scripts/runtime_sql_inventory.py",
        "scope": (
            "Direct Python SQL execution calls in services/**/*.py, including API, worker, "
            "and CLI modules. Relation names and simple leading DML targets are regex-derived "
            "candidates, not a parsed SQL AST. A query held in a local variable is resolved only "
            "from one unambiguous local assignment; dynamic table identifiers stay unresolved. "
            "The scan cannot prove query reachability, ORM/extension/external effects, complete "
            "database access, required columns, or authorization. It is not a grant allowlist."
        ),
        "summary": {
            "source_files": len(sources),
            "execution_sites": len(sites),
            "worker_operation_roots": len(closure["operations"]),
            "sites_with_worker_operation_refs": sum(bool(site["operation_refs"]) for site in sites),
            "sites_without_worker_operation_refs": sum(not site["operation_refs"] for site in sites),
            "statement_kinds": dict(sorted(statement_kinds.items())),
            "statement_groups": dict(sorted(Counter(site["statement_group"] for site in sites).items())),
            "expression_kinds": dict(sorted(expression_kinds.items())),
            "relation_candidates": len(relations),
            "write_target_relations": len({
                relation
                for site in sites
                for relation in site.get("write_target_relations", [])
            }),
            "sites_without_relation_candidates": sum(not site["candidate_relations"] for site in sites),
            "service_packages": len(service_packages),
        },
        "service_packages": service_packages,
        "relation_candidates": relations,
        "execution_sites": sites,
    }
    review_candidates.sort(key=lambda item: item["fingerprint"])
    return inventory, review_candidates


def build_inventory() -> dict:
    """Build the existing SQL inventory without adding review-only fields."""
    return _build_inventory_with_review_candidates()[0]


def _serialize(value: dict) -> str:
    relation_candidates = value["relation_candidates"]
    execution_sites = value["execution_sites"]
    header = {key: item for key, item in value.items() if key not in {
        "relation_candidates",
        "execution_sites",
    }}
    serialized_header = json.dumps(header, indent=2)
    records = [
        "  \"relation_candidates\": {",
        ",\n".join(
            "    " + json.dumps(relation) + ": "
            + json.dumps(summary, separators=(",", ": "))
            for relation, summary in relation_candidates.items()
        ),
        "  },",
        "  \"execution_sites\": [",
        ",\n".join(
            "    " + json.dumps(site, separators=(",", ": "))
            for site in execution_sites
        ),
        "  ]",
    ]
    return serialized_header[:-1] + ",\n" + "\n".join(records) + "\n}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write the generated inventory")
    group.add_argument(
        "--check",
        type=Path,
        help="Fail if the saved inventory or unresolved-write review ledger is stale",
    )
    args = parser.parse_args(argv)
    inventory, review_candidates = _build_inventory_with_review_candidates()
    expected = _serialize(inventory)

    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(expected, encoding="utf-8")
        print(f"Wrote runtime SQL inventory: {output.relative_to(ROOT) if output.is_relative_to(ROOT) else output}")
        return 0

    check = args.check if args.check.is_absolute() else ROOT / args.check
    try:
        actual = check.read_text(encoding="utf-8")
    except OSError:
        print(f"Missing runtime SQL inventory: {check}", file=sys.stderr)
        return 1
    if actual != expected:
        print(f"Runtime SQL inventory is stale: {check}", file=sys.stderr)
        return 1
    review_errors = check_write_review_ledger(review_candidates)
    if review_errors:
        print("Unresolved SQL write review ledger is stale:", file=sys.stderr)
        for error in review_errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Runtime SQL inventory is current: {check.relative_to(ROOT) if check.is_relative_to(ROOT) else check}")
    print(
        "Unresolved SQL write review ledger is current: "
        f"{_UNRESOLVED_WRITE_REVIEW_PATH.relative_to(ROOT)} "
        f"({len(review_candidates)} tracked candidates; ledger entries do not imply ACL approval)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
