"""Core services — microkernel with feature flags."""

__all__ = ["is_enabled", "get_feature", "list_features", "check_health", "HealthStatus"]


def __getattr__(name):
    """Keep contracts/settings imports independent of runtime initialization."""
    if name in {"is_enabled", "get_feature", "list_features"}:
        from services.core import features

        return getattr(features, name)
    if name in {"check_health", "HealthStatus"}:
        from services.core import health

        return getattr(health, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
