"""Validated deployment settings for existing optional provider adapters.

Selection describes dependencies; it does not install adapters or replace domain
operations. Native replacements are enabled only after their parity gates pass.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ProviderSettings:
    directus: bool = True
    clickhouse: bool = True
    grpc: bool = True
    metabase: bool = True
    mqtt: bool = True
    prefect: bool = False

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> ProviderSettings:
        """Read explicit feature switches without reading provider credentials."""
        environment = os.environ if environment is None else environment
        values = {}
        for name, definition in cls.__dataclass_fields__.items():
            key = f"KOKONUT_FEATURE_{name.upper()}"
            raw = environment.get(key)
            if raw is None:
                values[name] = definition.default
                continue
            normalized = raw.strip().lower()
            if normalized not in {"true", "false"}:
                raise ValueError(f"{key} must be true or false")
            values[name] = normalized == "true"
        return cls(**values)
