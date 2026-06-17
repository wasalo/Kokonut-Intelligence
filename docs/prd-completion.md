# PRD Completion Notes

This note tracks the PRD completion layer added on top of the existing Directus/PostgreSQL core.

## Implemented

- Common Data Schema support via `farm_registry_record`, including the 13 required farm onboarding fields from Kokonut documentation.
- Operational support tables for inventory, maintenance, and canonical revenue events: `inventory_event`, `maintenance_event`, `revenue_event`.
- Kokonut MRV event support via `mrv_event`, with ground, remote, and community payload slots.
- Privacy-preserving attestation request metadata via `attestation_request`, `private_payload_hash`, `payload_cid`, and `payload_hash`.
- Agent metadata tables: `agent_identity`, `agent_capability_manifest`, `agent_task`, and `agent_action_log`.
- Metric governance extensions on `metric_definition`: validation tests, report usage, deprecation policy, and definition state.
- Source lineage extensions for environmental and sensor evidence tables.
- Development-only local CID helper under `services/storage/`.
- Registry, MRV, attestation, and agent helper CLIs under `services/registry/`, `services/attestation/`, and `services/agents/`.
- EAS on Celo mainnet: 5 schemas registered, KokonutResolver deployed and owned by Kokonut multisig, attestation CLI supports onchain and offchain attestations.
- Pilot dApp session seed data and governed digital lego usage metrics for MVP Web3 engagement reporting.

## Lifecycle

Governed records use `draft`, `submitted`, `verified`, `published`, and `rejected`.

Payment, execution, attestation, agent, and export state are stored in explicit fields such as `payment_status`, `execution_status`, `agent_state`, `action_result`, `attestation_uid`, `tx_hash`, `attested_at`, and `revocation_date`.

## EAS Privacy Boundary

Private MRV evidence stays off-chain by default. This repository stores hashes, CIDs, request metadata, and public payload summaries only. The attestation CLI can sign and submit EAS transactions on Celo mainnet using the configured attester wallet.

For local development, `local://sha256/<hash>` CIDs are deterministic references to files in `.local-cid-store/`, which is ignored by Git.

## Agent Boundary

This repository stores agent metadata, capability manifests, task records, action logs, and governed data access patterns.

Contract identity, x402/ERC-8004 payments, escrow, marketplace routing, and reputation logic remain external and are attributed to `Kokonut-Agentic-Marketplace`.

## Deferred / External

Live dApp session ingestion, wallet-session analytics pipelines, agent contract identity, payments, escrow, marketplace routing, and reputation logic remain external to this repository. The current implementation includes pilot session data and governed metric support so MVP reporting can verify Web3 engagement without introducing marketplace/payment logic here.
