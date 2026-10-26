"""Isolated scheduled worker for read-only Baal governance indexing."""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlsplit

from services.common.cli import run
from services.common.worker_database import get_worker_db
from services.core.features import is_enabled

from . import baal_indexer

WORKER_KEY = "baal_indexer"
RPC_ENV = "KOKONUT_BAAL_INDEXER_RPC_ENDPOINT"


def _rpc_endpoint(environ: dict[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    endpoint = source.get(RPC_ENV, "")
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError(f"{RPC_ENV} must contain an HTTPS endpoint")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{RPC_ENV} must contain an HTTPS endpoint without URL credentials")
    return endpoint


class BaalWorkerPersistence:
    """Execute the migration 644 bounded database contract."""

    @staticmethod
    def _scalar(connection, statement: str, parameters=()):
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            row = cursor.fetchone()
        return row[0] if row else None

    def acquire_lock(self, connection) -> None:
        self._scalar(connection, "SELECT kokonut_security.acquire_baal_indexer_lock()")

    def release_lock(self, connection) -> None:
        self._scalar(connection, "SELECT kokonut_security.release_baal_indexer_lock()")

    def read_cursor(self, connection):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM kokonut_security.read_baal_indexer_cursor()")
            return cursor.fetchone()

    def resolve_protocol(self, connection):
        value = self._scalar(
            connection, "SELECT kokonut_security.resolve_baal_protocol()"
        )
        return str(value) if value else None

    def resolve_wallet(self, connection, address: str):
        value = self._scalar(
            connection,
            "SELECT kokonut_security.resolve_baal_wallet(%s)",
            (address,),
        )
        return str(value) if value else None

    def store_governance_event(self, connection, record: dict) -> None:
        payload = json.dumps(record, default=str, separators=(",", ":"))
        self._scalar(
            connection,
            "SELECT kokonut_security.store_baal_governance_event(%s::jsonb)",
            (payload,),
        )

    def update_status(
        self,
        connection,
        block: int,
        status: str,
        error: str | None = None,
    ) -> None:
        self._scalar(
            connection,
            "SELECT kokonut_security.update_baal_indexer_status(%s,%s,%s)",
            (block, status, error),
        )


def execute(*, from_block: int | None = None, to_block: int | None = None) -> int:
    """Run one Baal indexing pass using dedicated credentials and endpoint."""
    if not is_enabled("isolated_baal_indexer_worker"):
        raise RuntimeError("isolated Baal indexer worker is disabled")
    endpoint = _rpc_endpoint()
    return baal_indexer.run(
        from_block=from_block,
        to_block=to_block,
        database_factory=lambda: get_worker_db(WORKER_KEY),
        rpc_url=endpoint,
        persistence=BaalWorkerPersistence(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Isolated Baal governance indexer")
    parser.add_argument("--from-block", type=int)
    parser.add_argument("--to-block", type=int)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    run(lambda: execute(from_block=args.from_block, to_block=args.to_block))


if __name__ == "__main__":
    main()
