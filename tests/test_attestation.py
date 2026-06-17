"""Tests for EAS attestation module — schema encoder, config, CLI parsing."""

import json
import subprocess
import sys


def test_schema_encoder_roundtrip():
    """Test that schema encoder can encode and decode data."""
    from services.attestation.schema_encoder import encode_data, decode_data, parse_schema

    schema_text = "string locationId, uint256 quantity, bool compliant"
    fields = parse_schema(schema_text)
    assert len(fields) == 3
    assert fields[0]["name"] == "locationId"
    assert fields[0]["type"] == "string"

    data = [
        {"name": "locationId", "type": "string", "value": "loc-001"},
        {"name": "quantity", "type": "uint256", "value": 1500},
        {"name": "compliant", "type": "bool", "value": True},
    ]
    encoded = encode_data(data)
    assert isinstance(encoded, bytes)
    assert len(encoded) > 0

    decoded = decode_data(schema_text, encoded)
    assert decoded[0]["value"] == "loc-001"
    assert decoded[1]["value"] == 1500
    assert decoded[2]["value"] is True


def test_schema_encoder_types():
    """Test encoding of various EAS types."""
    from services.attestation.schema_encoder import encode_data

    data = [
        {"name": "addr", "type": "address", "value": "0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5"},
        {"name": "val", "type": "int256", "value": -42},
        {"name": "hash", "type": "bytes32", "value": "0x" + "ab" * 32},
        {"name": "text", "type": "string", "value": "hello"},
    ]
    encoded = encode_data(data)
    assert isinstance(encoded, bytes)


def test_chain_config():
    """Test chain configuration lookup."""
    from services.attestation.config import get_chain_config, EAS_CHAIN_CONFIG

    celo = get_chain_config("celo")
    assert celo["chain_id"] == 42220
    assert celo["eas_address"] == "0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92"

    optimism = get_chain_config("optimism")
    assert optimism["chain_id"] == 10

    try:
        get_chain_config("unsupported")
        assert False, "Should have raised"
    except ValueError:
        pass


def test_kokonut_schemas():
    """Test Kokonut schema definitions."""
    from services.attestation.schemas import KOKONUT_SCHEMAS, list_schemas, get_schema_text

    schemas = list_schemas()
    assert "kokonut-mrv" in schemas
    assert "kokonut-impact" in schemas
    assert "kokonut-financial" in schemas
    assert "kokonut-harvest" in schemas
    assert "kokonut-compliance" in schemas

    mrv = get_schema_text("kokonut-mrv")
    assert "locationId" in mrv
    assert "string" in mrv


def test_cli_help():
    """Test CLI help commands."""
    result = subprocess.run(
        [sys.executable, "-m", "services.attestation.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "schema" in result.stdout
    assert "attest" in result.stdout
    assert "offchain-attest" in result.stdout


def test_cli_schema_list():
    """Test CLI schema list command."""
    result = subprocess.run(
        [sys.executable, "-m", "services.attestation.cli", "schema", "list"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "kokonut-mrv" in result.stdout
    assert "kokonut-impact" in result.stdout


def test_cli_info():
    """Test CLI info command."""
    result = subprocess.run(
        [sys.executable, "-m", "services.attestation.cli", "info", "--chain", "celo"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "42220" in result.stdout
    assert "0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92" in result.stdout


def test_schema_db_name_mapping():
    """Test CLI schema keys map to database display names."""
    from services.attestation.schemas import SCHEMA_DB_NAMES, KOKONUT_SCHEMAS

    assert SCHEMA_DB_NAMES["kokonut-mrv"] == "Kokonut MRV"
    assert len(SCHEMA_DB_NAMES) == len(KOKONUT_SCHEMAS)


def test_abi_files_exist():
    """Test that ABI files are present."""
    from pathlib import Path
    contracts_dir = Path("services/attestation/contracts")
    assert (contracts_dir / "EAS.json").exists()
    assert (contracts_dir / "SchemaRegistry.json").exists()

    eas_abi = json.loads((contracts_dir / "EAS.json").read_text())
    assert len(eas_abi) > 0

    sr_abi = json.loads((contracts_dir / "SchemaRegistry.json").read_text())
    assert len(sr_abi) > 0


def test_public_payload_rejects_sensitive_keys():
    """Public attestation metadata must not carry private evidence fields."""
    from services.attestation.payload import prepare_attestation_request

    try:
        prepare_attestation_request(
            "mrv_claim",
            "claim-1",
            "mrv",
            {"payload_hash": "abc", "private_payload": {"secret": "raw"}},
        )
        assert False, "Should reject private public payload fields"
    except ValueError as exc:
        assert "sensitive/private" in str(exc)


def test_public_payload_accepts_hash_metadata():
    """Hash/CID metadata remains allowed in public attestation payloads."""
    from services.attestation.payload import prepare_attestation_request

    request = prepare_attestation_request(
        "mrv_claim",
        "claim-1",
        "mrv",
        {"payload_hash": "abc", "payload_cid": "local://sha256/abc"},
        private_payload={"raw_evidence": "kept private"},
    )
    assert request["private_payload_hash"]
    assert "private_payload" not in request


if __name__ == "__main__":
    tests = [
        test_schema_encoder_roundtrip,
        test_schema_encoder_types,
        test_chain_config,
        test_kokonut_schemas,
        test_cli_help,
        test_cli_schema_list,
        test_cli_info,
        test_schema_db_name_mapping,
        test_abi_files_exist,
        test_public_payload_rejects_sensitive_keys,
        test_public_payload_accepts_hash_metadata,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n  Pass: {passed}/{passed + failed}")
    if failed:
        sys.exit(1)
    print("  All attestation tests passed ✓")
