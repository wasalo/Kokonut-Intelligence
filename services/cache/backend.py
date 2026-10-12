"""Construction boundary retaining the canonical PostgreSQL computation cache."""

from __future__ import annotations

from services.cache.ports import ComputationCacheBackend


def get_computation_cache(conn=None, default_ttl_seconds: int = 3600) -> ComputationCacheBackend:
    from services.cache.cache import ComputationCache

    return ComputationCache(conn=conn, default_ttl_seconds=default_ttl_seconds)
