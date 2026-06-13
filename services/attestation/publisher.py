"""EAS attestation publisher — orchestrates onchain attestation from DB requests."""

from __future__ import annotations

from typing import Any

from .eas_client import EASClient
from .config import DEFAULT_CHAIN, KOKONUT_MULTISIG, EAS_RESOLVER_ADDRESS
from .schemas import KOKONUT_SCHEMAS


def register_kokonut_schemas(
    chain: str = DEFAULT_CHAIN,
    resolver_address: str = "",
    private_key: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Register all Kokonut schemas onchain and return UID mappings.

    Returns:
        {"kokonut-mrv": {"schema_uid": "0x...", "tx_hash": "0x..."}, ...}
    """
    client = EASClient(chain, private_key)
    resolver = resolver_address or EAS_RESOLVER_ADDRESS
    results = {}

    for name, definition in KOKONUT_SCHEMAS.items():
        print(f"Registering schema: {name}")
        result = client.register_schema(
            schema_text=definition["schema"],
            resolver_address=resolver,
            revocable=definition["revocable"],
        )
        results[name] = result
        print(f"  UID: {result['schema_uid']}")
        print(f"  TX:  {result['tx_hash']}")

    return results


def publish_attestation(
    schema_name: str,
    recipient: str,
    data: list[dict[str, Any]],
    chain: str = DEFAULT_CHAIN,
    private_key: str | None = None,
    revocable: bool = True,
    ref_uid: str = "",
) -> dict[str, Any]:
    """Publish an onchain attestation for a named Kokonut schema.

    Returns:
        {"attestation_uid": str, "tx_hash": str, "block_number": int}
    """
    client = EASClient(chain, private_key)
    schema_uid = _resolve_schema_uid(schema_name, chain)

    return client.attest(
        schema_uid=schema_uid,
        recipient=recipient,
        data=data,
        revocable=revocable,
        ref_uid=ref_uid,
    )


def publish_batch(
    attestations: list[dict[str, Any]],
    chain: str = DEFAULT_CHAIN,
    private_key: str | None = None,
) -> dict[str, Any]:
    """Publish multiple attestations in a single transaction.

    Args:
        attestations: List of {"schema_name", "recipient", "data", "revocable", "ref_uid"}

    Returns:
        {"attestation_uids": list[str], "tx_hash": str, "block_number": int}
    """
    client = EASClient(chain, private_key)

    resolved = []
    for att in attestations:
        att["schema_uid"] = _resolve_schema_uid(att["schema_name"], chain)
        resolved.append(att)

    return client.multi_attest(resolved)


def revoke_attestation(
    schema_name: str,
    attestation_uid: str,
    chain: str = DEFAULT_CHAIN,
    private_key: str | None = None,
) -> dict[str, Any]:
    """Revoke an onchain attestation.

    Returns:
        {"tx_hash": str, "block_number": int}
    """
    client = EASClient(chain, private_key)
    schema_uid = _resolve_schema_uid(schema_name, chain)
    return client.revoke(schema_uid, attestation_uid)


def get_attestation(
    attestation_uid: str,
    chain: str = DEFAULT_CHAIN,
) -> dict[str, Any]:
    """Retrieve an attestation from onchain."""
    client = EASClient(chain)
    return client.get_attestation(attestation_uid)


def get_schema(
    schema_uid: str,
    chain: str = DEFAULT_CHAIN,
) -> dict[str, Any]:
    """Retrieve schema info from onchain."""
    client = EASClient(chain)
    return client.get_schema(schema_uid)


def _resolve_schema_uid(schema_name: str, chain: str) -> str:
    """Resolve a schema name to its UID. For now, raises if not registered."""
    if schema_name.startswith("0x"):
        return schema_name
    raise ValueError(
        f"Schema '{schema_name}' not yet registered on {chain}. "
        f"Run 'python3 -m services.attestation.cli schema register --name {schema_name} --chain {chain}' first."
    )
