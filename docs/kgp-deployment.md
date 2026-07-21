# KGP Deployment

This guide covers the deployable KGP and operational Guild protocol workflow.
The repository supports Gnosis Chain and Chiado deployments, but a network is
not active merely because a Foundry script succeeds. Record verified addresses,
transactions, roles, deployment blocks, and indexer state in PostgreSQL before
calling a deployment active.

## Supported Networks

| Network | Chain ID | RPC variable | Explorer |
|---|---:|---|---|
| Gnosis | 100 | `GNOSIS_RPC_URL` | `https://gnosisscan.io` |
| Chiado | 10200 | `CHIADO_RPC_URL` | `https://blockscout.com/gnosis/chiado` |
| Anvil | 31337 | explicit `--rpc-url` | local node |

Gnosis and Chiado use xDAI for transaction fees. The KGP deployment script
accepts only Gnosis and Chiado. The operational Guild protocol and upgrade
scripts also accept Anvil for local smoke and upgrade testing.

## Deployment Components

Deploy and record these components separately:

1. `KokonutGuildRegistry`
2. `KokonutGuildDomain`
3. `KokonutTaskBoard`
4. `KokonutEvidenceReview`
5. `KokonutGuildGovernance`
6. KGP implementation
7. KGP ERC-1967 proxy
8. `KokonutGuildUpgradeTimelock`
9. PostgreSQL deployment and projection records
10. KGP/indexer cursor and address configuration

The operational Guild contracts are wired separately from KGP. KGP receives the
deployed domain registry address during initialization; the operational
protocol does not connect to or move funds from the Moloch treasury.

## Operational Guild Protocol Deployment

`DeployKokonutGuildProtocol.s.sol` deploys and wires the registry, domain
registry, task board, evidence review, and governance contracts:

```bash
cd contracts
forge script script/DeployKokonutGuildProtocol.s.sol:DeployKokonutGuildProtocol \
  --rpc-url "$CHIADO_RPC_URL" \
  --account "$DEPLOYER_ACCOUNT" \
  --sender "$GUILD_PROTOCOL_BOOTSTRAP" \
  --broadcast \
  --verify
```

The script requires:

```text
GUILD_PROTOCOL_BOOTSTRAP
GUILD_PROTOCOL_ADMIN
GUILD_PROTOCOL_ROLE_ADMIN
GUILD_PROTOCOL_GUILD_ADMIN
GUILD_PROTOCOL_DOMAIN_ADMIN
GUILD_PROTOCOL_TASK_ADMIN
GUILD_PROTOCOL_REVIEWER
GUILD_PROTOCOL_PROPOSER
GUILD_PROTOCOL_OBJECTOR
GUILD_PROTOCOL_EXECUTOR
```

For Anvil, operational role variables except bootstrap/admin can default to the
admin. For Chiado and Gnosis, all operational role values are explicit.

The broadcast sender must equal `GUILD_PROTOCOL_BOOTSTRAP`. Production
preconditions include:

- bootstrap differs from admin;
- role admin differs from bootstrap;
- admin is separate from operational roles;
- bootstrap does not retain operational roles after handoff.

The script:

- deploys all five contracts with bootstrap authority;
- wires the task board to evidence review;
- allowlists task/domain governance targets and selectors;
- grants configured administrators and operational roles;
- verifies evidence-review wiring and target permissions;
- revokes bootstrap administration and operational roles.

Record the returned registry, domain, task board, evidence review, and governance
addresses in the component columns of `kgp_protocol_deployment`.

### Local Anvil Smoke Test

```bash
anvil

cd contracts
GUILD_PROTOCOL_BOOTSTRAP=<anvil-deployer-address> \
GUILD_PROTOCOL_ADMIN=<admin-address> \
forge script script/DeployKokonutGuildProtocol.s.sol:DeployKokonutGuildProtocol \
  --rpc-url http://127.0.0.1:8545 \
  --account anvil \
  --sender <anvil-deployer-address> \
  --broadcast
```

## KGP Roles And Proxy Deployment

The KGP script requires:

```text
KGP_DEPLOYER
KGP_ADMIN
KGP_AWARDER
KGP_CLAIM_SIGNER
KGP_REVERSER
KGP_PAUSER
KGP_UPGRADER
KGP_DOMAIN_REGISTRY
```

Optional:

```text
KGP_URI
```

`KGP_URI` defaults to `ipfs://kokonut-kgp/{id}.json`.

`DeployKokonutGuildPoints.s.sol` checks that:

- the chain is Gnosis or Chiado;
- the deployer matches the Foundry broadcast sender;
- the deployer does not collide with privileged role addresses;
- the domain registry and its registry dependency contain code;
- the configured upgrader address contains code.

The script deploys a fresh implementation and an `ERC1967Proxy`, then calls
`initialize` with the configured roles, domain registry, and URI. It does not
deploy the upgrade timelock and does not itself verify that the upgrader code is
the intended timelock or that it already holds `UPGRADER_ROLE`.

There is a deployment-order constraint in the current scripts: the KGP script
requires `KGP_UPGRADER` to already contain code, while the timelock constructor
requires the approved KGP proxy to already contain code. The scripts do not
provide a turnkey CREATE2/predicted-proxy sequence to resolve this circular
dependency. Production operators must use an approved staged deployment
procedure or update the deployment tooling before broadcasting. Do not claim a
production deployment is complete until the final timelock/proxy binding and
`UPGRADER_ROLE` handoff have been verified.

Deploy KGP after the operational domain registry exists:

```bash
cd contracts
forge script script/DeployKokonutGuildPoints.s.sol:DeployKokonutGuildPoints \
  --rpc-url "$CHIADO_RPC_URL" \
  --account "$DEPLOYER_ACCOUNT" \
  --sender "$KGP_DEPLOYER" \
  --broadcast \
  --verify
```

The proxy address is the permanent public KGP address. The implementation
address is recorded for upgrade compatibility and deployment provenance.

## Upgrade Timelock

Deploy `KokonutGuildUpgradeTimelock` separately with:

```text
admin
proposer
executor
approvedProxy
```

The constructor rejects zero addresses, a zero delay, admin/proposer/executor
collisions, and a proxy without code. The timelock stores the approved proxy and
grants separate `PROPOSER_ROLE` and `EXECUTOR_ROLE` roles.

After the proxy/timelock deployment-order constraint is resolved, grant the
timelock `UPGRADER_ROLE` on the KGP proxy and revoke any temporary upgrade role
through the appropriate role-admin path.
Verify:

- timelock `approvedProxy()` equals the KGP proxy;
- the timelock has `UPGRADER_ROLE`;
- the deployment operator no longer has production upgrade authority;
- admin, proposer, and executor are separate durable authorities.

There is no repository deployment script for the timelock itself; use an
approved Foundry deployment procedure and record the resulting address.

## Mainnet Readiness

Before Gnosis deployment:

- run `forge test`;
- complete contract security review;
- complete Chiado deployment and upgrade rehearsal;
- verify all implementation, proxy, timelock, and component addresses;
- approve production roles through governance;
- initialize PostgreSQL deployment/projection records;
- initialize indexer cursor state;
- configure confirmed deployment block and contract address map;
- run a non-economic test award and reconcile it;
- verify canonical PostgreSQL balance against on-chain balances.

```bash
cd contracts
forge test
forge script script/DeployKokonutGuildPoints.s.sol:DeployKokonutGuildPoints \
  --rpc-url "$GNOSIS_RPC_URL" \
  --account "$DEPLOYER_ACCOUNT" \
  --sender "$KGP_DEPLOYER" \
  --broadcast \
  --verify
```

Do not describe the deployment as active until `kgp_protocol_deployment.status`
is set to `active` through the governed database workflow and the indexer has a
confirmed, reconciled starting point.

## Upgrades

The production upgrade path is:

1. Deploy the new UUPS implementation.
2. Run storage compatibility and contract tests.
3. Set `KGP_PROXY`, `KGP_TIMELOCK`, and `KGP_IMPLEMENTATION`.
4. Review upgrade calldata.
5. Queue through the timelock proposer.
6. Wait for the configured delay.
7. Execute through the separate timelock executor.
8. Verify proxy implementation, state preservation, roles, and reconciliation.

Queue an upgrade:

```bash
cd contracts
KGP_PROXY=<proxy-address> \
KGP_TIMELOCK=<timelock-address> \
KGP_IMPLEMENTATION=<implementation-address> \
KGP_UPGRADE_DATA=<optional-hex-calldata> \
forge script script/QueueKokonutGuildPointsUpgrade.s.sol:QueueKokonutGuildPointsUpgrade \
  --rpc-url "$GNOSIS_RPC_URL" \
  --account "$PROPOSER_ACCOUNT" \
  --sender "$PROPOSER_ADDRESS" \
  --broadcast
```

When `KGP_UPGRADE_DATA` is empty, the queue script encodes
`reinitializeDomainRegistry(KGP_DOMAIN_REGISTRY)`. This is intended for the
first migration from an implementation that did not yet have the domain
registry. Later upgrades require explicitly reviewed calldata.

Execute after the delay:

```bash
cd contracts
KGP_TIMELOCK=<timelock-address> \
KGP_UPGRADE_ID=<queued-upgrade-id> \
forge script script/ExecuteKokonutGuildPointsUpgrade.s.sol:ExecuteKokonutGuildPointsUpgrade \
  --rpc-url "$GNOSIS_RPC_URL" \
  --account "$EXECUTOR_ACCOUNT" \
  --sender "$EXECUTOR_ADDRESS" \
  --broadcast
```

The queue and execute scripts accept Anvil, Gnosis, and Chiado. The legacy
`UpgradeKokonutGuildPoints.s.sol` script is for controlled local/test use and
must not be used with a production EOA upgrader.

## PostgreSQL Deployment Record

Create a `kgp_protocol_deployment` record for each chain deployment. It stores:

- deployment key;
- chain ID and network name;
- KGP proxy and implementation addresses;
- contract version;
- deployment transaction and block;
- upgrade authority;
- registry, domain, task board, evidence review, and governance addresses;
- status: `planned`, `active`, `paused`, or `deprecated`;
- deployment metadata.

Reputation events reference the deployment. Chain events and indexer cursors
must also reference it so cross-chain projections cannot be mixed.

## Indexer Setup

The KGP indexer requires an initialized deployment and cursor:

```bash
python3 -m services.guilds.indexer \
  --once \
  --deployment-id UUID \
  --addresses-json '{"kgp":"0x...","registry":"0x...","domains":"0x...","tasks":"0x...","reviews":"0x...","governance":"0x..."}' \
  --chain-id 100 \
  --rpc-url "$GNOSIS_RPC_URL"
```

Alternatively provide one KGP address with `--contract-address`. The full
address map is required to project operational Guild events.

Environment controls:

```text
KGP_CONFIRMATIONS   default 12
KGP_BLOCK_BATCH     default 500
```

The CLI requires `--once` until a durable worker loop is enabled. Schedule
repeated scans with explicit retry, monitoring, and operator controls.

The indexer stores raw chain events, decodes allowlisted event signatures,
projects matching PostgreSQL records, and dead-letters events that do not match
a canonical record. It detects block-hash divergence, marks affected events
non-canonical, rewinds the cursor, resets projections, and replays canonical
events in block/log order.

## Post-Deployment Checks

Verify:

1. Proxy implementation address matches the recorded implementation.
2. Domain registry and Guild registry addresses are correct.
3. KGP roles match the approved role matrix.
4. Timelock approved proxy and KGP upgrader role are correct.
5. Operational protocol bootstrap roles were revoked.
6. Contract deployment records contain transaction hashes and blocks.
7. Indexer cursor chain ID and address identity checks pass.
8. A non-economic award/reversal or test projection reconciles end to end.
9. `v_kgp_canonical_balance` matches the intended on-chain projection.
10. No unexpected dead-letter events or integrity violations exist.

## References

- `contracts/script/DeployKokonutGuildProtocol.s.sol`
- `contracts/script/DeployKokonutGuildPoints.s.sol`
- `contracts/script/QueueKokonutGuildPointsUpgrade.s.sol`
- `contracts/script/ExecuteKokonutGuildPointsUpgrade.s.sol`
- `contracts/script/UpgradeKokonutGuildPoints.s.sol`
- `contracts/src/KokonutGuildUpgradeTimelock.sol`
- `schemas/postgres/317_kgp_protocol.sql`
- `schemas/postgres/318_guild_protocol_projection.sql`
- `schemas/postgres/319_guild_integrity_controls.sql`
- `services/guilds/indexer.py`
- `tests/test_kgp_service.py`
- `tests/test_guild_reorg.py`
