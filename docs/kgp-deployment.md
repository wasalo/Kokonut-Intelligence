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

`KGP_URI` is optional and defaults to `ipfs://kokonut-kgp/{id}.json`.

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

The upgrade key must have `UPGRADER_ROLE` on the proxy. Every upgrade requires a storage compatibility test and governance approval.

```bash
cd contracts
forge script script/UpgradeKokonutGuildPoints.s.sol:UpgradeKokonutGuildPoints \
  --rpc-url $GNOSIS_RPC_URL --broadcast --verify
```

Never upgrade the proxy by calling the implementation directly. The proxy address is the permanent public KGP address.
