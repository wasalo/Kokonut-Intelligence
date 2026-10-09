"""Tests for the shared HTTP client (services.common.http)."""

from __future__ import annotations

from unittest import mock

from services.common import http as http_module
from services.common.http import HttpClient


def test_get_defaults_timeout():
    client = HttpClient(timeout=7)
    session = mock.Mock()
    client.session = session
    client.get("https://example.com", params={"a": 1})
    session.get.assert_called_once_with("https://example.com", timeout=7, params={"a": 1})


def test_post_passes_through_kwargs_and_default_timeout():
    client = HttpClient(timeout=11)
    session = mock.Mock()
    client.session = session
    client.post("https://example.com", json={"x": 1}, headers={"A": "b"})
    session.post.assert_called_once_with(
        "https://example.com", timeout=11, json={"x": 1}, headers={"A": "b"}
    )


def test_explicit_timeout_overrides_default():
    client = HttpClient(timeout=30)
    session = mock.Mock()
    client.session = session
    client.get("https://example.com", timeout=5)
    session.get.assert_called_once_with("https://example.com", timeout=5)


def test_http_session_has_retrying_adapter():
    client = HttpClient(retries=3)
    adapter = client.session.get_adapter("https://example.com")
    assert adapter.max_retries.total == 3
    assert adapter.max_retries.backoff_factor == 1.0


def test_module_level_functions_delegate():
    with mock.patch.object(http_module, "http") as fake:
        http_module.get("u", params={"q": 1})
        fake.get.assert_called_once_with("u", params={"q": 1})
