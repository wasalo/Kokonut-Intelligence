from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from .methods import (
    AttestationMethods,
    CropCycleMethods,
    ExportMethods,
    ExpenseEventMethods,
    FarmMethods,
    HarvestEventMethods,
    LocationMethods,
    NoiMethods,
    PlotMethods,
    ReportMethods,
    SalesEventMethods,
    SensorReadingMethods,
    WalletProfileMethods,
)
from .types import ListOptions


class KokonutError(Exception):
    """Base error for Kokonut SDK."""

    def __init__(self, message: str, status_code: int = 0, response: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthenticationError(KokonutError):
    """Raised on 401 / authentication failures."""


class NotFoundError(KokonutError):
    """Raised on 404 responses."""


class PermissionError(KokonutError):
    """Raised on 403 responses."""


class ValidationError(KokonutError):
    """Raised on 400 / validation failures."""


class KokonutClient:
    """Python SDK client for the Kokonut Intelligence Platform (Directus-backed).

    Usage::

        client = KokonutClient("http://localhost:8055", token="...")
        # or
        client = KokonutClient("http://localhost:8055")
        await client.login("email", "password")

        locations = client.locations.list()
        farms = client.farms.list_by_location(location_id)
    """

    def __init__(self, base_url: str, token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

        # Typed convenience accessors
        self.locations = LocationMethods(self)
        self.farms = FarmMethods(self)
        self.plots = PlotMethods(self)
        self.crop_cycles = CropCycleMethods(self)
        self.harvest_events = HarvestEventMethods(self)
        self.sales_events = SalesEventMethods(self)
        self.expense_events = ExpenseEventMethods(self)
        self.sensor_readings = SensorReadingMethods(self)
        self.wallet_profiles = WalletProfileMethods(self)
        self.attestations = AttestationMethods(self)
        self.reports = ReportMethods(self)
        self.exports = ExportMethods(self)
        self.noi = NoiMethods(self)

    # -- Auth ------------------------------------------------------------------

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate and store the bearer token on the session.

        Returns the full Directus auth response (access_token, refresh_token, etc.).
        """
        resp = self.session.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password},
        )
        self._handle_error(resp)
        body: Dict[str, Any] = resp.json().get("data", resp.json())
        access_token = body.get("access_token", body.get("token", ""))
        self.session.headers["Authorization"] = f"Bearer {access_token}"
        return body

    def logout(self) -> None:
        """Invalidate the current refresh token and clear local auth state."""
        try:
            self.session.post(f"{self.base_url}/auth/logout")
        except requests.RequestException:
            pass
        self.session.headers.pop("Authorization", None)

    # -- Generic CRUD ----------------------------------------------------------

    def list_items(
        self,
        collection: str,
        options: Optional[ListOptions] = None,
        **kwargs: Any,
    ) -> List[Any]:
        params = options.to_params() if options else {}
        params.update(kwargs)
        resp = self.session.get(f"{self.base_url}/items/{collection}", params=self._serialize_params(params))
        self._handle_error(resp)
        data = resp.json()
        return data.get("data", data)

    def get_item(self, collection: str, item_id: str, fields: Optional[List[str]] = None) -> Any:
        params: Dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        resp = self.session.get(f"{self.base_url}/items/{collection}/{item_id}", params=params)
        self._handle_error(resp)
        data = resp.json()
        return data.get("data", data)

    def create_item(self, collection: str, data: Dict[str, Any]) -> Any:
        resp = self.session.post(f"{self.base_url}/items/{collection}", json=data)
        self._handle_error(resp)
        body = resp.json()
        return body.get("data", body)

    def create_items(self, collection: str, data: List[Dict[str, Any]]) -> List[Any]:
        resp = self.session.post(f"{self.base_url}/items/{collection}", json=data)
        self._handle_error(resp)
        body = resp.json()
        return body.get("data", body)

    def update_item(self, collection: str, item_id: str, data: Dict[str, Any]) -> Any:
        resp = self.session.patch(f"{self.base_url}/items/{collection}/{item_id}", json=data)
        self._handle_error(resp)
        body = resp.json()
        return body.get("data", body)

    def delete_item(self, collection: str, item_id: str) -> None:
        resp = self.session.delete(f"{self.base_url}/items/{collection}/{item_id}")
        self._handle_error(resp)

    # -- Aggregate -------------------------------------------------------------

    def aggregate(self, collection: str, **kwargs: Any) -> List[Any]:
        """Run an aggregate query via Directus /items/:collection/aggregate."""
        resp = self.session.get(
            f"{self.base_url}/items/{collection}/aggregate",
            params=self._serialize_params(kwargs),
        )
        self._handle_error(resp)
        data = resp.json()
        return data.get("data", data)

    # -- Internal helpers ------------------------------------------------------

    @staticmethod
    def _serialize_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize complex params (dicts/lists) to JSON strings for query strings."""
        out: Dict[str, Any] = {}
        for k, v in params.items():
            if isinstance(v, (dict, list)):
                out[k] = json.dumps(v)
            else:
                out[k] = v
        return out

    @staticmethod
    def _handle_error(resp: requests.Response) -> None:
        if resp.ok:
            return
        status = resp.status_code
        try:
            body = resp.json()
            errors = body.get("errors", [])
            message = errors[0].get("message", resp.text) if errors else resp.text
        except (ValueError, KeyError):
            message = resp.text or f"HTTP {status}"

        if status == 401:
            raise AuthenticationError(message, status, resp)
        if status == 403:
            raise PermissionError(message, status, resp)
        if status == 404:
            raise NotFoundError(message, status, resp)
        if status == 400:
            raise ValidationError(message, status, resp)
        raise KokonutError(message, status, resp)
