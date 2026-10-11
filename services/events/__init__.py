"""Event bus for reactive workflows.

Publish-subscribe event system replacing polling-based workflows
with reactive, event-driven communication between services.
"""

__all__ = ["InsightTransferEngine"]


def __getattr__(name):
    if name == "InsightTransferEngine":
        from .insight_transfer import InsightTransferEngine

        return InsightTransferEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
