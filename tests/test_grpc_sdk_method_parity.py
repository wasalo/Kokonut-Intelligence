"""Keep the TypeScript gRPC wrappers aligned with every public proto RPC."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICE_CONTRACTS = (
    (
        "DataService",
        ROOT / "proto/data/v1/service.proto",
        ROOT / "sdk/typescript/src/services/data-service.ts",
    ),
    (
        "EcocreditService",
        ROOT / "proto/ecocredit/v1/service.proto",
        ROOT / "sdk/typescript/src/services/ecocredit-service.ts",
    ),
)


def _proto_rpc_names(proto_path: Path) -> list[str]:
    return re.findall(r"\brpc\s+([A-Za-z_]\w*)\s*\(", proto_path.read_text())


def _typescript_rpc_wrappers(client_path: Path) -> list[str]:
    source = client_path.read_text()
    return [
        *re.findall(r'_call\("([A-Za-z_]\w*)"', source),
        *re.findall(r"\(this\.client as any\)\.([A-Za-z_]\w*)", source),
    ]


@pytest.mark.parametrize("service,proto_path,client_path", SERVICE_CONTRACTS)
def test_typescript_client_wraps_each_proto_rpc_exactly_once(
    service: str, proto_path: Path, client_path: Path
) -> None:
    proto_methods = _proto_rpc_names(proto_path)
    client_methods = _typescript_rpc_wrappers(client_path)

    assert len(proto_methods) == len(set(proto_methods)), f"{service} proto has duplicate RPC names"
    assert len(client_methods) == len(set(client_methods)), f"{service} SDK wraps an RPC more than once"
    assert set(client_methods) == set(proto_methods), (
        f"{service} SDK method mismatch: missing={sorted(set(proto_methods) - set(client_methods))}, "
        f"extra={sorted(set(client_methods) - set(proto_methods))}"
    )
