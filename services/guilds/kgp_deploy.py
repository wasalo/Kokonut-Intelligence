"""KGP deployment orchestration for Gnosis mainnet."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from services.common.logging import get_logger

logger = get_logger("guilds.kgp_deploy")

KGP_CONTRACTS = [
    "KokonutGuildRegistry",
    "KokonutGuildDomain",
    "KokonutTaskBoard",
    "KokonutEvidenceReview",
    "KokonutGuildGovernance",
    "KokonutGuildUpgradeTimelock",
    "KokonutGuildPoints",
]


def record_deployment(
    conn,
    chain: str,
    deployer_address: str,
    deployment_results: dict[str, str],
    multisig_address: str = None,
) -> dict:
    """Record KGP deployment results in the database.

    Args:
        conn: Database connection
        chain: Target chain (e.g., 'gnosis')
        deployer_address: Address that deployed the contracts
        deployment_results: Mapping of contract name -> deployed address
        multisig_address: Optional multisig to transfer ownership to

    Returns:
        Deployment record with id and status
    """
    result = conn.execute(
        conn.text(
            "INSERT INTO kgp_protocol_deployment "
            "(chain, deployer_address, deployed_contracts, multisig_address, status, deployed_at) "
            "VALUES (:chain, :deployer, :contracts, :multisig, 'deployed', NOW()) "
            "RETURNING id"
        ),
        {
            "chain": chain,
            "deployer": deployer_address,
            "contracts": json.dumps(deployment_results),
            "multisig": multisig_address,
        },
    ).mappings().first()

    logger.info(
        "Recorded KGP deployment %s on chain %s with %d contracts",
        result["id"], chain, len(deployment_results),
    )

    return {
        "id": str(result["id"]),
        "chain": chain,
        "status": "deployed",
        "contracts": deployment_results,
    }


def get_deployment(conn, deployment_id: str) -> dict | None:
    """Get a deployment record by ID."""
    result = conn.execute(
        conn.text("SELECT * FROM kgp_protocol_deployment WHERE id = :did"),
        {"did": deployment_id},
    ).mappings().first()
    return dict(result) if result else None


def list_deployments(conn, chain: str = None) -> list[dict]:
    """List all KGP deployments, optionally filtered by chain."""
    conditions = ["1=1"]
    params: dict = {}
    if chain:
        conditions.append("chain = :chain")
        params["chain"] = chain

    where = "WHERE " + " AND ".join(conditions)
    result = conn.execute(
        conn.text(f"SELECT * FROM kgp_protocol_deployment {where} ORDER BY deployed_at DESC"),
        params,
    )
    return [dict(r) for r in result.mappings()]


def verify_deployment(conn, chain: str) -> dict:
    """Verify that all KGP contracts are deployed on the given chain.

    Returns:
        {"chain": str, "contracts_found": int, "contracts_expected": int,
         "all_deployed": bool, "missing": list[str]}
    """
    deployment = conn.execute(
        conn.text(
            "SELECT deployed_contracts FROM kgp_protocol_deployment "
            "WHERE chain = :chain AND status = 'deployed' "
            "ORDER BY deployed_at DESC LIMIT 1"
        ),
        {"chain": chain},
    ).mappings().first()

    if not deployment:
        return {
            "chain": chain,
            "contracts_found": 0,
            "contracts_expected": len(KGP_CONTRACTS),
            "all_deployed": False,
            "missing": KGP_CONTRACTS,
        }

    deployed = json.loads(deployment["deployed_contracts"]) if isinstance(
        deployment["deployed_contracts"], str
    ) else deployment["deployed_contracts"]

    missing = [name for name in KGP_CONTRACTS if name not in deployed or not deployed[name]]

    return {
        "chain": chain,
        "contracts_found": len(KGP_CONTRACTS) - len(missing),
        "contracts_expected": len(KGP_CONTRACTS),
        "all_deployed": len(missing) == 0,
        "missing": missing,
    }
