"""Token/Staking integration — external contract query, tree binding, yield."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from ..common.logging import get_logger

logger = get_logger("analytics.token_integration")


def register_token(
    conn,
    chain: str,
    contract_address: str,
    symbol: str,
    name: str,
    decimals: int = 18,
    deployment_mode: str = "external",
    contract_source_code: str = None,
    abi: dict = None,
    deployment_date: str = None,
    deployer_address: str = None,
) -> str:
    """Register a governance token (external or internal contract)."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO governance_token (
            chain, contract_address, symbol, name, decimals,
            deployment_mode, contract_source_code, abi,
            deployment_date, deployer_address, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
        ON CONFLICT (chain, contract_address) DO UPDATE SET
            symbol = EXCLUDED.symbol, name = EXCLUDED.name,
            deployment_mode = EXCLUDED.deployment_mode,
            updated_at = NOW()
        RETURNING id
    """, (
        chain, contract_address, symbol, name, decimals,
        deployment_mode, contract_source_code,
        json.dumps(abi) if abi else None,
        deployment_date, deployer_address,
    ))
    token_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Registered token: %s (%s on %s, mode=%s)", symbol, contract_address[:10], chain, deployment_mode)
    return token_id


def bind_tree(
    conn,
    tree_record_id: str,
    token_id: str,
    wallet_address: str,
    token_id_onchain: str = None,
    binding_tx_hash: str = None,
) -> str:
    """Create 1:1 tree-to-token binding."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tree_token_binding (
            tree_record_id, token_id, token_id_onchain, wallet_address,
            binding_tx_hash, status
        ) VALUES (%s, %s, %s, %s, %s, 'bound')
        RETURNING id
    """, (tree_record_id, token_id, token_id_onchain or "", wallet_address, binding_tx_hash))
    binding_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Bound tree %s to token %s (wallet=%s)", tree_record_id[:8], token_id[:8], wallet_address[:10])
    return binding_id


def unbind_tree(conn, binding_id: str, unbinding_tx_hash: str = None) -> bool:
    """Remove tree-token binding."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE tree_token_binding
        SET status = 'unbound', unbinding_date = CURRENT_DATE, unbinding_tx_hash = %s
        WHERE id = %s AND status = 'bound'
    """, (unbinding_tx_hash, binding_id))
    affected = cur.rowcount
    conn.commit()
    cur.close()
    return affected > 0


def get_tree_bound_tokens(conn, location_id: str) -> List[Dict[str, Any]]:
    """Query all bound tokens for a farm."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            ttb.id AS binding_id,
            ttb.token_id_onchain,
            ttb.wallet_address,
            ttb.binding_date,
            ttb.status,
            gt.symbol AS token_symbol,
            gt.chain AS token_chain,
            gt.contract_address,
            tr.species_name,
            tr.height_m,
            tr.dbh_cm,
            tr.health_score
        FROM tree_token_binding ttb
        JOIN governance_token gt ON gt.id = ttb.token_id
        JOIN tree_record tr ON tr.id = ttb.tree_record_id
        WHERE tr.location_id = %s AND ttb.status = 'bound'
        ORDER BY gt.symbol, ttb.binding_date
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return rows


def create_staking_position(
    conn,
    wallet_address: str,
    token_id: str,
    token_amount: float,
    lock_period_days: int = 90,
) -> str:
    """Record a staking position."""
    lock_end = datetime.now(timezone.utc).date() + timedelta(days=lock_period_days)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO staking_position (
            wallet_address, token_id, token_amount, lock_period_days,
            lock_start, lock_end, status
        ) VALUES (%s, %s, %s, %s, CURRENT_DATE, %s, 'active')
        RETURNING id
    """, (wallet_address, token_id, token_amount, lock_period_days, lock_end))
    position_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    logger.info("Staking position created: %s tokens, %d days lock", token_amount, lock_period_days)
    return position_id


def compute_yield(conn, epoch: str, location_id: str = None) -> Dict[str, Any]:
    """Compute yield distribution for an epoch from farm revenue."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get total staked tokens
    cur.execute("""
        SELECT COALESCE(SUM(token_amount), 0) AS total_staked
        FROM staking_position
        WHERE status IN ('active', 'locked')
    """)
    staked = float(cur.fetchone()["total_staked"] or 0)

    if staked <= 0:
        cur.close()
        return {"status": "error", "message": "No active staking positions"}

    # Get revenue for the epoch
    query = """
        SELECT COALESCE(SUM(amount), 0) AS total_revenue
        FROM revenue_event
        WHERE EXTRACT(YEAR FROM observation_date) = %s
    """
    params = [int(epoch)]
    if location_id:
        query += " AND location_id = %s"
        params.append(location_id)
    cur.execute(query, params)
    revenue = float(cur.fetchone()["total_revenue"] or 0)

    # Apply redistribution: operator gets share, rest goes to stakers
    # Use commons_redistribution_policy if available
    cur.execute("""
        SELECT operator_allocation_pct, commons_allocation_pct
        FROM commons_redistribution_policy
        WHERE status = 'active' LIMIT 1
    """)
    policy = cur.fetchone()
    operator_pct = float(policy["operator_allocation_pct"] or 30) / 100 if policy else 0.3
    staker_share = revenue * (1 - operator_pct)

    distribution_per_token = staker_share / staked if staked > 0 else 0

    cur.close()

    return {
        "epoch": epoch,
        "total_revenue_usd": round(revenue, 2),
        "operator_share_pct": round(operator_pct * 100, 1),
        "staker_share_usd": round(staker_share, 2),
        "total_staked_tokens": round(staked, 8),
        "distribution_per_token": round(distribution_per_token, 8),
    }


def get_token_balance(conn, wallet_address: str, token_id: str = None) -> Dict[str, Any]:
    """Get token balance (from snapshot or compute from bindings)."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Count bound trees as voting power
    query = """
        SELECT COUNT(*) AS bound_trees, gt.symbol, gt.chain, gt.contract_address
        FROM tree_token_binding ttb
        JOIN governance_token gt ON gt.id = ttb.token_id
        WHERE ttb.wallet_address = %s AND ttb.status = 'bound'
    """
    params = [wallet_address]
    if token_id:
        query += " AND ttb.token_id = %s"
        params.append(token_id)
    query += " GROUP BY gt.symbol, gt.chain, gt.contract_address"

    cur.execute(query, params)
    bindings = [dict(r) for r in cur.fetchall()]

    # Get staking
    cur.execute("""
        SELECT COALESCE(SUM(token_amount), 0) AS staked,
               COALESCE(SUM(accumulated_rewards), 0) AS rewards
        FROM staking_position
        WHERE wallet_address = %s AND status IN ('active', 'locked')
    """, (wallet_address,))
    staking = dict(cur.fetchone() or {})

    cur.close()

    total_bound = sum(int(b["bound_trees"]) for b in bindings)

    return {
        "wallet_address": wallet_address,
        "bound_trees": total_bound,
        "tokens_by_symbol": bindings,
        "staked_tokens": float(staking.get("staked", 0) or 0),
        "accumulated_rewards": float(staking.get("rewards", 0) or 0),
        "voting_power": total_bound,  # 1 tree = 1 vote
    }


def get_voting_power(conn, wallet_address: str) -> Dict[str, Any]:
    """Derive voting power from tree count and staking."""
    balance = get_token_balance(conn, wallet_address)

    # Voting power = bound trees + staked tokens (if unlocked)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT COALESCE(SUM(token_amount), 0) AS unlocked_staked
        FROM staking_position
        WHERE wallet_address = %s AND status = 'active'
        AND lock_end <= CURRENT_DATE
    """, (wallet_address,))
    unlocked = float(cur.fetchone()["unlocked_staked"] or 0)
    cur.close()

    voting_power = balance["bound_trees"] + int(unlocked)

    return {
        "wallet_address": wallet_address,
        "voting_power": voting_power,
        "bound_trees": balance["bound_trees"],
        "unlocked_staked": int(unlocked),
    }
