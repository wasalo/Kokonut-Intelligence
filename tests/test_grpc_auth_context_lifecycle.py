"""Ensure gRPC identity context is scoped to each handler invocation."""

from __future__ import annotations

from unittest.mock import MagicMock

import grpc
import pytest

from services.grpc.auth import _authenticated_handler, get_current_auth

AUTH = {"api_key_id": "key-1", "role_name": "operator", "scopes": ["data_stream:read"]}


def test_unary_handler_context_is_reset_after_return():
    observed = []

    def behavior(request, context):
        observed.append(get_current_auth())
        return "response"

    handler = grpc.unary_unary_rpc_method_handler(behavior)
    wrapped = _authenticated_handler(handler, AUTH)

    assert get_current_auth() is None
    assert wrapped.unary_unary("request", MagicMock()) == "response"
    assert observed == [AUTH]
    assert get_current_auth() is None


def test_streaming_response_context_is_reset_before_each_yield_and_on_cancel():
    observed = []
    closed = []

    def behavior(request, context):
        try:
            for value in ("one", "two"):
                observed.append((value, get_current_auth()))
                yield value
        finally:
            closed.append(get_current_auth())

    handler = grpc.unary_stream_rpc_method_handler(behavior)
    wrapped = _authenticated_handler(handler, AUTH)
    responses = iter(wrapped.unary_stream("request", MagicMock()))

    assert get_current_auth() is None
    assert next(responses) == "one"
    assert get_current_auth() is None
    responses.close()
    assert observed == [("one", AUTH)]
    assert closed == [AUTH]
    assert get_current_auth() is None


def test_bidirectional_stream_context_is_reset_between_messages():
    observed = []

    def behavior(requests, context):
        for request in requests:
            observed.append((request, get_current_auth()))
            yield f"response:{request}"

    handler = grpc.stream_stream_rpc_method_handler(behavior)
    wrapped = _authenticated_handler(handler, AUTH)
    responses = iter(wrapped.stream_stream(iter(("one", "two")), MagicMock()))

    assert get_current_auth() is None
    assert next(responses) == "response:one"
    assert get_current_auth() is None
    assert next(responses) == "response:two"
    assert get_current_auth() is None
    with pytest.raises(StopIteration):
        next(responses)
    assert observed == [("one", AUTH), ("two", AUTH)]
    assert get_current_auth() is None


def test_client_streaming_unary_context_is_reset_after_response():
    observed = []

    def behavior(requests, context):
        values = list(requests)
        observed.append((values, get_current_auth()))
        return len(values)

    handler = grpc.stream_unary_rpc_method_handler(behavior)
    wrapped = _authenticated_handler(handler, AUTH)

    assert wrapped.stream_unary(iter(("one", "two")), MagicMock()) == 2
    assert observed == [(["one", "two"], AUTH)]
    assert get_current_auth() is None


def test_streaming_context_is_reset_when_handler_raises():
    def behavior(request, context):
        assert get_current_auth() == AUTH
        yield "first"
        raise ValueError("stream failed")

    handler = grpc.unary_stream_rpc_method_handler(behavior)
    wrapped = _authenticated_handler(handler, AUTH)
    responses = iter(wrapped.unary_stream("request", MagicMock()))

    assert next(responses) == "first"
    assert get_current_auth() is None
    with pytest.raises(ValueError, match="stream failed"):
        next(responses)
    assert get_current_auth() is None
