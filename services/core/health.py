"""Service health contracts — checks for critical and optional services."""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone

from services.common.logging import get_logger

logger = get_logger("core.health")


@dataclass
class HealthStatus:
    """Health check result for a single service."""
    service: str
    healthy: bool
    critical: bool
    message: str
    latency_ms: int = 0
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "healthy": self.healthy,
            "critical": self.critical,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "checked_at": self.checked_at,
        }


def _check_postgres() -> HealthStatus:
    """Check PostgreSQL connectivity."""
    import time
    start = time.monotonic()
    try:
        from services.common.database import get_db
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT 1")
        db.close()
        latency = int((time.monotonic() - start) * 1000)
        return HealthStatus("database", True, True, "PostgreSQL connected", latency)
    except Exception:
        logger.exception("PostgreSQL health check failed")
        latency = int((time.monotonic() - start) * 1000)
        return HealthStatus("database", False, True, "PostgreSQL unavailable", latency)


def _check_clickhouse() -> HealthStatus:
    """Check ClickHouse connectivity."""
    import time
    start = time.monotonic()
    try:
        from services.ingestion.base import get_clickhouse
        client = get_clickhouse()
        if client is None:
            return HealthStatus("clickhouse", False, False, "ClickHouse client not configured")
        client.ping()
        latency = int((time.monotonic() - start) * 1000)
        return HealthStatus("clickhouse", True, False, "ClickHouse connected", latency)
    except Exception:
        logger.exception("ClickHouse health check failed")
        latency = int((time.monotonic() - start) * 1000)
        return HealthStatus("clickhouse", False, False, "ClickHouse unavailable", latency)


def _check_directus() -> HealthStatus:
    """Check Directus API health."""
    import os
    import time

    from services.common.http import http

    start = time.monotonic()
    try:
        url = os.environ.get("DIRECTUS_URL", "http://localhost:8055")
        resp = http.get(f"{url}/server/ping", timeout=5)
        resp.raise_for_status()
        latency = int((time.monotonic() - start) * 1000)
        return HealthStatus("directus", True, True, "Directus responding", latency)
    except Exception:
        logger.exception("Directus health check failed")
        latency = int((time.monotonic() - start) * 1000)
        return HealthStatus("directus", False, True, "Directus unavailable", latency)


def _check_port(host: str, port: int, service_name: str, critical: bool = False) -> HealthStatus:
    """Check if a TCP port is reachable."""
    import time
    start = time.monotonic()
    try:
        sock = socket.create_connection((host, port), timeout=3)
        sock.close()
        latency = int((time.monotonic() - start) * 1000)
        return HealthStatus(service_name, True, critical, f"Port {port} open", latency)
    except Exception:
        latency = int((time.monotonic() - start) * 1000)
        return HealthStatus(service_name, False, critical, f"Port {port} unreachable")


_CHECKERS = {
    "database": _check_postgres,
    "clickhouse": _check_clickhouse,
    "directus": _check_directus,
}


def check_health(services: list[str] | None = None) -> list[HealthStatus]:
    """Check health of specified or all services.

    Args:
        services: List of service names to check. If None, checks all enabled.

    Returns:
        List of HealthStatus results.
    """
    from services.core.features import FEATURES

    results = []
    targets = services or [name for name, cfg in FEATURES.items() if cfg["enabled"]]

    for service_name in targets:
        feature = FEATURES.get(service_name)
        if not feature:
            results.append(HealthStatus(service_name, False, False, "Unknown service"))
            continue

        # Use registered checker if available
        checker = _CHECKERS.get(service_name)
        if checker:
            results.append(checker())
        # Check port-based services
        elif "port" in feature:
            results.append(_check_port("localhost", feature["port"], service_name, feature.get("critical", False)))
        else:
            results.append(HealthStatus(service_name, True, feature.get("critical", False), "No health check defined"))

    return results


def overall_health(services: list[str] | None = None) -> dict:
    """Get overall system health status."""
    from services import __git_sha__, __version__

    results = check_health(services)
    critical_failures = [r for r in results if r.critical and not r.healthy]
    all_healthy = all(r.healthy for r in results)

    return {
        "healthy": all_healthy,
        "version": __version__,
        "git_sha": __git_sha__,
        "critical_failures": len(critical_failures),
        "services": [r.to_dict() for r in results],
    }
