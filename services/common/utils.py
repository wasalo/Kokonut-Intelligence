"""Shared utility helpers for Kokonut Intelligence services."""

from __future__ import annotations

import hashlib
from typing import Any


def serialize_value(obj: Any) -> Any:
    """Convert a value to a JSON-safe representation.

    - datetimes / anything with ``isoformat()`` → ISO-8601 string
    - ``bytes`` / ``memoryview`` → SHA-256 digest prefix (avoids embedding
      raw binary, e.g. hashes or attachments, in JSON output)

    Used by the report generator and the governed exporter so JSON serialization
    stays consistent across services.
    """
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, (bytes, memoryview)):
        return hashlib.sha256(bytes(obj)).hexdigest()[:16]
    return obj


def serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Serialize each value in a list of dict rows via :func:`serialize_value`."""
    return [{k: serialize_value(v) for k, v in row.items()} for row in rows]
