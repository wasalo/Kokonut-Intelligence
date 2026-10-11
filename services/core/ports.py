"""Vendor-independent contracts shared by provider adapters."""

from __future__ import annotations

from typing import Protocol


class ProviderHealth(Protocol):
    service: str
    healthy: bool
    critical: bool
    message: str
    state: str

    def to_dict(self) -> dict: ...


class HealthProbe(Protocol):
    def __call__(self) -> ProviderHealth: ...
