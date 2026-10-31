#!/usr/bin/env python3
"""Print the Gateway's versioned public API OpenAPI subset as JSON.

Run this with the Gateway runtime dependencies installed, for example:

    python3 -m scripts.export_public_api_openapi > docs/refactor/native-public-api-v1.openapi.json
"""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import FastAPI

from services.gateway.router import get_route_policy, router

_COMPONENT_REF = re.compile(r"^#/components/([^/]+)/(.+)$")


def _references(value: Any):
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str):
            match = _COMPONENT_REF.match(reference)
            if match:
                yield match.group(1), match.group(2).replace("~1", "/").replace("~0", "~")
        for child in value.values():
            yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def build_public_api_spec() -> dict[str, Any]:
    app = FastAPI(
        title="Kokonut Intelligence Gateway",
        version="1.0.0",
        description="Versioned public read contract for the Kokonut Gateway.",
    )
    app.include_router(router, prefix="/api")
    source = app.openapi()
    paths: dict[str, dict[str, Any]] = {}
    for path, operations in source.get("paths", {}).items():
        if path != "/api/v1" and not path.startswith("/api/v1/"):
            continue
        policy_path = re.sub(r"\{[^/]+\}", "00000000-0000-0000-0000-000000000000", path)
        for method, operation in operations.items():
            policy = get_route_policy(method.upper(), policy_path)
            if not policy["public"]:
                continue
            if method.lower() != "get" or policy["action"] != "read":
                raise ValueError(
                    f"Public API snapshot supports public reads only: {method.upper()} {path}"
                )
            operation["x-kokonut-policy"] = {
                "resource": policy["resource"],
                "action": policy["action"],
                "public": policy["public"],
                "location_scoped": policy["location_id"] is not None,
            }
            paths.setdefault(path, {})[method] = operation

    source_components = source.get("components", {})
    components: dict[str, dict[str, Any]] = {}
    pending = list(_references(paths))
    visited: set[tuple[str, str]] = set()
    while pending:
        section, name = pending.pop()
        key = (section, name)
        if key in visited:
            continue
        visited.add(key)
        item = source_components.get(section, {}).get(name)
        if item is None:
            continue
        components.setdefault(section, {})[name] = item
        pending.extend(_references(item))

    spec = {
        "openapi": source["openapi"],
        "info": source["info"],
        "paths": paths,
    }
    if components:
        spec["components"] = components
    if "servers" in source:
        spec["servers"] = source["servers"]
    return spec


if __name__ == "__main__":
    print(json.dumps(build_public_api_spec(), indent=2, sort_keys=True))
