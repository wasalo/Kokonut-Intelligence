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
KGP_DEPLOYER
KGP_ADMIN
KGP_AWARDER
KGP_CLAIM_SIGNER
KGP_REVERSER
KGP_PAUSER
KGP_UPGRADER
KGP_DOMAIN_REGISTRY
```

`KGP_URI` is optional and defaults to `ipfs://kokonut-kgp/{id}.json`. `KGP_UPGRADER` must be a deployed `KokonutGuildUpgradeTimelock` contract on Gnosis and Chiado, and `KGP_DOMAIN_REGISTRY` must be the deployed Guild domain registry.

Deploy `KokonutGuildUpgradeTimelock` with the KGP proxy as its approved proxy argument. The constructor arguments are `admin`, `proposer`, `executor`, `delay`, and `KGP_PROXY`; the resulting timelock address is then supplied as `KGP_UPGRADER`.

The deployer is selected with Foundry's `--account`/`--sender` options and must match `KGP_DEPLOYER`. Production role addresses should be multisigs, governance-controlled accounts, or dedicated rotated service keys. The deployment script rejects a deployer/role collision and requires the timelock contract as `UPGRADER_ROLE`.

## Chiado

```bash
cd contracts
GNOSIS_RPC_URL=https://rpc.gnosischain.com \
CHIADO_RPC_URL=https://rpc.chiadochain.net \
forge script script/DeployKokonutGuildPoints.s.sol:DeployKokonutGuildPoints \
  --rpc-url $CHIADO_RPC_URL --account $DEPLOYER_ACCOUNT --sender $DEPLOYER_ADDRESS --broadcast --verify
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
  --rpc-url $GNOSIS_RPC_URL --account $DEPLOYER_ACCOUNT --sender $DEPLOYER_ADDRESS --broadcast --verify
```

## Upgrade

Production upgrades are queued and executed through `KokonutGuildUpgradeTimelock`, which is bound to the approved KGP proxy at deployment. The timelock address must hold `UPGRADER_ROLE`; the proposer and executor are separate Foundry accounts. Set `KGP_IMPLEMENTATION` to an already deployed implementation, then run each script with the appropriate `--account`/`--sender`. For the first upgrade from a pre-domain-registry implementation, omit `KGP_UPGRADE_DATA` and provide `KGP_DOMAIN_REGISTRY`; the queue script atomically calls `reinitializeDomainRegistry`. For later upgrades, provide reviewed calldata in `KGP_UPGRADE_DATA`. Every upgrade requires a storage compatibility test, governance approval, and the configured delay.

```bash
cd contracts
forge script script/QueueKokonutGuildPointsUpgrade.s.sol:QueueKokonutGuildPointsUpgrade \
  --rpc-url $GNOSIS_RPC_URL --account $PROPOSER_ACCOUNT --sender $PROPOSER_ADDRESS --broadcast
forge script script/ExecuteKokonutGuildPointsUpgrade.s.sol:ExecuteKokonutGuildPointsUpgrade \
  --rpc-url $GNOSIS_RPC_URL --account $EXECUTOR_ACCOUNT --sender $EXECUTOR_ADDRESS --broadcast
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

For Chiado and Gnosis, `GUILD_PROTOCOL_BOOTSTRAP` is the temporary bootstrap address and must differ from `GUILD_PROTOCOL_ADMIN`. Select the broadcaster with Foundry's `--account`/`--sender`; the script wires the contracts, grants the configured production roles, verifies the handoff, and revokes bootstrap administration. Set explicit values for `GUILD_PROTOCOL_ADMIN`, `GUILD_PROTOCOL_GUILD_ADMIN`, `GUILD_PROTOCOL_DOMAIN_ADMIN`, `GUILD_PROTOCOL_TASK_ADMIN`, `GUILD_PROTOCOL_REVIEWER`, `GUILD_PROTOCOL_PROPOSER`, `GUILD_PROTOCOL_OBJECTOR`, and `GUILD_PROTOCOL_EXECUTOR`.

For local Anvil smoke testing:

```bash
anvil
GUILD_PROTOCOL_BOOTSTRAP=<anvil-deployer-address> \
GUILD_PROTOCOL_ADMIN=<admin-address> \
forge script script/DeployKokonutGuildProtocol.s.sol:DeployKokonutGuildProtocol \
  --rpc-url http://127.0.0.1:8545 --account anvil --sender <anvil-deployer-address> --broadcast
```
