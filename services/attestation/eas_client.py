"""EAS Client — Python wrapper for EAS contract interactions via web3.py."""

from __future__ import annotations

from typing import Any

from web3 import Web3
from web3.constants import ADDRESS_ZERO

from .config import get_chain_config, load_abi, DEFAULT_CHAIN, EAS_RESOLVER_ADDRESS
from .signer import EASSigner
from .schema_encoder import encode_data


class EASClient:
    """Client for interacting with EAS contracts on any supported chain."""

    def __init__(self, chain: str = DEFAULT_CHAIN, private_key: str | None = None):
        self.chain = chain
        self.config = get_chain_config(chain)
        self.signer = EASSigner(chain, private_key)

        eas_abi = load_abi("EAS")
        sr_abi = load_abi("SchemaRegistry")

        self.eas = self.signer.w3.eth.contract(
            address=Web3.to_checksum_address(self.config["eas_address"]),
            abi=eas_abi,
        )
        self.schema_registry = self.signer.w3.eth.contract(
            address=Web3.to_checksum_address(self.config["schema_registry_address"]),
            abi=sr_abi,
        )

    @property
    def attester_address(self) -> str:
        return self.signer.address

    def is_connected(self) -> bool:
        return self.signer.is_connected()

    # --- Schema Registration ---

    def register_schema(
        self,
        schema_text: str,
        resolver_address: str = "",
        revocable: bool = True,
    ) -> dict[str, Any]:
        """Register a new EAS schema onchain.

        Returns:
            {"schema_uid": str, "tx_hash": str, "block_number": int}
        """
        resolver = Web3.to_checksum_address(resolver_address) if resolver_address else ADDRESS_ZERO

        tx = self.schema_registry.functions.register(
            schema_text,
            resolver,
            revocable,
        ).build_transaction({
            "from": self.signer.address,
            "chainId": self.config["chain_id"],
        })

        receipt = self.signer.estimate_and_send(tx)

        logs = self.schema_registry.events.Registered().process_receipt(receipt)
        schema_uid = logs[0]["args"]["uid"].hex() if logs else ""

        return {
            "schema_uid": "0x" + schema_uid if schema_uid else "",
            "tx_hash": receipt["transactionHash"].hex(),
            "block_number": receipt["blockNumber"],
        }

    def get_schema(self, schema_uid: str) -> dict[str, Any]:
        """Retrieve schema info from onchain."""
        result = self.schema_registry.functions.getSchema(schema_uid).call()
        return {
            "uid": result[0].hex() if isinstance(result[0], bytes) else result[0],
            "resolver": result[1],
            "revocable": result[2],
            "schema": result[3],
        }

    # --- Onchain Attestation ---

    def attest(
        self,
        schema_uid: str,
        recipient: str,
        data: list[dict[str, Any]],
        revocable: bool = True,
        ref_uid: str = "",
        expiration_time: int = 0,
    ) -> dict[str, Any]:
        """Create an onchain attestation.

        Args:
            schema_uid: The schema UID to attest against.
            recipient: Address of the attestation recipient.
            data: List of {"name": str, "type": str, "value": Any} for SchemaEncoder.
            revocable: Whether the attestation can be revoked.
            ref_uid: Optional reference to another attestation UID.
            expiration_time: Unix timestamp for expiration (0 = no expiration).

        Returns:
            {"attestation_uid": str, "tx_hash": str, "block_number": int}
        """
        encoded_data = encode_data(data)
        ref = bytes.fromhex(ref_uid[2:]) if ref_uid else b"\x00" * 32

        tx = self.eas.functions.attest(
            {
                "schema": bytes.fromhex(schema_uid[2:]) if schema_uid.startswith("0x") else schema_uid,
                "data": {
                    "recipient": Web3.to_checksum_address(recipient),
                    "expirationTime": expiration_time,
                    "revocable": revocable,
                    "refUID": ref,
                    "data": encoded_data,
                    "value": 0,
                },
            }
        ).build_transaction({
            "from": self.signer.address,
            "chainId": self.config["chain_id"],
        })

        receipt = self.signer.estimate_and_send(tx)

        logs = self.eas.events.Attested().process_receipt(receipt)
        attestation_uid = logs[0]["args"]["uid"].hex() if logs else ""

        return {
            "attestation_uid": "0x" + attestation_uid if attestation_uid else "",
            "tx_hash": receipt["transactionHash"].hex(),
            "block_number": receipt["blockNumber"],
        }

    def multi_attest(
        self,
        attestations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create multiple attestations in a single transaction.

        Args:
            attestations: List of {"schema_uid", "recipient", "data", "revocable", "ref_uid", "expiration_time"}

        Returns:
            {"attestation_uids": list[str], "tx_hash": str, "block_number": int}
        """
        eas_attestations = []
        for att in attestations:
            encoded_data = encode_data(att["data"])
            ref = bytes.fromhex(att.get("ref_uid", "")[2:]) if att.get("ref_uid") else b"\x00" * 32
            eas_attestations.append({
                "schema": bytes.fromhex(att["schema_uid"][2:]) if att["schema_uid"].startswith("0x") else att["schema_uid"],
                "data": {
                    "recipient": Web3.to_checksum_address(att["recipient"]),
                    "expirationTime": att.get("expiration_time", 0),
                    "revocable": att.get("revocable", True),
                    "refUID": ref,
                    "data": encoded_data,
                    "value": 0,
                },
            })

        tx = self.eas.functions.multiAttest(eas_attestations).build_transaction({
            "from": self.signer.address,
            "chainId": self.config["chain_id"],
        })

        receipt = self.signer.estimate_and_send(tx)

        logs = self.eas.events.Attested().process_receipt(receipt)
        uids = ["0x" + log["args"]["uid"].hex() for log in logs]

        return {
            "attestation_uids": uids,
            "tx_hash": receipt["transactionHash"].hex(),
            "block_number": receipt["blockNumber"],
        }

    # --- Revocation ---

    def revoke(
        self,
        schema_uid: str,
        attestation_uid: str,
    ) -> dict[str, Any]:
        """Revoke an onchain attestation.

        Returns:
            {"tx_hash": str, "block_number": int}
        """
        tx = self.eas.functions.revoke(
            {
                "schema": bytes.fromhex(schema_uid[2:]) if schema_uid.startswith("0x") else schema_uid,
                "data": {
                    "uid": bytes.fromhex(attestation_uid[2:]) if attestation_uid.startswith("0x") else attestation_uid,
                    "value": 0,
                },
            }
        ).build_transaction({
            "from": self.signer.address,
            "chainId": self.config["chain_id"],
        })

        receipt = self.signer.estimate_and_send(tx)
        return {
            "tx_hash": receipt["transactionHash"].hex(),
            "block_number": receipt["blockNumber"],
        }

    # --- Queries ---

    def get_attestation(self, attestation_uid: str) -> dict[str, Any]:
        """Retrieve an attestation from onchain."""
        uid = bytes.fromhex(attestation_uid[2:]) if attestation_uid.startswith("0x") else attestation_uid
        result = self.eas.functions.getAttestation(uid).call()
        return {
            "uid": "0x" + result[0].hex(),
            "schema": "0x" + result[1].hex(),
            "time": result[2],
            "expirationTime": result[3],
            "revocationTime": result[4],
            "refUID": "0x" + result[5].hex(),
            "recipient": result[6],
            "attester": result[7],
            "revocable": result[8],
            "data": "0x" + result[9].hex(),
        }

    def is_valid_attestation(self, attestation_uid: str) -> bool:
        """Check if an attestation UID is valid onchain."""
        uid = bytes.fromhex(attestation_uid[2:]) if attestation_uid.startswith("0x") else attestation_uid
        return self.eas.functions.isAttestationValid(uid).call()
