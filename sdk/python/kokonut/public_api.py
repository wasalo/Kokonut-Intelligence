"""Typed client for the versioned native Kokonut public API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional
from urllib.parse import quote

import requests


@dataclass(frozen=True)
class PublicLocation:
    id: str
    name: str
    country: Optional[str]
    region: Optional[str]
    status: Literal["active"]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PublicLocation":
        return cls(
            id=str(payload["id"]),
            name=str(payload["name"]),
            country=payload.get("country"),
            region=payload.get("region"),
            status=payload["status"],
        )


class PublicApiError(Exception):
    """Raised when the versioned public API returns an unsuccessful response."""

    def __init__(self, message: str, status_code: int = 0, response: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class PublicLocationMethods:
    def __init__(self, client: "KokonutPublicApiClient") -> None:
        self._client = client

    def list(self) -> list[PublicLocation]:
        return [PublicLocation.from_payload(row) for row in self._client._get("/locations")["data"]]

    def get(self, location_id: str) -> PublicLocation:
        path_id = quote(location_id, safe="")
        payload = self._client._get(f"/locations/{path_id}")["data"]
        return PublicLocation.from_payload(payload)


class KokonutPublicApiClient:
    """Client for stable `/api/v1` reads on the Kokonut Gateway.

    `base_url` is the Gateway origin (for example `http://localhost:8098`),
    not the legacy Directus origin used by :class:`KokonutClient`.
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/api/v1"
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault("Accept", "application/json")
        if api_key:
            self.session.headers["x-api-key"] = api_key
        self.locations = PublicLocationMethods(self)

    def close(self) -> None:
        self.session.close()

    def _get(self, path: str) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}{path}", timeout=self.timeout)
        if not response.ok:
            try:
                body = response.json()
                message = body.get("error", response.text) if isinstance(body, dict) else response.text
            except ValueError:
                message = response.text or f"HTTP {response.status_code}"
            raise PublicApiError(message, response.status_code, response)
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("data"), (dict, list)):
            raise PublicApiError("Invalid public API response envelope", response.status_code, response)
        return body
