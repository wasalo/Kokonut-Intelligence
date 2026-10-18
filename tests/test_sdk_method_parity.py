"""Keep the Python and TypeScript SDK convenience-method surfaces aligned."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _camel_case(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.title() for part in tail)


def _python_method_inventory() -> dict[str, set[str]]:
    tree = ast.parse((ROOT / "sdk/python/kokonut/methods.py").read_text(encoding="utf-8"))
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    inventory: dict[str, set[str]] = {}
    for name, node in classes.items():
        methods = {
            _camel_case(member.name)
            for member in node.body
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not member.name.startswith("_")
        }
        if name != "GenericMethods" and any(
            isinstance(base, ast.Name) and base.id == "GenericMethods" for base in node.bases
        ):
            methods.update(inventory["GenericMethods"])
        inventory[name] = methods
    return inventory


def _typescript_method_inventory() -> dict[str, set[str]]:
    source = (ROOT / "sdk/javascript/src/methods.ts").read_text(encoding="utf-8")
    declarations = re.finditer(
        r"export interface (?P<name>[A-Za-z_]\w*Methods)"
        r"(?P<extends>\s+extends\s+GenericMethods)?\s*\{",
        source,
    )
    inventory: dict[str, set[str]] = {}
    for declaration in declarations:
        depth = 0
        end = declaration.end() - 1
        for end in range(end, len(source)):
            if source[end] == "{":
                depth += 1
            elif source[end] == "}":
                depth -= 1
                if depth == 0:
                    break
        else:
            raise AssertionError(f"Unclosed TypeScript interface {declaration.group('name')}")

        body = source[declaration.end() : end]
        methods = set(re.findall(r"^\s*([A-Za-z_]\w*)\s*\(", body, re.MULTILINE))
        name = declaration.group("name")
        if declaration.group("extends"):
            methods.update(inventory["GenericMethods"])
        inventory[name] = methods
    return inventory


def test_python_and_typescript_sdk_method_names_match():
    python_methods = _python_method_inventory()
    typescript_methods = _typescript_method_inventory()

    assert python_methods.keys() == typescript_methods.keys()
    for name in sorted(python_methods):
        assert python_methods[name] == typescript_methods[name], (
            f"{name} method mismatch: Python-only="
            f"{sorted(python_methods[name] - typescript_methods[name])}, "
            f"TypeScript-only={sorted(typescript_methods[name] - python_methods[name])}"
        )
