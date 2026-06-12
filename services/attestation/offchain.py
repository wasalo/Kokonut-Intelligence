"""Offchain EAS attestation signing and verification.

Creates EIP-712 signed offchain attestations that can be verified without gas.
"""

from __future__ import annotations

import time
from typing import Any

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3

from .config import get_chain_config, DEFAULT_CHAIN, ATTESTER_PRIVATE_KEY
from .schema_encoder import encode_data


EAS_DOMAIN_TYPEHASH = Web3.keccak(
    text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
)

ATTEST_TYPEHASH = Web3.keccak(
    text="Attest(bytes32 schema,address recipient,uint64 expirationTime,bool revocable,bytes32 refUID,bytes data,uint256 nonce)"
)


def _build_domain_separator(chain: str) -> bytes:
    """Build the EIP-712 domain separator for EAS."""
    config = get_chain_config(chain)
    return Web3.keccak(
        abi_encode(
            ["bytes32", "bytes32", "bytes32", "uint256", "address"],
            [
                EAS_DOMAIN_TYPEHASH,
                Web3.keccak(text="EAS Attestation"),
                Web3.keccak(text="0.26"),
                config["chain_id"],
                Web3.to_checksum_address(config["eas_address"]),
            ],
        )
    )


def sign_offchain_attestation(
    schema_uid: str,
    recipient: str,
    data: list[dict[str, Any]],
    chain: str = DEFAULT_CHAIN,
    private_key: str | None = None,
    revocable: bool = True,
    ref_uid: str = "",
    expiration_time: int = 0,
    nonce: int | None = None,
) -> dict[str, Any]:
    """Create a signed offchain attestation.

    Args:
        schema_uid: The schema UID.
        recipient: Address of the recipient.
        data: List of {"name": str, "type": str, "value": Any}.
        chain: Target chain name.
        private_key: Attester private key (falls back to env).
        revocable: Whether revocable.
        ref_uid: Reference attestation UID.
        expiration_time: Unix timestamp (0 = no expiration).
        nonce: Optional nonce (auto-generated if not provided).

    Returns:
        Signed attestation object with signature components.
    """
    key = private_key or ATTESTER_PRIVATE_KEY
    if not key:
        raise ValueError("No private key provided.")
    account: LocalAccount = Account.from_key(key)

    encoded_data = encode_data(data)
    ref = bytes.fromhex(ref_uid[2:]) if ref_uid else b"\x00" * 32
    schema = bytes.fromhex(schema_uid[2:]) if schema_uid.startswith("0x") else bytes.fromhex(schema_uid)

    if nonce is None:
        nonce = int(time.time() * 1000)

    domain_separator = _build_domain_separator(chain)

    struct_hash = Web3.keccak(
        abi_encode(
            ["bytes32", "bytes32", "address", "uint64", "bool", "bytes32", "bytes", "uint256"],
            [
                ATTEST_TYPEHASH,
                schema,
                Web3.to_checksum_address(recipient),
                expiration_time,
                revocable,
                ref,
                encoded_data,
                nonce,
            ],
        )
    )

    digest = Web3.keccak(b"\x19\x01" + domain_separator + struct_hash)
    signed = account.signHash(digest)

    return {
        "schema": schema_uid,
        "recipient": Web3.to_checksum_address(recipient),
        "expirationTime": expiration_time,
        "revocable": revocable,
        "refUID": ref_uid or "0x" + "00" * 32,
        "data": "0x" + encoded_data.hex(),
        "nonce": nonce,
        "time": int(time.time()),
        "signature": {
            "v": signed.v,
            "r": "0x" + signed.r.to_bytes(32, "big").hex(),
            "s": "0x" + signed.s.to_bytes(32, "big").hex(),
        },
        "attester": account.address,
        "chain": chain,
    }


def verify_offchain_attestation(
    attestation: dict[str, Any],
    expected_signer: str | None = None,
) -> bool:
    """Verify an offchain attestation signature.

    Args:
        attestation: The signed attestation object.
        expected_signer: Optional expected signer address.

    Returns:
        True if the signature is valid.
    """
    chain = attestation.get("chain", DEFAULT_CHAIN)
    domain_separator = _build_domain_separator(chain)

    schema = attestation["schema"]
    schema_bytes = bytes.fromhex(schema[2:]) if schema.startswith("0x") else bytes.fromhex(schema)
    ref_uid = attestation.get("refUID", "0x" + "00" * 32)
    ref = bytes.fromhex(ref_uid[2:]) if ref_uid.startswith("0x") else b"\x00" * 32
    data = attestation.get("data", "0x")
    data_bytes = bytes.fromhex(data[2:]) if data.startswith("0x") else b""

    struct_hash = Web3.keccak(
        abi_encode(
            ["bytes32", "bytes32", "address", "uint64", "bool", "bytes32", "bytes", "uint256"],
            [
                ATTEST_TYPEHASH,
                schema_bytes,
                Web3.to_checksum_address(attestation["recipient"]),
                attestation.get("expirationTime", 0),
                attestation.get("revocable", True),
                ref,
                data_bytes,
                attestation["nonce"],
            ],
        )
    )

    digest = Web3.keccak(b"\x19\x01" + domain_separator + struct_hash)

    sig = attestation["signature"]
    recovered = Account.recover_hash(digest, vrs=(sig["v"], int(sig["r"], 16), int(sig["s"], 16)))

    if expected_signer and recovered.lower() != expected_signer.lower():
        return False

    return recovered.lower() == attestation["attester"].lower()


def abi_encode(types: list[str], values: list[Any]) -> bytes:
    """Encode values using eth_abi."""
    from eth_abi import encode
    return encode(types, values)
