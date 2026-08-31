"""Marketplace settlement via SAFE (KI-14 D3).

Routes value moves (credit transfers, fee settlement) through the Gnosis
Core Team SAFE with 2-of-3 confirmation, replacing raw DB-only escrow
updates. The agent proposes settlement txs as a SAFE delegate; humans
confirm in the Safe app.

The order book stays in the DB (source of truth). Only the *value move*
(token transfer seller → buyer, fee → treasury) is proposed as a SAFE tx.
"""

from __future__ import annotations

import os
from decimal import Decimal

from services.treasury.propose import SafeProposeClient, SafeTxData

# Gnosis: Core Team SAFE (2-of-3) or a dedicated marketplace SAFE.
# Using Core Team SAFE for v1.2; a dedicated marketplace SAFE is a future option.
SETTLEMENT_SAFE = "0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5"
SETTLEMENT_CHAIN = "gnosis"
CREDIT_TOKEN = "0xc6b075ac3234a7ac729114b27370b552fa284690"  # KokonutCreditToken (shares)


def _delegate_key() -> str | None:
    return os.environ.get("SAFE_DELEGATE_KEY") or os.environ.get(
        "ATTESTER_PRIVATE_KEY"
    )


def propose_settlement(
    order_id: str,
    *,
    seller: str,
    buyer: str,
    quantity: Decimal,
    fee: Decimal = Decimal("0"),
    fee_recipient: str | None = None,
    safe_address: str = SETTLEMENT_SAFE,
    safe_chain: str = SETTLEMENT_CHAIN,
) -> dict:
    """Propose a credit transfer from seller → buyer (+ fee → treasury).

    Builds a KokonutCreditToken transfer call as a SAFE transaction and
    proposes it to the Gnosis SAFE for human confirmation.

    Args:
        order_id: credit_sell_order or credit_buy_order id
        seller: seller address
        buyer: buyer address
        quantity: credit quantity to transfer
        fee: fee amount (if any, deducted from quantity)
        fee_recipient: address for fee (defaults to the SAFE itself)
        safe_address: settlement SAFE (Core Team SAFE on Gnosis)
        safe_chain: chain for the settlement SAFE

    Returns:
        {"proposal_status": str, "safe_tx_hash": str, ...}
    """
    proposer = SafeProposeClient(
        chain=safe_chain,
        safe_address=safe_address,
        delegate_key=_delegate_key(),
    )
    # Build the credit transfer data (ERC-20 transferFrom)
    # The settlement SAFE should hold the credits (or have allowance)
    # Encode: transferFrom(settlement_safe, buyer, wei_quantity)
    wei_quantity = int(quantity * Decimal(10**18))
    # ERC-20 transferFrom selector: 0x23b872dd
    transfer_from_selector = "0x23b872dd"
    # ABI encode: address from, address to, uint256 value
    from_addr = safe_address[2:].lower().zfill(64)
    to_addr = buyer[2:].lower().zfill(64)
    value_hex = hex(wei_quantity)[2:].zfill(64)
    data = f"{transfer_from_selector}{from_addr}{to_addr}{value_hex}"

    safe_tx = SafeTxData(
        to=CREDIT_TOKEN,
        value=0,
        data=data,
        nonce=None,  # resolved from SAFE state
    )
    proposal = proposer.propose(safe_tx)

    # Fee tx (separate proposal, if applicable)
    fee_result = None
    if fee > 0 and fee_recipient:
        wei_fee = int(fee * Decimal(10**18))
        fee_to = (fee_recipient or safe_address)[2:].lower().zfill(64)
        fee_data = f"{transfer_from_selector}{from_addr}{fee_to}{hex(wei_fee)[2:].zfill(64)}"
        fee_tx = SafeTxData(to=CREDIT_TOKEN, value=0, data=fee_data, nonce=None)
        fee_result = proposer.propose(fee_tx)

    return {
        "order_id": order_id,
        "proposal_status": "proposed",
        "safe_tx_hash": proposal.get("safeTxHash") or safe_tx.safe_tx_hash,
        "safe_chain": safe_chain,
        "safe_address": safe_address,
        "fee_tx_hash": fee_result.get("safeTxHash") if fee_result else None,
    }


def propose_farm_op(
    safe_id: str,
    to: str,
    value: int | str = 0,
    data: str = "0x",
    memo: str = "",
    *,
    safe_address: str | None = None,
    safe_chain: str = "gnosis",
) -> dict:
    """Propose an operation on a farm SAFE (payroll, inputs, expenses).

    Args:
        safe_id: safe_account id (for reference)
        to: target address
        value: value in wei
        data: call data
        memo: human-readable description
        safe_address: the farm SAFE's address
        safe_chain: chain of the farm SAFE

    Returns:
        {"proposal_status": str, "safe_tx_hash": str, ...}
    """
    proposer = SafeProposeClient(
        chain=safe_chain,
        safe_address=safe_address,
        delegate_key=_delegate_key(),
    )
    safe_tx = SafeTxData(
        to=to,
        value=int(value) if isinstance(value, str) else value,
        data=data,
        nonce=None,
    )
    proposal = proposer.propose(safe_tx)

    return {
        "safe_id": safe_id,
        "memo": memo,
        "proposal_status": "proposed",
        "safe_tx_hash": proposal.get("safeTxHash") or safe_tx.safe_tx_hash,
        "safe_chain": safe_chain,
        "safe_address": safe_address,
    }