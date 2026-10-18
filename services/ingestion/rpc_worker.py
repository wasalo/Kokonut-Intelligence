"""Run one chain's wallet balance snapshot through the isolated RPC identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from web3 import Web3

from services.common.cli import print_json, run
from services.common.worker_database import get_worker_db
from services.common.worker_environment import isolated_worker_key
from services.core.features import is_enabled

from .rpc_provider import RPC_CLI_CHAINS, configured_rpc_endpoints

WORKER_KEY = "rpc_indexer"
_PROJECTION_COLUMNS = [
    "timestamp", "wallet_address", "chain", "tx_hash", "block_number",
    "event_type", "value", "token", "status", "metadata",
]
_ETH_BALANCE_QUANTUM = Decimal("0.00000001")


class RPCWorkerPersistenceError(RuntimeError):
    """A bounded database operation failed and the chain run must stop."""


class RPCWorkerIncompleteError(RuntimeError):
    """At least one wallet provider request failed during an otherwise durable run."""


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _snapshot_record_json(record: dict[str, Any]) -> str:
    """Serialize a snapshot with its decimal balance as an exact JSON number."""
    value = record.get("value")
    if not isinstance(value, Decimal):
        return json.dumps(record, separators=(",", ":"), default=str)
    if not value.is_finite():
        raise ValueError("RPC balance value is invalid")
    decimal_number = format(value, "f")
    serializable_record = {**record, "value": decimal_number}
    encoded = json.dumps(serializable_record, separators=(",", ":"), default=str)
    encoded_string = json.dumps(decimal_number, separators=(",", ":"))
    marker = f'"value":{encoded_string}'
    if marker not in encoded:
        raise ValueError("RPC balance value could not be serialized")
    return encoded.replace(marker, f'"value":{decimal_number}', 1)


def _snapshot_record(
    *, wallet_id: str, chain: str, address: str, block_number: int,
    block_timestamp: int, balance_wei: int
) -> tuple[dict[str, Any], str]:
    if isinstance(block_number, bool) or not isinstance(block_number, int) or block_number < 0:
        raise ValueError("RPC block number is invalid")
    if isinstance(balance_wei, bool) or not isinstance(balance_wei, int) or balance_wei < 0:
        raise ValueError("RPC balance is invalid")
    if isinstance(block_timestamp, bool) or not isinstance(block_timestamp, int) or block_timestamp < 0:
        raise ValueError("RPC block timestamp is invalid")
    observed_at = datetime.fromtimestamp(block_timestamp, tz=timezone.utc).isoformat()
    tx_hash = "0x" + hashlib.sha256(
        f"kokonut:rpc-balance:{chain}:{wallet_id}:{block_number}".encode()
    ).hexdigest()
    balance_eth = (Decimal(balance_wei) / Decimal(10**18)).quantize(
        _ETH_BALANCE_QUANTUM, rounding=ROUND_HALF_UP
    )
    record = {
        "wallet_id": wallet_id,
        "chain": chain,
        "tx_hash": tx_hash,
        "block_number": block_number,
        "block_timestamp": observed_at,
        "from_address": "",
        "to_address": address,
        "value": balance_eth,
        "token": "ETH",
        "gas_used": 0,
        "gas_price": 0,
        "status": "success",
        "activity_type": "balance_check",
    }
    return record, _hash_payload(record)


def _record_snapshot(
    connection, chain: str, record: dict[str, Any], payload_hash: str
) -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.store_rpc_indexer_snapshot(%s, %s::uuid, %s::jsonb, %s)",
                (
                    chain,
                    record["wallet_id"],
                    _snapshot_record_json(record),
                    payload_hash,
                ),
            )
            result = cursor.fetchone()
            if result is None:
                raise RuntimeError("RPC snapshot function returned no result")
        connection.commit()
        return bool(result[0])
    except Exception as exc:
        connection.rollback()
        raise RPCWorkerPersistenceError(
            f"RPC wallet snapshot could not be persisted ({type(exc).__name__})"
        ) from None


def _finish_chain(
    connection,
    *,
    chain: str,
    status: str,
    error: str | None,
    wallet_count: int,
    last_block: int | None,
    elapsed_ms: int,
    payload_hash: str,
) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.finish_rpc_indexer_chain(%s, %s, %s, %s, %s, %s, %s)",
                (chain, status, error, wallet_count, last_block, elapsed_ms, payload_hash),
            )
            if cursor.fetchone() is None:
                raise RuntimeError("RPC completion function returned no result")
        connection.commit()
    except Exception as exc:
        connection.rollback()
        raise RPCWorkerPersistenceError(
            f"RPC chain completion could not be persisted ({type(exc).__name__})"
        ) from None


def ingest(chain: str) -> dict[str, Any]:
    """Record one bounded balance snapshot run without shared DB credentials."""
    if chain not in RPC_CLI_CHAINS:
        raise ValueError("Unsupported RPC chain")
    started = time.monotonic()
    endpoints = configured_rpc_endpoints()
    connection = get_worker_db(WORKER_KEY)
    lock_acquired = False
    finished = False
    wallet_count = 0
    inserted_count = 0
    last_block: int | None = None
    errors: list[str] = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.acquire_rpc_indexer_chain_lock(%s)", (chain,)
            )
        connection.commit()
        lock_acquired = True

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT wallet_id::text, address, label FROM kokonut_security.list_rpc_indexer_wallets(%s)",
                (chain,),
            )
            wallets = cursor.fetchall()
        connection.commit()
        wallet_count = len(wallets)
        endpoint = endpoints[chain]
        provider = Web3.HTTPProvider(endpoint, request_kwargs={"timeout": 20})
        web3 = Web3(provider)

        for wallet_id, wallet_address, label in wallets:
            try:
                checksum_address = Web3.to_checksum_address(wallet_address)
                block_number = int(web3.eth.block_number)
                balance_wei = int(web3.eth.get_balance(checksum_address, block_identifier=block_number))
                block = web3.eth.get_block(block_number)
                block_timestamp = int(block["timestamp"])
                record, payload_hash = _snapshot_record(
                    wallet_id=str(wallet_id),
                    chain=chain,
                    address=checksum_address,
                    block_number=block_number,
                    block_timestamp=block_timestamp,
                    balance_wei=balance_wei,
                )
                if _record_snapshot(connection, chain, record, payload_hash):
                    inserted_count += 1
                last_block = max(block_number, last_block or block_number)
            except RPCWorkerPersistenceError:
                raise
            except Exception as exc:
                connection.rollback()
                errors.append(
                    f"{str(wallet_id)[:8]}: RPC request failed ({type(exc).__name__})"
                )

        status = "error" if errors else "healthy"
        safe_error = "; ".join(errors[:3])[:500] if errors else None
        elapsed_ms = min(600_000, max(0, int((time.monotonic() - started) * 1000)))
        run_hash = _hash_payload(
            {
                "chain": chain,
                "wallet_count": wallet_count,
                "inserted_count": inserted_count,
                "last_block": last_block,
                "errors": len(errors),
            }
        )
        _finish_chain(
            connection,
            chain=chain,
            status=status,
            error=safe_error,
            wallet_count=inserted_count,
            last_block=last_block if status == "healthy" else None,
            elapsed_ms=elapsed_ms,
            payload_hash=run_hash,
        )
        finished = True
        if errors:
            raise RPCWorkerIncompleteError(f"RPC indexing incomplete for {chain}: {safe_error}")
        return {
            "status": "success",
            "chain": chain,
            "wallets": wallet_count,
            "snapshots_inserted": inserted_count,
            "last_block": last_block,
        }
    except Exception as exc:
        connection.rollback()
        if lock_acquired and not finished:
            try:
                _finish_chain(
                    connection,
                    chain=chain,
                    status="error",
                    error=f"RPC worker failed ({type(exc).__name__})",
                    wallet_count=inserted_count,
                    last_block=None,
                    elapsed_ms=min(600_000, max(0, int((time.monotonic() - started) * 1000))),
                    payload_hash=_hash_payload({"chain": chain, "failure": type(exc).__name__}),
                )
                finished = True
            except Exception:
                connection.rollback()
        if isinstance(exc, (ValueError, RPCWorkerPersistenceError, RPCWorkerIncompleteError)):
            raise
        raise RuntimeError(f"RPC indexing failed ({type(exc).__name__})") from None
    finally:
        if lock_acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT kokonut_security.release_rpc_indexer_chain_lock(%s)", (chain,)
                    )
                connection.commit()
            except Exception:
                connection.rollback()
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated RPC wallet snapshot indexing")
    parser.add_argument("--chain", required=True, choices=RPC_CLI_CHAINS)
    args = parser.parse_args()
    if not is_enabled("isolated_rpc_indexer_worker"):
        parser.error("isolated RPC indexer worker is disabled")
    if isolated_worker_key() != WORKER_KEY:
        parser.error("RPC indexer worker must be launched by the scheduled worker boundary")
    print_json(ingest(args.chain))


if __name__ == "__main__":
    run(main)
