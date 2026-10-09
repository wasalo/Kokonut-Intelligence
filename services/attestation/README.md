# attestation

`services.attestation` — Attestation request preparation helpers.

## CLI Usage

```bash
python3 -m services.attestation
```
```bash
python3 -m services.attestation.cli --help
```

## Modules

- `cli` — EAS Attestation CLI for Kokonut Intelligence.
- `config` — EAS chain configuration for Kokonut Intelligence.
- `eas_client` — EAS Client — Python wrapper for EAS contract interactions via web3.py.
- `offchain` — Offchain EAS attestation signing and verification.
- `payload` — Prepare privacy-preserving EAS attestation request payloads.
- `publisher` — EAS attestation publisher — orchestrates onchain attestation from DB requests.
- `schema_encoder` — EAS SchemaEncoder — encodes/decodes attestation data for EAS schemas.
- `schemas` — Kokonut EAS schema definitions for Celo and multi-chain attestation.
- `signer` — Wallet/signer management for EAS attestation transactions.
- `contracts/` — sub-package

## Files

10 Python modules
