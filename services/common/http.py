"""Shared HTTP client for outbound service calls.

Single place for the timeout/retry behavior that service modules used to
reimplement (or omit) around raw ``requests.*`` calls. Wraps a
:class:`requests.Session` with urllib3 ``Retry`` so transient connection
errors (connect/read timeouts, refused connections) are retried with
exponential backoff, while status codes are left for callers to handle via
``raise_for_status()`` — matching the ``TRANSIENT_EXCEPTIONS`` semantics of
:mod:`services.ingestion.base`.

Usage::

    from services.common.http import http

    resp = http.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Re-exported exception types so callers can catch retryable failures without
# importing `requests` directly (e.g. copernicus_remote_sensing).
Timeout = requests.Timeout
ConnectionError = requests.ConnectionError

DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 1.0


class HttpClient:
    """A session-backed HTTP client with default timeout and retries.

    Per-request kwargs (``timeout``, ``headers``, ``json``, ``params``,
    ``allow_redirects``, ...) pass straight through to requests; any request
    without an explicit ``timeout`` gets :data:`DEFAULT_TIMEOUT`.
    """

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        backoff: float = DEFAULT_BACKOFF,
    ) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=0,  # status retries off: callers decide via raise_for_status
            backoff_factor=backoff,
            allowed_methods=frozenset(
                ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
            ),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.get(url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.post(url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.put(url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.delete(url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.patch(url, **kwargs)

    def close(self) -> None:
        self.session.close()


#: Module-level default client shared by services (connection pooling).
http = HttpClient()


def get(url: str, **kwargs: Any) -> requests.Response:
    return http.get(url, **kwargs)


def post(url: str, **kwargs: Any) -> requests.Response:
    return http.post(url, **kwargs)


def put(url: str, **kwargs: Any) -> requests.Response:
    return http.put(url, **kwargs)


def delete(url: str, **kwargs: Any) -> requests.Response:
    return http.delete(url, **kwargs)


def patch(url: str, **kwargs: Any) -> requests.Response:
    return http.patch(url, **kwargs)
