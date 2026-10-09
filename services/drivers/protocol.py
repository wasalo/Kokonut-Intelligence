"""DataSourceDriver protocol — the contract all data source drivers must implement.

Usage:
    from services.drivers.protocol import DataSourceDriver

    class MyDriver:
        name = "my_source"
        version = "1.0.0"
        driver_type = "sensor"

        def validate_config(self, config: dict) -> bool: ...
        def discover(self, config: dict) -> list[dict]: ...
        def fetch(self, source: dict) -> dict: ...
        def transform(self, raw: dict) -> list[dict]: ...
        def health_check(self, config: dict) -> bool: ...
"""

from __future__ import annotations

from typing import Protocol, Any, runtime_checkable


@runtime_checkable
class DataSourceDriver(Protocol):
    """Protocol that all data source drivers must implement."""

    name: str
    version: str
    driver_type: str  # 'sensor', 'remote_sensing', 'market', 'blockchain', 'weather', 'climate', 'gis'

    def validate_config(self, config: dict) -> bool:
        """Validate driver configuration against config_schema.

        Returns True if config is valid, False otherwise.
        """
        ...

    def discover(self, config: dict) -> list[dict]:
        """Discover available data sources from this driver.

        Returns a list of source descriptors, each a dict with at least
        a 'source_id' and 'display_name' key.
        """
        ...

    def fetch(self, source: dict) -> dict:
        """Fetch raw data from a source.

        Args:
            source: A source descriptor from discover() or with connection details.

        Returns:
            Raw data dict with 'data' key containing the fetched records.
        """
        ...

    def transform(self, raw: dict) -> list[dict]:
        """Transform raw data into governed records.

        Takes the output of fetch() and returns a list of dicts suitable
        for insertion into governed tables.
        """
        ...

    def health_check(self, config: dict) -> bool:
        """Check if the driver's data source is accessible.

        Returns True if healthy, False otherwise.
        """
        ...
