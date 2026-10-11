"""Computation cache — PostgreSQL-backed result caching with TTL and event-driven invalidation."""

from services.cache.backend import get_computation_cache
from services.cache.cache import ComputationCache

__all__ = ["ComputationCache", "get_computation_cache"]
