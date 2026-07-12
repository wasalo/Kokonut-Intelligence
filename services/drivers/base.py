"""Base driver class with common patterns (retry, logging, hashing).

All concrete drivers should inherit from BaseDriver and implement
the abstract methods.
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from services.common.logging import get_logger


class BaseDriver(ABC):
    """Base class providing common driver infrastructure.

    Subclasses must implement: validate_config, discover, fetch, transform, health_check.
    """

    name: str = "base"
    version: str = "1.0.0"
    driver_type: str = "unknown"

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._logger = get_logger(f"driver.{self.name}")

    @abstractmethod
    def validate_config(self, config: dict) -> bool:
        """Validate driver configuration."""
        ...

    @abstractmethod
    def discover(self, config: dict) -> list[dict]:
        """Discover available data sources."""
        ...

    @abstractmethod
    def fetch(self, source: dict) -> dict:
        """Fetch raw data from a source."""
        ...

    @abstractmethod
    def transform(self, raw: dict) -> list[dict]:
        """Transform raw data into governed records."""
        ...

    @abstractmethod
    def health_check(self, config: dict) -> bool:
        """Check if the data source is accessible."""
        ...

    def run(self, source: dict) -> list[dict]:
        """Execute the full fetch-transform pipeline with timing and error handling."""
        start = time.monotonic()
        try:
            raw = self.fetch(source)
            records = self.transform(raw)
            duration_ms = int((time.monotonic() - start) * 1000)
            self._logger.info(
                "Driver %s completed: %d records in %dms",
                self.name, len(records), duration_ms,
            )
            return records
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            self._logger.error(
                "Driver %s failed after %dms: %s",
                self.name, duration_ms, exc,
            )
            raise

    @staticmethod
    def hash_payload(data: Any) -> str:
        """Produce a SHA-256 hex digest of JSON-serializable data."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    @staticmethod
    def now_utc() -> datetime:
        """Current UTC time."""
        return datetime.now(timezone.utc)

    def _log_ingestion(
        self,
        source_system: str,
        source_table: str,
        source_id: str,
        target_table: str,
        target_id: str | None,
        operation: str,
        status: str,
        payload_hash: str | None = None,
        rows_affected: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Write to ingestion_log via the shared utility."""
        try:
            from services.ingestion.base import log_ingestion
            log_ingestion(
                source_system=source_system,
                source_table=source_table,
                source_id=source_id,
                target_table=target_table,
                target_id=target_id,
                operation=operation,
                payload_hash=payload_hash,
                status=status,
                rows_affected=rows_affected,
                error_message=error_message,
            )
        except Exception:
            self._logger.debug("Failed to write ingestion log")
