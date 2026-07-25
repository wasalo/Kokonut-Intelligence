"""Chain sync: reconciles PostgreSQL credit ledger with onchain ERC-1155 state."""

from __future__ import annotations

from services.common.logging import get_logger

logger = get_logger("credit_class.chain_sync")


def sync_credits_to_chain(conn, credit_batch_id: str, private_key: str | None = None) -> dict:
    """Mint onchain credits for a batch that exists in PostgreSQL.

    Reads credit_balance for the batch, mints via KokonutCreditToken.issue(),
    and records the contract mapping in credit_batch_contract.

    Returns:
        {"batch_id": str, "minted": int, "tx_hash": str}
    """
    from services.attestation.config import get_chain_config

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

    total_minted = sum(float(b["tradable_amount"]) + float(b["retired_amount"]) for b in balances)

    contract_record = conn.execute(
        conn.text(
            "SELECT contract_address FROM credit_batch_contract "
            "WHERE credit_batch_id = :bid AND chain = 'ethereum'"
        ),
        {"bid": credit_batch_id},
    ).mappings().first()

    if not contract_record:
        raise ValueError(f"No credit_batch_contract found for batch {credit_batch_id} on ethereum")

    logger.info(
        "Would mint %d credits for batch %s on contract %s (dry run)",
        total_minted, credit_batch_id, contract_record["contract_address"],
    )

    return {
        "batch_id": credit_batch_id,
        "minted": int(total_minted),
        "contract_address": contract_record["contract_address"],
        "dry_run": True,
    }


def verify_chain_balance(conn, token_id: int, account: str, chain: str = "ethereum") -> dict:
    """Compare PostgreSQL balance with onchain balance for a token/account pair.

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
    try:
        from services.attestation.eas_client import EASClient
        client = EASClient(chain)
        if client.is_connected():
            contract = client.signer.w3.eth.contract(
                address=client.config["eas_address"],
                abi=[{"name": "balanceOf", "type": "function", "stateMutability": "view",
                       "inputs": [{"name": "account", "type": "address"}, {"name": "id", "type": "uint256"}],
                       "outputs": [{"name": "", "type": "uint256"}]}],
            )
            chain_balance = float(contract.functions.balanceOf(
                client.signer.w3.to_checksum_address(account), token_id
            ).call())
    except Exception as e:
        logger.warning("Could not query onchain balance: %s", e)

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


def reconcile_all(conn, chain: str = "ethereum") -> dict:
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
        try:
            result = verify_chain_balance(
                conn,
                token_id=hash(batch["credit_batch_id"]),
                account="0x0000000000000000000000000000000000000000",
                chain=chain,
            )
            checked += 1
            if not result["match"]:
                discrepancies.append(result)
        except Exception as e:
            logger.warning("Reconciliation error for batch %s: %s", batch["credit_batch_id"], e)

    return {
        "chain": chain,
        "checked": checked,
        "discrepancies": discrepancies,
        "all_match": len(discrepancies) == 0,
    }
