"""Isolated scheduled runner for the legacy Gnosis Moloch v2 indexer."""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlsplit

from services.common.cli import run
from services.common.worker_database import get_worker_db
from services.core.features import is_enabled
from services.ingestion.clickhouse_outbox import OutboxEnqueueError

from . import gnosis_indexer

WORKER_KEY = "gnosis_indexer"
RPC_ENV = "KOKONUT_GNOSIS_INDEXER_RPC_ENDPOINTS"


def _rpc_endpoint(environ: dict[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    raw = source.get(RPC_ENV, "")
    try:
        endpoints = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise ValueError(f"{RPC_ENV} must be a JSON object with a gnosis endpoint") from None
    if not isinstance(endpoints, dict) or set(endpoints) != {"gnosis"}:
        raise ValueError(f"{RPC_ENV} must contain only the gnosis endpoint")
    endpoint = endpoints.get("gnosis")
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError(f"{RPC_ENV} must contain a non-empty gnosis endpoint")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{RPC_ENV} must contain an HTTPS endpoint without URL credentials")
    return endpoint


class GnosisWorkerPersistence:
    """Call the migration 643 bounded database contract."""

    @staticmethod
    def _scalar(connection, statement: str, parameters=()):
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            row = cursor.fetchone()
        return row[0] if row else None

    def acquire_lock(self, connection) -> None:
        self._scalar(connection, "SELECT kokonut_security.acquire_gnosis_indexer_lock()")

    def release_lock(self, connection) -> None:
        self._scalar(connection, "SELECT kokonut_security.release_gnosis_indexer_lock()")

    def read_cursor(self, connection):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM kokonut_security.read_gnosis_indexer_cursor()")
            return cursor.fetchone()

    def claim_event(
        self, connection, chain, tx_hash, log_index, block_number, block_hash, event_name
    ) -> bool:
        result = self._scalar(
            connection,
            "SELECT kokonut_security.claim_gnosis_event_log(%s,%s,%s,%s,%s,%s)",
            (chain, tx_hash, log_index, block_number, block_hash, event_name),
        )
        return bool(result)

    def resolve_wallet(self, connection, address: str, chain: str):
        if chain != "gnosis":
            return None
        result = self._scalar(
            connection, "SELECT kokonut_security.resolve_gnosis_wallet(%s)", (address,)
        )
        return str(result) if result else None

    def resolve_wallet_location(self, connection, wallet_id: str):
        result = self._scalar(
            connection,
            "SELECT kokonut_security.resolve_gnosis_wallet_location(%s::uuid)",
            (wallet_id,),
        )
        return str(result) if result else None

    def resolve_protocol(self, connection):
        result = self._scalar(
            connection, "SELECT kokonut_security.resolve_gnosis_protocol()"
        )
        return str(result) if result else None

    def _store(self, connection, function_name: str, record: dict):
        encoded = json.dumps(record, default=str, separators=(",", ":"))
        result = self._scalar(
            connection,
            f"SELECT kokonut_security.{function_name}(%s::jsonb)",
            (encoded,),
        )
        return str(result) if result else None

    def store_governance_event(self, connection, record: dict):
        return self._store(connection, "store_gnosis_governance_event", record)

    def store_treasury_event(self, connection, record: dict):
        bounded_record = {
            **record,
            "source": record.get("source", "moloch_dao"),
            "notes": json.dumps(record.get("metadata", {})),
        }
        return self._store(connection, "store_gnosis_treasury_event", bounded_record)

    def store_digital_lego_usage(self, connection, record: dict):
        return self._store(connection, "store_gnosis_digital_lego_usage", record)

    def enqueue_projection(self, connection, **values) -> str:
        try:
            result = self._scalar(
                connection,
                """SELECT kokonut_security.enqueue_gnosis_clickhouse(
                       %s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)""",
                (
                    values["event_key"], values["source_table"], values["source_id"],
                    values["target_table"], json.dumps(values["columns"]),
                    json.dumps(values["rows"], default=str), values["payload_hash"],
                ),
            )
            if result is None:
                raise OutboxEnqueueError("Gnosis outbox function returned no receipt")
            return str(result)
        except OutboxEnqueueError:
            raise
        except Exception:
            raise OutboxEnqueueError("Could not enqueue the canonical Gnosis projection") from None

    def update_status(
        self, connection, block: int, status: str, error: str | None, metadata: dict
    ) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.update_gnosis_indexer_status(%s,%s,%s,%s::jsonb)",
                (block, status, error, json.dumps(metadata, separators=(",", ":"))),
            )


def execute(*, from_block: int | None = None, to_block: int | None = None) -> None:
    """Run one block-bounded indexing pass using only worker-specific inputs."""
    if not is_enabled("isolated_gnosis_indexer_worker"):
        raise RuntimeError("isolated Gnosis indexer worker is disabled")
    endpoint = _rpc_endpoint()
    gnosis_indexer.run(
        from_block=from_block,
        to_block=to_block,
        database_factory=lambda: get_worker_db(WORKER_KEY),
        rpc_url=endpoint,
        persistence=GnosisWorkerPersistence(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Isolated Gnosis Moloch indexer")
    parser.add_argument("--from-block", type=int)
    parser.add_argument("--to-block", type=int)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    run(lambda: execute(from_block=args.from_block, to_block=args.to_block))


if __name__ == "__main__":
    main()
