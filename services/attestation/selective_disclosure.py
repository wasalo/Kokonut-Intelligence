"""Selective disclosure via Merkle tree for EAS attestations."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from services.common.logging import get_logger

logger = get_logger("attestation.selective_disclosure")


def build_disclosure_tree(claim_data: dict[str, Any]) -> tuple[bytes, list[dict], list[bytes]]:
    """Build a Merkle tree from field-level claim data.

    Each leaf = keccak256(abi.encodePacked(fieldIndex, fieldName, fieldValueHash))

    Args:
        claim_data: Dict of field_name -> field_value

    Returns:
        (root_hash, leaves_info, leaf_hashes)
    """
    leaves = []
    leaf_hashes = []

    for idx, (name, value) in enumerate(sorted(claim_data.items())):
        value_str = json.dumps(value, sort_keys=True, default=str)
        value_hash = hashlib.sha256(value_str.encode()).digest()
        leaf_data = _encode_leaf(idx, name, value_hash)
        leaf_hash = hashlib.sha256(leaf_data).digest()

        leaves.append({
            "index": idx,
            "name": name,
            "value": value,
            "value_hash": value_hash.hex(),
            "leaf_hash": leaf_hash.hex(),
        })
        leaf_hashes.append(leaf_hash)

    root = _compute_root(leaf_hashes)

    return root, leaves, leaf_hashes


def generate_proof(
    leaf_hashes: list[bytes],
    leaf_index: int,
) -> tuple[list[bytes], list[int]]:
    """Generate a Merkle proof for a specific leaf.

    Returns:
        (proof_hashes, proof_indices) where proof_indices indicate
        0=left, 1=right sibling at each level
    """
    if leaf_index >= len(leaf_hashes):
        raise ValueError(f"Leaf index {leaf_index} out of range (tree has {len(leaf_hashes)} leaves)")

    proof = []
    indices = []
    current_level = list(leaf_hashes)
    current_index = leaf_index

    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            combined = _hash_pair(left, right)
            next_level.append(combined)

            if i == current_index or i + 1 == current_index:
                sibling = right if i == current_index else left
                proof.append(sibling)
                indices.append(0 if i == current_index else 1)

        current_level = next_level
        current_index //= 2

    return proof, indices


def verify_proof(
    root: bytes,
    leaf_hash: bytes,
    proof: list[bytes],
    proof_indices: list[int],
) -> bool:
    """Verify a Merkle proof.

    Args:
        root: Expected root hash
        leaf_hash: Hash of the leaf to verify
        proof: List of sibling hashes from leaf to root
        proof_indices: 0=left, 1=right at each level

    Returns:
        True if proof is valid
    """
    current = leaf_hash
    for sibling, idx in zip(proof, proof_indices):
        if idx == 0:
            current = _hash_pair(current, sibling)
        else:
            current = _hash_pair(sibling, current)

    return current == root


def prepare_disclosure_attestation(
    claim_data: dict[str, Any],
    disclose_fields: list[str] | None = None,
) -> dict:
    """Build a Merkle root and generate proofs for specified fields.

    Args:
        claim_data: Full claim data dict
        disclose_fields: Fields to generate proofs for (None = all)

    Returns:
        {"root": hex, "leaf_count": int,
         "disclosures": [{field, value, proof, proof_indices}, ...]}
    """
    root, leaves, leaf_hashes = build_disclosure_tree(claim_data)
    fields_to_disclose = disclose_fields or list(claim_data.keys())

    disclosures = []
    for leaf in leaves:
        if leaf["name"] in fields_to_disclose:
            proof, indices = generate_proof(leaf_hashes, leaf["index"])
            disclosures.append({
                "field": leaf["name"],
                "value": leaf["value"],
                "proof": [h.hex() for h in proof],
                "proof_indices": indices,
            })

    return {
        "root": root.hex(),
        "leaf_count": len(leaves),
        "disclosures": disclosures,
    }


def _encode_leaf(index: int, name: str, value_hash: bytes) -> bytes:
    """Encode a leaf as keccak256(abi.encodePacked(index, name, value_hash))."""
    name_bytes = name.encode("utf-8")
    return hashlib.sha256(
        index.to_bytes(32, "big") + name_bytes + value_hash
    ).digest()


def _hash_pair(left: bytes, right: bytes) -> bytes:
    """Hash two nodes together for the tree."""
    return hashlib.sha256(left + right).digest()


def _compute_root(leaves: list[bytes]) -> bytes:
    """Compute the Merkle root from a list of leaf hashes."""
    if not leaves:
        return b"\x00" * 32
    if len(leaves) == 1:
        return leaves[0]

    level = list(leaves)
    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            next_level.append(_hash_pair(left, right))
        level = next_level

    return level[0]
