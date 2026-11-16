"""Database connection selection shared by scheduler entrypoints."""

from __future__ import annotations

import os

from services.common.database import get_db
from services.common.worker_database import get_worker_db


def scheduler_database_is_selected(environ=None) -> bool:
    """Return whether scheduler execution must use its isolated identity."""
    source = os.environ if environ is None else environ
    return (
        "KOKONUT_SCHEDULER_DATABASE_URL" in source
        or source.get("KOKONUT_ISOLATED_WORKER_KEY") == "scheduler"
        or source.get("KOKONUT_DENY_SHARED_DATABASE", "").lower() == "true"
    )


def get_scheduler_connection():
    """Connect as the dedicated scheduler identity when explicitly selected."""
    if scheduler_database_is_selected():
        return get_worker_db("scheduler", connect_timeout=5)
    return get_db(connect_timeout=5)
