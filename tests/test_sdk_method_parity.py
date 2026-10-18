"""Keep the Python and TypeScript SDK convenience-method surfaces aligned."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _camel_case(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.title() for part in tail)


def _python_method_signatures() -> dict[str, dict[str, tuple[bool, ...]]]:
    tree = ast.parse((ROOT / "sdk/python/kokonut/methods.py").read_text(encoding="utf-8"))
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    inventory: dict[str, dict[str, tuple[bool, ...]]] = {}
    for name, node in classes.items():
        methods: dict[str, tuple[bool, ...]] = {}
        for member in node.body:
            if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) or member.name.startswith("_"):
                continue
            positional = member.args.posonlyargs + member.args.args
            if member.args.args and member.args.args[0].arg in {"self", "cls"}:
                positional = positional[1:]
            required = len(positional) - len(member.args.defaults)
            methods[_camel_case(member.name)] = tuple(
                index >= required for index in range(len(positional))
            )

        if name != "GenericMethods" and any(
            isinstance(base, ast.Name) and base.id == "GenericMethods" for base in node.bases
        ):
            inherited = inventory["GenericMethods"].copy()
            inherited.update(methods)
            methods = inherited
        inventory[name] = methods
    return inventory


def _split_typescript_parameters(parameters: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(parameters):
        if char in "<[{(":
            depth += 1
        elif char in ">]})":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(parameters[start:index].strip())
            start = index + 1
    final = parameters[start:].strip()
    if final:
        result.append(final)
    return result


def _typescript_parameter_is_optional(parameter: str) -> bool:
    match = re.match(r"\s*(?:\.\.\.)?[A-Za-z_$][\w$]*(\?)?\s*(?::|=)", parameter)
    if match is None:
        raise AssertionError(f"Could not parse TypeScript SDK parameter: {parameter!r}")
    return bool(match.group(1)) or "=" in parameter.split(":", 1)[0]


def _typescript_method_signatures() -> dict[str, dict[str, set[tuple[bool, ...]]]]:
    source = (ROOT / "sdk/javascript/src/methods.ts").read_text(encoding="utf-8")
    declarations = re.finditer(
        r"export interface (?P<name>[A-Za-z_]\w*Methods)"
        r"(?P<extends>\s+extends\s+GenericMethods)?\s*\{",
        source,
    )
    inventory: dict[str, dict[str, set[tuple[bool, ...]]]] = {}
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
        methods: dict[str, set[tuple[bool, ...]]] = {}
        for method in re.finditer(r"^\s*([A-Za-z_]\w*)\s*\(", body, re.MULTILINE):
            parameter_start = method.end()
            depth = 1
            parameter_end = parameter_start
            while parameter_end < len(body) and depth:
                if body[parameter_end] == "(":
                    depth += 1
                elif body[parameter_end] == ")":
                    depth -= 1
                parameter_end += 1
            if depth:
                raise AssertionError(f"Unclosed TypeScript method signature {method.group(1)}")

            parameters = _split_typescript_parameters(body[parameter_start : parameter_end - 1])
            shape = tuple(_typescript_parameter_is_optional(parameter) for parameter in parameters)
            methods.setdefault(method.group(1), set()).add(shape)

        name = declaration.group("name")
        if declaration.group("extends"):
            inherited = {key: value.copy() for key, value in inventory["GenericMethods"].items()}
            inherited.update(methods)
            methods = inherited
        inventory[name] = methods
    return inventory


def test_python_and_typescript_sdk_method_names_match():
    python_methods = _python_method_signatures()
    typescript_methods = _typescript_method_signatures()

    assert python_methods.keys() == typescript_methods.keys()
    for name in sorted(python_methods):
        assert python_methods[name].keys() == typescript_methods[name].keys(), (
            f"{name} method mismatch: Python-only="
            f"{sorted(python_methods[name].keys() - typescript_methods[name].keys())}, "
            f"TypeScript-only={sorted(typescript_methods[name].keys() - python_methods[name].keys())}"
        )


def test_typescript_preserves_python_method_argument_optionality():
    python_methods = _python_method_signatures()
    typescript_methods = _typescript_method_signatures()

    for group, methods in python_methods.items():
        for method, python_shape in methods.items():
            typescript_shapes = typescript_methods[group][method]
            assert python_shape in typescript_shapes, (
                f"{group}.{method} argument optionality mismatch: Python={python_shape}, "
                f"TypeScript overloads={sorted(typescript_shapes)}"
            )
