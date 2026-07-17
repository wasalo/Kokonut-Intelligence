# KGP Deployment

KGP is deployed as a UUPS proxy with a separately deployed implementation. Production deployment targets Gnosis Chain; Chiado is used for integration and upgrade testing.

## Networks

| Network | Chain ID | RPC variable | Explorer |
| --- | ---: | --- | --- |
| Gnosis | 100 | `GNOSIS_RPC_URL` | `https://gnosisscan.io` |
| Chiado | 10200 | `CHIADO_RPC_URL` | `https://blockscout.com/gnosis/chiado` |

Both networks use xDAI for transaction fees.

## Deployment Roles

The deployment script requires explicit values for every role:

```text
KGP_DEPLOYER_PRIVATE_KEY
KGP_ADMIN
KGP_AWARDER
KGP_CLAIM_SIGNER
KGP_REVERSER
KGP_PAUSER
KGP_UPGRADER
```

`KGP_URI` is optional and defaults to `ipfs://kokonut-kgp/{id}.json`. `KGP_UPGRADER` must be a deployed `KokonutGuildUpgradeTimelock` contract on Gnosis and Chiado.

The deployer only broadcasts the deployment. Production role addresses should be multisigs, governance-controlled accounts, or dedicated rotated service keys. The deployer must not retain `UPGRADER_ROLE` unless explicitly approved.

## Chiado

```bash
cd contracts
GNOSIS_RPC_URL=https://rpc.gnosischain.com \
CHIADO_RPC_URL=https://rpc.chiadochain.net \
forge script script/DeployKokonutGuildPoints.s.sol:DeployKokonutGuildPoints \
  --rpc-url $CHIADO_RPC_URL --broadcast --verify
```

Before broadcasting, confirm that the configured role addresses are intentional and that the deployer has enough Chiado xDAI for deployment gas.

## Gnosis Mainnet

Mainnet deployment requires:

- Passing `forge test` and contract security review.
- A successful Chiado deployment and upgrade test.
- Verified deployment artifacts and addresses.
- Explicit governance approval for the production role configuration.
- A PostgreSQL `kgp_protocol_deployment` record.
- Indexer configuration with a confirmed deployment block.
- A non-economic test award followed by reconciliation.

```bash
cd contracts
forge script script/DeployKokonutGuildPoints.s.sol:DeployKokonutGuildPoints \
  --rpc-url $GNOSIS_RPC_URL --broadcast --verify
```

## Upgrade

Production upgrades are queued and executed through `KokonutGuildUpgradeTimelock`. The timelock address must hold `UPGRADER_ROLE`; the proposer and executor keys are separate operational authorities. Every upgrade requires a storage compatibility test, governance approval, and the configured delay.

```bash
cd contracts
forge script script/QueueKokonutGuildPointsUpgrade.s.sol:QueueKokonutGuildPointsUpgrade \
  --rpc-url $GNOSIS_RPC_URL --broadcast
forge script script/ExecuteKokonutGuildPointsUpgrade.s.sol:ExecuteKokonutGuildPointsUpgrade \
  --rpc-url $GNOSIS_RPC_URL --broadcast
```

`UpgradeKokonutGuildPoints.s.sol` is retained for controlled local/test use only. Never use it with a production EOA upgrader. Never upgrade the proxy by calling the implementation directly; the proxy address is the permanent public KGP address.

## Guild Protocol Deployment

The operational Guild contracts are deployed and wired separately from KGP:

```bash
cd contracts
forge script script/DeployKokonutGuildProtocol.s.sol:DeployKokonutGuildProtocol \
  --rpc-url $CHIADO_RPC_URL --broadcast --verify
```

The deployment creates and wires the registry, domain registry, task board, evidence review, and operational governance contracts. It does not connect to or move funds from the Moloch treasury.

For Chiado and Gnosis, `GUILD_PROTOCOL_DEPLOYER_PRIVATE_KEY` is a temporary bootstrap key. The script deploys with that key, wires the contracts, grants the configured production roles, verifies the handoff, and revokes bootstrap administration. Set distinct production values for `GUILD_PROTOCOL_ADMIN`, `GUILD_PROTOCOL_GUILD_ADMIN`, `GUILD_PROTOCOL_DOMAIN_ADMIN`, `GUILD_PROTOCOL_TASK_ADMIN`, `GUILD_PROTOCOL_REVIEWER`, `GUILD_PROTOCOL_PROPOSER`, `GUILD_PROTOCOL_OBJECTOR`, and `GUILD_PROTOCOL_EXECUTOR`; do not rely on the local-development defaults.

For local Anvil smoke testing:

```bash
anvil
GUILD_PROTOCOL_DEPLOYER_PRIVATE_KEY=<anvil-key> \
GUILD_PROTOCOL_ADMIN=<admin-address> \
forge script script/DeployKokonutGuildProtocol.s.sol:DeployKokonutGuildProtocol \
  --rpc-url http://127.0.0.1:8545 --broadcast
```
