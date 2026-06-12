"""EAS SchemaEncoder — encodes/decodes attestation data for EAS schemas.

Port of @ethereum-attestation-service/eas-sdk SchemaEncoder.
"""

from __future__ import annotations

import re
from typing import Any

from eth_abi import encode as abi_encode
from eth_abi import decode as abi_decode
from web3 import Web3


# EAS type mapping: schema type string → ABI type
TYPE_MAP = {
    "bool": "bool",
    "uint8": "uint8",
    "uint16": "uint16",
    "uint32": "uint32",
    "uint64": "uint64",
    "uint128": "uint128",
    "uint256": "uint256",
    "int8": "int8",
    "int16": "int16",
    "int32": "int32",
    "int64": "int64",
    "int128": "int128",
    "int256": "int256",
    "address": "address",
    "string": "string",
    "bytes": "bytes",
    "bytes32": "bytes32",
}


def parse_schema(schema_text: str) -> list[dict[str, str]]:
    """Parse an EAS schema string into field definitions.

    Example:
        "string locationId, uint256 quantity, bool compliant"
        → [{"name": "locationId", "type": "string"}, {"name": "quantity", "type": "uint256"}, ...]
    """
    fields = []
    for part in schema_text.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if len(tokens) < 2:
            raise ValueError(f"Invalid schema field: {part}")
        type_name = tokens[0]
        field_name = tokens[1]
        if type_name not in TYPE_MAP:
            raise ValueError(f"Unsupported EAS type: {type_name}. Supported: {list(TYPE_MAP)}")
        fields.append({"name": field_name, "type": type_name})
    return fields


def encode_data(fields: list[dict[str, Any]]) -> bytes:
    """Encode field values into ABI-encoded bytes for EAS.

    Args:
        fields: List of {"name": str, "type": str, "value": Any}

    Returns:
        ABI-encoded bytes.
    """
    abi_types = []
    values = []
    for field in fields:
        type_name = field["type"]
        abi_type = TYPE_MAP.get(type_name)
        if not abi_type:
            raise ValueError(f"Unsupported type: {type_name}")
        abi_types.append(abi_type)
        values.append(_normalize_value(type_name, field["value"]))

    return abi_encode(abi_types, values)


def decode_data(schema_text: str, encoded: bytes) -> list[dict[str, Any]]:
    """Decode ABI-encoded attestation data using a schema text.

    Returns:
        List of {"name": str, "type": str, "value": Any}
    """
    fields = parse_schema(schema_text)
    abi_types = [TYPE_MAP[f["type"]] for f in fields]
    decoded = abi_decode(abi_types, encoded)
    result = []
    for i, field in enumerate(fields):
        value = decoded[i]
        if isinstance(value, bytes):
            value = "0x" + value.hex()
        result.append({"name": field["name"], "type": field["type"], "value": value})
    return result


def _normalize_value(type_name: str, value: Any) -> Any:
    """Normalize a Python value for ABI encoding."""
    if type_name == "bool":
        return bool(value)
    if type_name.startswith("uint") or type_name.startswith("int"):
        return int(value)
    if type_name == "address":
        return Web3.to_checksum_address(str(value))
    if type_name == "string":
        return str(value)
    if type_name == "bytes32":
        if isinstance(value, str) and value.startswith("0x"):
            return bytes.fromhex(value[2:].zfill(64))
        if isinstance(value, bytes):
            return value.ljust(32, b"\x00")[:32]
        return Web3.keccak(text=str(value))
    if type_name == "bytes":
        if isinstance(value, str) and value.startswith("0x"):
            return bytes.fromhex(value[2:])
        if isinstance(value, bytes):
            return value
        return str(value).encode()
    return value
