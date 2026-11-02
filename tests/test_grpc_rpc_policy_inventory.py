"""Pin gRPC protobuf methods to reviewed authorization policies."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SERVICES = {
    "data.v1.DataService": {
        "proto": ROOT / "proto/data/v1/service.proto",
        "implementation": ROOT / "services/grpc/data_service.py",
        "class_name": "DataServiceServicer",
        "policies": {
            "GenerateIRI": "iri_registry:write",
            "ResolveIRI": "iri_registry:read",
            "GetVersionHistory": "iri_registry:read",
            "ComputeContentHash": "public",
            "CreateContentHash": "data_stream:write",
            "FindIRIByHash": "data_stream:read",
            "DefineResolver": "data_stream:write",
            "RegisterToResolver": "data_stream:write",
            "GetResolversForIRI": "data_stream:read",
            "ListResolvers": "data_stream:read",
            "AttestToIRI": "data_stream:write",
            "GetAttestorsForIRI": "data_stream:read",
            "StreamNewIRIs": "iri_registry:read",
        },
    },
    "ecocredit.v1.EcocreditService": {
        "proto": ROOT / "proto/ecocredit/v1/service.proto",
        "implementation": ROOT / "services/grpc/credit_class_service.py",
        "class_name": "EcocreditServiceServicer",
        "policies": {
            "Classes": "ecocredit:class:read",
            "Class": "ecocredit:class:read",
            "ClassesByAdmin": "ecocredit:class:read",
            "ClassIssuers": "ecocredit:class:read",
            "CreateClass": "ecocredit:class:write",
            "UpdateClass": "ecocredit:class:write",
            "Projects": "ecocredit:project:read",
            "Project": "ecocredit:project:read",
            "ProjectsByClass": "ecocredit:project:read",
            "Batches": "ecocredit:batch:read",
            "Batch": "ecocredit:batch:read",
            "BatchesByClass": "ecocredit:batch:read",
            "BatchesByProject": "ecocredit:batch:read",
            "CreateBatch": "location:ecocredit_batch:create",
            "Balance": "ecocredit:balance:read",
            "Balances": "ecocredit:balance:read",
            "BalancesByBatch": "ecocredit:balance:read",
            "Supply": "ecocredit:batch:read",
            "StreamBalances": "ecocredit:balance:read",
            "StreamBatchUpdates": "ecocredit:batch:read",
            "Baskets": "ecocredit:basket:read",
            "Basket": "ecocredit:basket:read",
            "CreateBasket": "ecocredit:basket:write",
            "PutInBasket": "ecocredit:basket:write",
            "TakeFromBasket": "ecocredit:basket:write",
            "SellOrders": "marketplace:read",
            "SellOrder": "marketplace:read",
            "CreateSellOrder": "marketplace:write",
            "UpdateSellOrder": "marketplace:write",
            "CancelSellOrder": "marketplace:write",
            "CreateBuyOrder": "marketplace:write",
            "ExecuteBuyOrder": "marketplace:write",
            "StreamSellOrders": "marketplace:read",
            "AllowedDenoms": "marketplace:read",
            "GetFeeParams": "marketplace:read",
            "BridgeOut": "ecocredit:bridge:write",
            "BridgeIn": "ecocredit:bridge:write",
            "BridgeComplete": "ecocredit:bridge:write",
            "ApplyToClass": "location:ecocredit_enrollment:apply",
            "EvaluateApplication": "ecocredit:class:write",
            "ListEnrollments": "ecocredit:class:read",
            "CreditTypes": "ecocredit:class:read",
        },
    },
}


def _rpc_methods(proto_path: Path) -> set[str]:
    return set(re.findall(r"^\s*rpc\s+(\w+)\s*\(", proto_path.read_text(), re.MULTILINE))


def _service_method_nodes(source_path: Path, class_name: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(source_path.read_text(), filename=str(source_path))
    service = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    return {node.name: node for node in service.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _method_policy(method: ast.FunctionDef) -> tuple[str, int] | None:
    calls = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"require_scope", "require_location_scope"}
    ]
    assert len(calls) <= 1, f"{method.name} must have at most one scope declaration"
    if not calls:
        return None
    call = calls[0]
    if call.func.id == "require_location_scope":
        resource = next(keyword.value for keyword in call.keywords if keyword.arg == "resource")
        action = next(keyword.value for keyword in call.keywords if keyword.arg == "action")
        assert isinstance(resource, ast.Constant) and isinstance(resource.value, str)
        assert isinstance(action, ast.Constant) and isinstance(action.value, str)
        return f"location:{resource.value}:{action.value}", call.lineno
    resource, action = call.args[1:3]
    assert isinstance(resource, ast.Constant) and isinstance(resource.value, str)
    assert isinstance(action, ast.Constant) and isinstance(action.value, str)
    return f"{resource.value}:{action.value}", call.lineno


def _connection_acquisition_lines(method: ast.FunctionDef) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"_get_conn", "_db_factory"}
    ]


def test_proto_rpc_methods_match_reviewed_policy_and_handler_inventory():
    for service_name, contract in SERVICES.items():
        expected = contract["policies"]
        rpc_methods = _rpc_methods(contract["proto"])
        assert rpc_methods == set(expected), f"{service_name}: protobuf policy inventory drift"

        implementations = _service_method_nodes(contract["implementation"], contract["class_name"])
        methods = {name: implementations[name] for name in rpc_methods if name in implementations}
        assert set(methods) == rpc_methods, f"{service_name}: missing RPC implementation"

        for name, method in methods.items():
            policy = _method_policy(method)
            if expected[name] == "public":
                assert policy is None, f"{service_name}/{name} must remain database-free and public"
                assert not _connection_acquisition_lines(method), (
                    f"{service_name}/{name} is public and must not acquire a database connection"
                )
                continue

            assert policy is not None, f"{service_name}/{name} is missing its scope check"
            scope, guard_line = policy
            assert scope == expected[name], f"{service_name}/{name} scope policy changed"
            connection_lines = _connection_acquisition_lines(method)
            assert connection_lines, f"{service_name}/{name} has no reviewed database acquisition"
            assert guard_line < min(connection_lines), (
                f"{service_name}/{name} must check scope before acquiring a database connection"
            )
