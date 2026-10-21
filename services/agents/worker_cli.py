"""One-shot signed worker entry point for deterministic AI-summary drafts."""

from __future__ import annotations

import argparse
import json
from typing import Any

from services.agents.ai_summary import build_summary
from services.agents.worker_draft import (
    create_worker_ai_summary_draft,
    get_worker_ai_summary_draft,
)
from services.common.database import get_db

_SUMMARY_TYPES = ("operations", "financial", "environmental", "combined")


def run_worker_summary(
    location_id: str,
    summary_type: str,
    request_id: str,
    *,
    connection_factory=None,
    summary_builder=None,
    existing_reader=None,
    draft_writer=None,
) -> dict[str, Any]:
    """Generate under a read-only shared connection and persist as a worker.

    The request lookup happens before generation so an exact retry returns its
    original result without repeating source queries. Source data is read in a
    read-only transaction; draft creation and provenance attachment use the
    separate signed worker connection in :mod:`worker_draft`.
    """
    read_existing = existing_reader or get_worker_ai_summary_draft
    write_draft = draft_writer or create_worker_ai_summary_draft
    generate = summary_builder or build_summary
    prior = read_existing(location_id, summary_type, request_id)
    if prior is not None:
        return prior

    connection = (connection_factory or get_db)()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '3s'")
        summary = generate(connection, location_id, summary_type)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    # Match the legacy deterministic summary model label while the worker
    # adapter supplies signed identity, idempotency, and source references.
    payload = {**summary, "model_version": summary.get("model_version", "rules-v1")}
    return write_draft(location_id, summary_type, request_id, payload)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate one location-scoped AI summary using the signed worker identity"
    )
    parser.add_argument("--location-id", required=True, help="Location UUID")
    parser.add_argument(
        "--summary-type", choices=_SUMMARY_TYPES, default="combined", help="Summary generator"
    )
    parser.add_argument(
        "--request-id", required=True, help="Stable UUID reused when retrying this operation"
    )
    args = parser.parse_args()
    result = run_worker_summary(args.location_id, args.summary_type, args.request_id)
    print(
        json.dumps(
            {
                "summary_id": result.get("summary_id"),
                "resulting_status": result.get("resulting_status"),
                "replayed": bool(result.get("replayed")),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
