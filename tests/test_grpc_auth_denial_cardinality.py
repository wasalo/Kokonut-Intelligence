"""Authentication denials preserve the registered gRPC method shape."""

from unittest.mock import MagicMock

import grpc
import pytest

from services.grpc.auth import APIKeyInterceptor


class _AbortCalled(Exception):
    pass


@pytest.mark.parametrize(
    ("request_streaming", "response_streaming", "builder_name", "behavior_name"),
    [
        (False, False, "unary_unary_rpc_method_handler", "unary_unary"),
        (False, True, "unary_stream_rpc_method_handler", "unary_stream"),
        (True, False, "stream_unary_rpc_method_handler", "stream_unary"),
        (True, True, "stream_stream_rpc_method_handler", "stream_stream"),
    ],
)
def test_missing_key_denial_preserves_rpc_cardinality(
    request_streaming, response_streaming, builder_name, behavior_name
):
    def request_deserializer(payload):
        return payload

    def response_serializer(payload):
        return payload

    registered = getattr(grpc, builder_name)(
        lambda request, context: iter(()) if response_streaming else None,
        request_deserializer=request_deserializer,
        response_serializer=response_serializer,
    )
    continuation = MagicMock(return_value=registered)
    database_factory = MagicMock()
    interceptor = APIKeyInterceptor(database_factory)
    details = MagicMock(
        method="/example.v1.Service/Stream",
        invocation_metadata=[],
    )

    denied = interceptor.intercept_service(continuation, details)

    continuation.assert_called_once_with(details)
    database_factory.assert_not_called()
    assert denied.request_streaming is request_streaming
    assert denied.response_streaming is response_streaming
    assert denied.request_deserializer is request_deserializer
    assert denied.response_serializer is response_serializer

    context = MagicMock()
    context.abort.side_effect = _AbortCalled
    request = iter(()) if request_streaming else object()
    behavior = getattr(denied, behavior_name)

    if response_streaming:
        with pytest.raises(_AbortCalled):
            next(iter(behavior(request, context)))
    else:
        with pytest.raises(_AbortCalled):
            behavior(request, context)

    context.abort.assert_called_once_with(
        grpc.StatusCode.UNAUTHENTICATED,
        "Missing x-api-key metadata",
    )
