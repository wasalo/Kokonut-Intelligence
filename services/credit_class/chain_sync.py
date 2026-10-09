"""Chain sync: reconciles PostgreSQL credit ledger with on-chain ERC-1155 state.

All on-chain calls are gated by CREDIT_ONCHAIN_SYNC_ENABLED (default false).
No behavioral change for existing deployments.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from services.common.logging import get_logger

logger = get_logger("credit_class.chain_sync")

ENABLED = os.environ.get("CREDIT_ONCHAIN_SYNC_ENABLED", "false").lower() in ("1", "true", "yes")

_ABI_PATH = Path(__file__).parent.parent.parent / "contracts" / "abis" / "KokonutCreditToken.json"

# Minimal ABI subset for the functions we call
_MINIMAL_ABI: list[dict] | None = None


def _load_abi() -> list[dict]:
    """Load the full ABI from the compiled contract artifact."""
    global _MINIMAL_ABI
    if _MINIMAL_ABI is not None:
        return _MINIMAL_ABI
    if _ABI_PATH.exists():
        _MINIMAL_ABI = json.loads(_ABI_PATH.read_text())
    else:
        # Fallback: minimal ABI with the functions we need
        _MINIMAL_ABI = [
            {
                "name": "issue",
                "type": "function",
                "stateMutability": "nonpayable",
                "inputs": [
                    {"name": "batchId", "type": "bytes32"},
                    {"name": "recipient", "type": "address"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "vintageYear", "type": "uint256"},
                    {"name": "jurisdiction", "type": "string"},
                    {"name": "methodology", "type": "string"},
                    {"name": "evidenceHash", "type": "bytes32"},
                ],
                "outputs": [],
            },
            {
                "name": "retire",
                "type": "function",
                "stateMutability": "nonpayable",
                "inputs": [
                    {"name": "tokenId", "type": "uint256"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "reasonHash", "type": "bytes32"},
                ],
                "outputs": [],
            },
            {
                "name": "balanceOf",
                "type": "function",
                "stateMutability": "view",
                "inputs": [
                    {"name": "account", "type": "address"},
                    {"name": "id", "type": "uint256"},
                ],
                "outputs": [{"name": "", "type": "uint256"}],
            },
            {
                "name": "totalIssued",
                "type": "function",
                "stateMutability": "view",
                "inputs": [{"name": "tokenId", "type": "uint256"}],
                "outputs": [{"name": "", "type": "uint256"}],
            },
            {
                "name": "totalRetired",
                "type": "function",
                "stateMutability": "view",
                "inputs": [{"name": "tokenId", "type": "uint256"}],
                "outputs": [{"name": "", "type": "uint256"}],
            },
            {
                "name": "batchExists",
                "type": "function",
                "stateMutability": "view",
                "inputs": [{"name": "batchId", "type": "bytes32"}],
                "outputs": [{"name": "", "type": "bool"}],
            },
        ]
    return _MINIMAL_ABI


def _get_web3_and_contract(
    chain: str = "celo",
    private_key: str | None = None,
    contract_address: str | None = None,
):
    """Return (w3, account, contract) for on-chain credit operations."""
    from web3 import Web3
    from eth_account import Account

    from services.ingestion.config import CHAIN_RPC_MAP

    rpc_url = CHAIN_RPC_MAP.get(chain)
    if not rpc_url:
        raise ValueError(f"No RPC URL configured for chain: {chain}")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to {chain} RPC at {rpc_url}")

    pk = private_key or os.environ.get("CREDIT_ISSUER_PRIVATE_KEY", "")
    if not pk:
        raise ValueError("No private key. Set CREDIT_ISSUER_PRIVATE_KEY env var or pass private_key.")

    account = Account.from_key(pk)
    abi = _load_abi()
    addr = w3.to_checksum_address(contract_address) if contract_address else None
    contract = w3.eth.contract(address=addr, abi=abi) if addr else None

    return w3, account, contract


def _compute_token_id(
    w3,
    batch_id_bytes: bytes,
    vintage_year: int,
    recipient: str,
    serial_number: int,
) -> int:
    """Compute tokenId exactly as the Solidity contract does:

    tokenId = uint256(keccak256(abi.encode(batchId, vintageYear, recipient, serialNumber)))
    """
    from web3 import Web3
    from eth_abi import encode

    encoded = encode(
        ["bytes32", "uint256", "address", "uint256"],
        [batch_id_bytes, vintage_year, recipient, serial_number],
    )
    token_hash = Web3.keccak(encoded)
    return int.from_bytes(token_hash, "big")


def _batch_id_to_bytes32(batch_code: str) -> bytes:
    """Convert a batch code string to a bytes32 value (keccak256 hash)."""
    from web3 import Web3

    return Web3.keccak(batch_code.encode("utf-8"))


def sync_credits_to_chain(
    conn,
    credit_batch_id: str,
    private_key: str | None = None,
    chain: str = "celo",
    contract_address: str | None = None,
) -> dict:
    """Mint on-chain credits for a batch that exists in PostgreSQL.

    Reads credit_balance for the batch, mints via KokonutCreditToken.issue(),
    and records the contract mapping in credit_batch_contract.

    Returns:
        {"batch_id": str, "minted": int, "tx_hash": str}
    """
    if not ENABLED:
        logger.info("CREDIT_ONCHAIN_SYNC_ENABLED is false; skipping chain sync for batch %s", credit_batch_id)
        return {"batch_id": credit_batch_id, "minted": 0, "tx_hash": "", "skipped": True}

    batch = conn.execute(
        conn.text("SELECT * FROM credit_batch WHERE id = :bid"),
        {"bid": credit_batch_id},
    ).mappings().first()
    if not batch:
        raise ValueError(f"Credit batch not found: {credit_batch_id}")

    balances = conn.execute(
        conn.text(
            "SELECT account_address, tradable_amount, retired_amount "
            "FROM credit_balance "
            "WHERE credit_batch_id = :bid AND (tradable_amount > 0 OR retired_amount > 0)"
        ),
        {"bid": credit_batch_id},
    ).mappings().all()

    if not balances:
        logger.info("No balances to sync for batch %s", credit_batch_id)
        return {"batch_id": credit_batch_id, "minted": 0, "tx_hash": ""}

    contract_record = conn.execute(
        conn.text(
            "SELECT contract_address FROM credit_batch_contract "
            "WHERE credit_batch_id = :bid AND chain = :chain"
        ),
        {"bid": credit_batch_id, "chain": chain},
    ).mappings().first()

    if not contract_record:
        raise ValueError(f"No credit_batch_contract found for batch {credit_batch_id} on {chain}")

    w3, account, contract = _get_web3_and_contract(
        chain=chain, private_key=private_key, contract_address=contract_record["contract_address"],
    )

    batch_id_bytes = _batch_id_to_bytes32(batch["batch_code"])
    vintage_year = batch["vintage_year"]
    jurisdiction = batch.get("jurisdiction", "") or ""
    methodology = batch.get("methodology", "") or ""
    evidence_hash = bytes(32)  # zero bytes32

    total_minted = 0
    tx_hashes = []

    for bal in balances:
        recipient = w3.to_checksum_address(bal["account_address"])
        amount = int(float(bal["tradable_amount"]) + float(bal["retired_amount"]))
        if amount <= 0:
            continue

        serial_result = conn.execute(
            conn.text(
                "SELECT COALESCE(MAX(serial_number), 0) + 1 AS next_serial "
                "FROM credit_chain_mint WHERE credit_batch_id = :bid"
            ),
            {"bid": credit_batch_id},
        ).mappings().first()
        serial_number = int(serial_result["next_serial"]) if serial_result else 1

        token_id = _compute_token_id(w3, batch_id_bytes, vintage_year, recipient, serial_number)

        try:
            tx = contract.functions.issue(
                batch_id_bytes,
                recipient,
                amount,
                vintage_year,
                jurisdiction,
                methodology,
                evidence_hash,
            ).build_transaction({
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "chainId": w3.eth.chain_id,
                "gas": 500000,
                "maxFeePerGas": w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
            })

            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            tx_hashes.append(receipt.transactionHash.hex())

            conn.execute(
                conn.text(
                    "INSERT INTO credit_chain_mint "
                    "(credit_batch_id, token_id, recipient, amount, serial_number, tx_hash, chain) "
                    "VALUES (:bid, :tid, :rec, :amt, :sn, :txh, :chain)"
                ),
                {
                    "bid": credit_batch_id,
                    "tid": str(token_id),
                    "rec": recipient,
                    "amt": amount,
                    "sn": serial_number,
                    "txh": receipt.transactionHash.hex(),
                    "chain": chain,
                },
            )

            total_minted += amount
            logger.info(
                "Minted %d credits (tokenId=%s) for %s, tx=%s",
                amount, token_id, recipient, receipt.transactionHash.hex(),
            )
        except Exception as e:
            logger.error("Failed to mint %d credits for %s: %s", amount, recipient, e)
            raise

    return {
        "batch_id": credit_batch_id,
        "minted": total_minted,
        "tx_hashes": tx_hashes,
        "contract_address": contract_record["contract_address"],
        "chain": chain,
    }


def retire_onchain(
    conn,
    retirement_id: str,
    private_key: str | None = None,
    chain: str = "celo",
) -> dict:
    """Burn on-chain credits for a confirmed retirement.

    Returns:
        {"retirement_id": str, "burned": int, "tx_hash": str}
    """
    if not ENABLED:
        logger.info("CREDIT_ONCHAIN_SYNC_ENABLED is false; skipping on-chain retirement %s", retirement_id)
        return {"retirement_id": retirement_id, "burned": 0, "tx_hash": "", "skipped": True}

    retirement = conn.execute(
        conn.text("SELECT * FROM credit_retirement WHERE id = :rid"),
        {"rid": retirement_id},
    ).mappings().first()
    if not retirement:
        raise ValueError(f"Retirement not found: {retirement_id}")

    credit = conn.execute(
        conn.text("SELECT * FROM carbon_credit WHERE id = :cid"),
        {"cid": str(retirement["credit_id"])},
    ).mappings().first()
    if not credit:
        raise ValueError(f"Carbon credit not found: {retirement['credit_id']}")

    contract_record = conn.execute(
        conn.text(
            "SELECT contract_address FROM credit_batch_contract "
            "WHERE credit_batch_id = :bid AND chain = :chain"
        ),
        {"bid": str(credit.get("credit_batch_id", "")) if credit.get("credit_batch_id") else None, "chain": chain},
    ).mappings().first()

    # Fall back to credit_class level contract mapping
    if not contract_record and credit.get("credit_batch_id"):
        batch = conn.execute(
            conn.text("SELECT credit_class_id FROM credit_batch WHERE id = :bid"),
            {"bid": str(credit["credit_batch_id"])},
        ).mappings().first()
        if batch:
            contract_record = conn.execute(
                conn.text(
                    "SELECT contract_address FROM credit_batch_contract "
                    "WHERE credit_batch_id IN (SELECT id FROM credit_batch WHERE credit_class_id = :ccid) "
                    "AND chain = :chain LIMIT 1"
                ),
                {"ccid": str(batch["credit_class_id"]), "chain": chain},
            ).mappings().first()

    if not contract_record:
        raise ValueError(f"No contract address found for credit {credit['id']} on {chain}")

    w3, account, contract = _get_web3_and_contract(
        chain=chain, private_key=private_key, contract_address=contract_record["contract_address"],
    )

    retired_tonnes = float(retirement["retired_tonnes"])
    amount = int(retired_tonnes * 1000)  # convert tonnes to token units (3 decimals)

    # Use credit's vintage year and a serial from chain_mint history
    vintage_year = credit["vintage_year"]
    batch_id_bytes = bytes(32)  # placeholder; actual tokenId lookup below

    # Look up the tokenId from the mint history
    mint_record = conn.execute(
        conn.text(
            "SELECT token_id FROM credit_chain_mint "
            "WHERE credit_batch_id = :bid ORDER BY created_at DESC LIMIT 1"
        ),
        {"bid": str(credit["credit_batch_id"]) if credit.get("credit_batch_id") else None},
    ).mappings().first()

    if mint_record:
        token_id = int(mint_record["token_id"])
    else:
        token_id = 0

    reason_hash = w3.keccak(retirement.get("retirement_reason", "").encode("utf-8")) if retirement.get("retirement_reason") else bytes(32)

    try:
        tx = contract.functions.retire(
            token_id,
            amount,
            reason_hash,
        ).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": w3.eth.chain_id,
            "gas": 300000,
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        conn.execute(
            conn.text(
                "UPDATE credit_retirement SET chain_tx_hash = :txh, chain = :chain "
                "WHERE id = :rid"
            ),
            {"txh": receipt.transactionHash.hex(), "chain": chain, "rid": retirement_id},
        )

        logger.info(
            "Retired %d token units (tokenId=%s) on-chain for retirement %s, tx=%s",
            amount, token_id, retirement_id, receipt.transactionHash.hex(),
        )

        return {
            "retirement_id": retirement_id,
            "burned": amount,
            "tx_hash": receipt.transactionHash.hex(),
            "chain": chain,
        }
    except Exception as e:
        logger.error("Failed to retire on-chain for retirement %s: %s", retirement_id, e)
        raise


def verify_chain_balance(
    conn,
    token_id: int,
    account: str,
    chain: str = "celo",
    contract_address: str | None = None,
) -> dict:
    """Compare PostgreSQL balance with on-chain balance for a token/account pair.

    Uses the ERC-1155 KokonutCreditToken contract (not EAS).

    Returns:
        {"token_id": int, "account": str, "pg_balance": float, "chain_balance": float,
         "match": bool, "discrepancy": float}
    """
    pg_balance = conn.execute(
        conn.text(
            "SELECT tradable_amount, retired_amount FROM credit_balance "
            "WHERE credit_batch_id = :tid AND account_address = :account"
        ),
        {"tid": str(token_id), "account": account},
    ).mappings().first()

    pg_tradable = float(pg_balance["tradable_amount"]) if pg_balance else 0.0
    pg_retired = float(pg_balance["retired_amount"]) if pg_balance else 0.0
    pg_total = pg_tradable + pg_retired

    chain_balance = 0.0
    if not ENABLED:
        logger.debug("CREDIT_ONCHAIN_SYNC_ENABLED is false; chain balance check skipped")
        return {
            "token_id": token_id,
            "account": account,
            "pg_balance": pg_total,
            "chain_balance": 0.0,
            "match": True,
            "discrepancy": 0.0,
            "chain_query_skipped": True,
        }

    try:
        from web3 import Web3

        contract_rec = conn.execute(
            conn.text(
                "SELECT contract_address FROM credit_batch_contract "
                "WHERE credit_batch_id = :bid AND chain = :chain LIMIT 1"
            ),
            {"bid": str(token_id), "chain": chain},
        ).mappings().first()

        if not contract_rec and contract_address:
            addr = contract_address
        elif contract_rec:
            addr = contract_rec["contract_address"]
        else:
            logger.warning("No contract address for token_id %s on %s", token_id, chain)
            return {
                "token_id": token_id,
                "account": account,
                "pg_balance": pg_total,
                "chain_balance": 0.0,
                "match": False,
                "discrepancy": pg_total,
            }

        w3, _, contract = _get_web3_and_contract(
            chain=chain, contract_address=addr,
        )
        checksum_account = w3.to_checksum_address(account)
        chain_balance = float(contract.functions.balanceOf(checksum_account, token_id).call())
    except Exception as e:
        logger.warning("Could not query on-chain balance: %s", e)

    match = abs(pg_total - chain_balance) < 0.01
    discrepancy = pg_total - chain_balance

    return {
        "token_id": token_id,
        "account": account,
        "pg_balance": pg_total,
        "chain_balance": chain_balance,
        "match": match,
        "discrepancy": discrepancy,
    }


def reconcile_all(conn, chain: str = "celo") -> dict:
    """Full reconciliation across all batches. Returns discrepancy summary."""
    batches = conn.execute(
        conn.text(
            "SELECT DISTINCT credit_batch_id FROM credit_balance "
            "WHERE tradable_amount > 0 OR retired_amount > 0"
        ),
    ).mappings().all()

    discrepancies = []
    checked = 0

    for batch in batches:
        batch_id = batch["credit_batch_id"]
        # Look up token IDs from chain mint history
        mint_records = conn.execute(
            conn.text(
                "SELECT DISTINCT token_id, account_address FROM credit_chain_mint "
                "WHERE credit_batch_id = :bid"
            ),
            {"bid": batch_id},
        ).mappings().all()

        if not mint_records:
            # Fall back to balance table accounts
            bal_records = conn.execute(
                conn.text(
                    "SELECT account_address FROM credit_balance "
                    "WHERE credit_batch_id = :bid AND (tradable_amount > 0 OR retired_amount > 0)"
                ),
                {"bid": batch_id},
            ).mappings().all()
            for bal in bal_records:
                try:
                    result = verify_chain_balance(
                        conn,
                        token_id=0,
                        account=bal["account_address"],
                        chain=chain,
                    )
                    checked += 1
                    if not result["match"]:
                        discrepancies.append(result)
                except Exception as e:
                    logger.warning("Reconciliation error for batch %s account %s: %s",
                                   batch_id, bal["account_address"], e)
        else:
            for mint in mint_records:
                try:
                    result = verify_chain_balance(
                        conn,
                        token_id=int(mint["token_id"]),
                        account=mint["account_address"],
                        chain=chain,
                    )
                    checked += 1
                    if not result["match"]:
                        discrepancies.append(result)
                except Exception as e:
                    logger.warning("Reconciliation error for batch %s token %s: %s",
                                   batch_id, mint["token_id"], e)

    return {
        "chain": chain,
        "checked": checked,
        "discrepancies": discrepancies,
        "all_match": len(discrepancies) == 0,
    }
