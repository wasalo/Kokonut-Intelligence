"""Focused authorization coverage for location-scoped credit gRPC writes."""

from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import grpc
import pytest

LOCATION_ID = "a4b1b9e3-4d44-4df3-8d13-539c6cb2a5f0"
CREDENTIAL_HASH = "a" * 64


@pytest.fixture
def service_pb2(tmp_path, monkeypatch):
    from grpc_tools import protoc

    repository_root = Path(__file__).parents[1]
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    proto_sources = (
        "proto/common/pagination.proto",
        "proto/ecocredit/v1/types.proto",
        "proto/ecocredit/v1/service.proto",
    )
    assert protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{repository_root / 'proto'}",
            f"--python_out={generated_root}",
            *(str(repository_root / source) for source in proto_sources),
        ]
    ) == 0
    for package in ("common", "ecocredit", "ecocredit/v1"):
        package_dir = generated_root / package
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").touch()
    monkeypatch.syspath_prepend(str(generated_root))
    grpc_package = importlib.import_module("services.grpc")
    monkeypatch.setattr(grpc_package, "__path__", [*grpc_package.__path__, str(generated_root)])
    initial_modules = set(sys.modules)
    yield importlib.import_module("services.grpc.ecocredit.v1.service_pb2")
    for name in set(sys.modules) - initial_modules:
        if name == "common" or name.startswith(("common.", "ecocredit.", "services.grpc.ecocredit")):
            sys.modules.pop(name, None)


def _auth_context(*scopes: str, credential_hash: str = CREDENTIAL_HASH):
    from services.grpc.auth import grpc_auth_context

    return grpc_auth_context.set(
        {
            "api_key_id": "key-1",
            "credential_hash": credential_hash,
            "role_name": "operator",
            "scopes": list(scopes),
        }
    )


def test_interceptor_propagates_only_hash_into_handler_context():
    from services.grpc.auth import APIKeyInterceptor, get_current_auth

    raw_key = "synthetic-credit-client-key"
    db_connection = MagicMock()
    db_factory = MagicMock(return_value=db_connection)
    db_factory.release = MagicMock()
    db_connection.execute.return_value.mappings.return_value.first.return_value = {
        "id": "key-1",
        "is_active": True,
        "expires_at": None,
        "scopes": [f"ecocredit_batch:create:{LOCATION_ID}"],
        "role_name": "operator",
        "permissions": {},
    }
    observed = []
    original_handler = grpc.unary_unary_rpc_method_handler(
        lambda request, context: observed.append(get_current_auth())
    )
    details = SimpleNamespace(
        method="ecocredit.v1.EcocreditService/CreateBatch",
        invocation_metadata=(("x-api-key", raw_key),),
    )

    wrapped = APIKeyInterceptor(db_factory).intercept_service(
        lambda _details: original_handler,
        details,
    )
    wrapped.unary_unary(None, MagicMock())

    assert observed[0]["credential_hash"] == hashlib.sha256(raw_key.encode()).hexdigest()
    assert raw_key not in repr(observed[0])
    db_factory.release.assert_called_once_with(db_connection)


def test_location_scope_normalizes_uuid_and_returns_key_hash():
    from services.grpc.auth import require_location_scope

    token = _auth_context(f"ecocredit_batch:create:{LOCATION_ID}")
    try:
        context = MagicMock()
        normalized, credential_hash = require_location_scope(
            context,
            resource="ecocredit_batch",
            action="create",
            location_id=LOCATION_ID.upper(),
        )
        assert normalized == str(UUID(LOCATION_ID))
        assert credential_hash == CREDENTIAL_HASH
        context.abort.assert_not_called()
    finally:
        from services.grpc.auth import grpc_auth_context

        grpc_auth_context.reset(token)


@pytest.mark.parametrize(
    "scope",
    [
        "ecocredit_batch:create",
        "ecocredit_batch:create:*",
        "*:*:*",
        f"ecocredit_batch:create:{'b' * 8}",
    ],
)
def test_global_wildcard_or_other_location_scope_fails_closed(scope):
    from services.grpc.auth import require_location_scope

    token = _auth_context(scope)
    try:
        context = MagicMock()
        context.abort.side_effect = grpc.RpcError()
        with pytest.raises(grpc.RpcError):
            require_location_scope(
                context,
                resource="ecocredit_batch",
                action="create",
                location_id=LOCATION_ID,
            )
        context.abort.assert_called_once_with(
            grpc.StatusCode.PERMISSION_DENIED,
            "Location-scoped grant 'ecocredit_batch:create' required",
        )
    finally:
        from services.grpc.auth import grpc_auth_context

        grpc_auth_context.reset(token)


def test_location_scope_rejects_invalid_uuid_before_connection_access():
    from services.grpc.auth import require_location_scope

    token = _auth_context("ecocredit_batch:create:not-a-uuid")
    try:
        context = MagicMock()
        context.abort.side_effect = grpc.RpcError()
        with pytest.raises(grpc.RpcError):
            require_location_scope(
                context,
                resource="ecocredit_batch",
                action="create",
                location_id="not-a-uuid",
            )
        context.abort.assert_called_once_with(grpc.StatusCode.INVALID_ARGUMENT, "location_id must be a UUID")
    finally:
        from services.grpc.auth import grpc_auth_context

        grpc_auth_context.reset(token)


@pytest.mark.parametrize(
    ("method_name", "resource", "action", "request_name", "service_module", "service_function", "response_id"),
    [
        (
            "CreateBatch",
            "ecocredit_batch",
            "create",
            "CreateBatchRequest",
            "services.credit_class.batch_manager",
            "create_batch",
            "batch_id",
        ),
        (
            "ApplyToClass",
            "ecocredit_enrollment",
            "apply",
            "ApplyToClassRequest",
            "services.credit_class.enrollment",
            "apply_to_class",
            "enrollment_id",
        ),
    ],
)
def test_scoped_mutation_checks_grant_before_connection_and_context_before_write(
    monkeypatch,
    service_pb2,
    method_name,
    resource,
    action,
    request_name,
    service_module,
    service_function,
    response_id,
):
    from services.grpc import credit_class_service
    from services.grpc.auth import grpc_auth_context
    events = []
    connection = MagicMock()
    connection_factory = MagicMock(return_value=connection)
    connection_factory.release = MagicMock()
    domain_write = MagicMock(return_value={"id": "created-1", "batch_code": "B-1"})
    monkeypatch.setattr(importlib.import_module(service_module), service_function, domain_write)
    monkeypatch.setattr(
        credit_class_service,
        "set_location_tenant_context",
        lambda context, conn, **kwargs: events.append(("context", conn, kwargs)),
    )
    def record_write(*args, **kwargs):
        events.append(("write", args[0], kwargs))
        if response_id == "enrollment_id":
            return {"id": "created-1", "status": "submitted"}
        return {"id": "created-1", "batch_code": "B-1"}

    domain_write.side_effect = record_write
    token = grpc_auth_context.set(
        {
            "api_key_id": "key-1",
            "credential_hash": CREDENTIAL_HASH,
            "role_name": "operator",
            "scopes": [f"{resource}:{action}:{LOCATION_ID}"],
        }
    )
    try:
        request_class = getattr(service_pb2, request_name)
        request = request_class(location_id=LOCATION_ID)
        if request_name == "CreateBatchRequest":
            request.credit_class_id = "class-1"
            request.vintage_year = 2026
            request.total_quantity = 2
        else:
            request.credit_class_id = "class-1"
        context = MagicMock()

        response = getattr(credit_class_service.EcocreditServiceServicer(connection_factory), method_name)(
            request,
            context,
        )

        assert getattr(response, response_id) == "created-1"
        assert [event[0] for event in events] == ["context", "write"]
        assert events[0][1] is connection
        assert events[0][2] == {
            "resource": resource,
            "action": action,
            "location_id": LOCATION_ID,
            "credential_hash": CREDENTIAL_HASH,
        }
        assert events[1][1] is connection
        assert events[1][2]["location_id"] == LOCATION_ID
        connection_factory.release.assert_called_once_with(connection)
    finally:
        grpc_auth_context.reset(token)


@pytest.mark.parametrize(
    ("method_name", "request_name", "old_scope"),
    [
        ("CreateBatch", "CreateBatchRequest", "ecocredit:batch:write"),
        ("ApplyToClass", "ApplyToClassRequest", "ecocredit:class:write"),
    ],
)
def test_legacy_global_mutation_scope_is_rejected_before_connection(
    service_pb2,
    method_name,
    request_name,
    old_scope,
):
    from services.grpc import credit_class_service
    from services.grpc.auth import grpc_auth_context
    connection_factory = MagicMock()
    connection_factory.release = MagicMock()
    token = grpc_auth_context.set(
        {
            "api_key_id": "key-1",
            "credential_hash": CREDENTIAL_HASH,
            "role_name": "operator",
            "scopes": [old_scope],
        }
    )
    try:
        context = MagicMock()
        context.abort.side_effect = grpc.RpcError()
        request = getattr(service_pb2, request_name)(location_id=LOCATION_ID)
        with pytest.raises(grpc.RpcError):
            getattr(credit_class_service.EcocreditServiceServicer(connection_factory), method_name)(request, context)
        context.abort.assert_called_once_with(
            grpc.StatusCode.PERMISSION_DENIED,
            f"Location-scoped grant '{'ecocredit_batch:create' if method_name == 'CreateBatch' else 'ecocredit_enrollment:apply'}' required",
        )
        connection_factory.assert_not_called()
    finally:
        grpc_auth_context.reset(token)


def test_database_scope_denial_is_sanitized_as_permission_denied(monkeypatch):
    from services.common.tenant_context import TenantContextDenied
    from services.grpc import auth

    setter = MagicMock(side_effect=TenantContextDenied("private denial detail"))
    monkeypatch.setattr("services.common.tenant_context.set_gateway_tenant_context", setter)
    context = MagicMock()
    context.abort.side_effect = grpc.RpcError()

    with pytest.raises(grpc.RpcError):
        auth.set_location_tenant_context(
            context,
            MagicMock(),
            resource="ecocredit_batch",
            action="create",
            location_id=LOCATION_ID,
            credential_hash=CREDENTIAL_HASH,
        )

    setter.assert_called_once()
    assert "private denial detail" not in context.abort.call_args.args[1]
    assert context.abort.call_args.args == (
        grpc.StatusCode.PERMISSION_DENIED,
        "Location-scoped API-key grant is no longer active",
    )
