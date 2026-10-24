"""Shared report-scope validation helpers."""


def require_network_scope(report_type: str, location_id: str | None) -> None:
    """Reject farm attribution when a report reads network-wide sources."""
    if location_id is not None:
        raise ValueError(f"{report_type} uses network-wide sources and cannot be farm-scoped")
