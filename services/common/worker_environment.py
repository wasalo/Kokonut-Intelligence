"""Build child environments with explicit worker-secret boundaries."""

from __future__ import annotations

import os
import re
from typing import Mapping, Sequence

_WORKER_SECRET_ENV = re.compile(
    r"^KOKONUT_([A-Z][A-Z0-9_]*)_(?:DATABASE_URL|WORKER_CREDENTIAL)$"
)
_WORKER_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def worker_subprocess_environment(
    *,
    allowed_worker_keys: Sequence[str] = (),
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Copy the environment while allowing only explicitly named worker secrets.

    Standard application settings are preserved. Variables shaped like
    ``KOKONUT_<WORKER>_DATABASE_URL`` or
    ``KOKONUT_<WORKER>_WORKER_CREDENTIAL`` are removed unless that worker key
    is explicitly allowed for the child. An empty allowlist is appropriate for
    APIs, scheduled commands, event handlers, and other general subprocesses.
    """
    if isinstance(allowed_worker_keys, (str, bytes)):
        raise ValueError("worker keys must be provided as a sequence")
    allowed: set[str] = set()
    for key in allowed_worker_keys:
        if not isinstance(key, str) or not _WORKER_KEY.fullmatch(key):
            raise ValueError("worker keys must be alphanumeric identifiers")
        allowed.add(key.upper())

    source = os.environ if environ is None else environ
    child_environment: dict[str, str] = {}
    for name, value in source.items():
        match = _WORKER_SECRET_ENV.fullmatch(name)
        if match is None or match.group(1) in allowed:
            child_environment[name] = value
    return child_environment
