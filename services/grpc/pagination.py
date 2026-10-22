"""Bounded offset-cursor pagination for gRPC list responses."""

from __future__ import annotations

import re

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500
MAX_OFFSET = 2**63 - 1
_OFFSET_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)\Z")


def parse_page_request(page_request) -> tuple[int, int]:
    """Validate a page request and return its offset and effective limit."""
    raw_offset = bytes(page_request.offset)
    if raw_offset:
        try:
            offset_text = raw_offset.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("pagination offset must be an ASCII decimal cursor") from exc
        if not _OFFSET_PATTERN.fullmatch(offset_text):
            raise ValueError("pagination offset must be an ASCII decimal cursor")
        offset = int(offset_text)
    else:
        offset = 0

    if offset > MAX_OFFSET:
        raise ValueError("pagination offset exceeds the supported range")

    limit = int(page_request.limit) or DEFAULT_PAGE_SIZE
    if limit > MAX_PAGE_SIZE:
        raise ValueError(f"pagination limit must not exceed {MAX_PAGE_SIZE}")

    return offset, limit


def paginate_items(items: list, page_request) -> tuple[list, dict[str, bytes | int]]:
    """Return one bounded page and its opaque decimal-offset cursor metadata.

    Cursor bytes are an ASCII decimal row offset. Clients should treat
    ``next_key`` as opaque and pass it back as ``offset``. The ordering of the
    input list must be deterministic for the lifetime of a page sequence.
    """
    offset, limit = parse_page_request(page_request)

    total = len(items)
    end = min(offset + limit, total)
    next_key = str(end).encode("ascii") if end < total else b""
    return items[offset:end], {"next_key": next_key, "total": total}
