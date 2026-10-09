# Gnosis Mainnet Deployment

Chain ID: `100`

## Deployed Contracts

| Component | Address | Deployment transaction |
|---|---|---|
| Guild Registry | `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad` | `0xc4bfbfdf73327fefc12356f2d348ec698b437155a23ad36d87efe17ce43dad7d` |
| Guild Domain | `0x45dC48FEC5f145020bB84e7d39bc4B2FED166d01` | `0x2863309fbfd66041952c22e020a59602ee60168167ba57e0c3fd40e7f344c234` |
| Task Board | `0x2319bc674eeA617990bc40e44a98b6856C358801` | `0x9e609190c4fcd545e4284903ea344aeb9988be981cf2ef84ea3ee395f35caed9` |
| Evidence Review | `0x48Ae65bed10d8F9B6E952bb7091c14CCe9AB64De` | `0x43437017c0d66db268f82cf03650d56f44ff29e62c1a36013430a761344f3d2b` |
| Guild Governance | `0x9aEBAbF4e85b831aDba53eE62eA939A22b93F4fc` | `0x620ee78e7e0941e06e560621f3ee6726f703e42c378e1163d7e69d14673ee75d` |
| KGP implementation | `0x3F9E600d3bC211dfDb80147fdb05Ad5d44AE02c2` | `0xe3d50c1c78629b89992b214fd626e326104093fe59a4e4130af959f7f8d30e3b` |
| KGP proxy | `0x136247fCad81c4BE6560754AF440D7B1A320516f` | `0x3d7cbfdc16c32dad6262176a714d674587e5844e5e7cefcbd27c5918d33f965d` |
| KGP upgrade timelock | `0xefAeF01B3DDeF2041A1dbdCEbcA352eD2240920A` | `0x7b1c59b53fd59c3e6bc33a2513f9316bdba5300cf66324b53ccb3e503556caeb` |
| Credit Token implementation | `0xDf4D764526d6b9537C9E6414fFade4d9a6A2c648` | `0x2e8d513685f8bac3a18113fa4546f74caa368b85e8ad2ff62afe2b49c585735b` |
| Credit Token proxy | `0x26Cc52596279D568e7A340DB16e1E24eFa5b95d3` | `0x19154bbbdf05babf78ef589091b64e8fc04ae68c9c0ec417a71840f6b56d04a1` |
| Credit Token ProxyAdmin | `0xD95b21385257BcE512B22f6d7F22dC1d64b3d0F7` | `0x32b0c88630476079107a270258b7c6e1378c77cd41415869f706390a1873ac99` |
| Selective Disclosure implementation | `0x14293D31c15594bcB03d6581d26FF9353a882884` | `0xdffa7728da1ca79c9bfe85d8a50c14da851654b73fb146397b877ecea518cdb3` |
| Selective Disclosure proxy | `0x964b0d0B02965654491e9F8265772165B8fE4562` | `0x5fb133e0fef434cb7d5673d131b3f98bd258a0fe6711a7cd4849aee306453b13` |
| Price Oracle implementation | `0x78B1697D3C25bE6F165e8Ed359FF313F381DA3f0` | `0x351ac9041af21f5031e90eddeb0173824242fefe5f7a55094d5c66387e37693c` |
| Price Oracle proxy | `0xA6D24A665FB2f41C07c54b145034576e9BC6826a` | `0x818eae4ee8d1c29e1ba3065b144e2f04e81889f4a532cee1ea323898c139f305` |

## KGP Authority Handoff

The KGP proxy was initially deployed with a temporary upgrader because the
timelock must bind to the proxy address. The temporary upgrader then performed
the role handoff directly because `UPGRADER_ROLE` is self-administered by the
KGP contract; the Protocol Admin multisig is not the role administrator.

| Action | Transaction | Block |
|---|---|---:|
| Grant `UPGRADER_ROLE` to timelock | `0x93ce23efd4b81cd4bbe9e65e4989121be2ac309962bc1c75575ab21fdba142dd` | 47406899 |
| Revoke `UPGRADER_ROLE` from temporary EOA | `0x3c545ad99cdbed25804162b80d502462781bd36608b5d5c6136a12579f7f0841` | 47406919 |

Final verification:

- Timelock `approvedProxy()` equals `0x136247fCad81c4BE6560754AF440D7B1A320516f`.
- Timelock `minDelay` is `172800` seconds (48 hours).
- Timelock has `UPGRADER_ROLE` on the KGP proxy.
- Temporary upgrader `0x0ea26051F7657d59418da186137141CeA90D0652` no longer has `UPGRADER_ROLE`.

## Authority Matrix

| Authority | Address | Scope |
|---|---|---|
| Protocol Admin multisig | `0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5` | Default administration and Credit Token ProxyAdmin ownership |
| Guild role admin | `0x50AFcd6CE9E3aE15ae5731FF8c1d255289ca203B` | Guild protocol role administration and evidence review |
| Domain/task admin | `0x50b4d652a69F2a67Ee1fb7C383Ab1125Bdc93fCb` | Domains, tasks, KGP awards, and selective disclosure attestation |
| Governance proposer | `0x318C9bAfa423Aa5869FFd7CC61F3A6D7e4fa21a6` | Guild governance proposals |
| Governance objector | `0x5893f4cfD15edd8B7E92D436043Ab48F343D6559` | Guild governance objections |
| Governance executor | `0x5c3a27860ed28C28007b385963d07353b2825417` | Guild governance execution |
| Emergency pauser/oracle updater | `0xe09B0f3ad5b3789820d6945D41Bf3a317e6E2De9` | Pause controls, Credit Token burning, and price updates |
| Credit issuer | `0xf8D008aEbf360104E900664D7cc31A0cf0C0963a` | Credit issuance |
| KGP claim signer | `0xd58bB7Ae72B5b2FDc980C908baB75013a3628820` | KGP voucher signing |
| KGP reverser | `0xba55C7eb8EEE6aE6e5645Ac982c4a25859862f07` | KGP reversals |
| Upgrade proposer | `0xb122E6C7C36944dB10aD86D6c05A08f33AD4a9B9` | Queue KGP upgrades |
| Upgrade executor | `0x8cEA432e1be2C2E060fb05E3B015eDd3d581A983` | Execute delayed KGP upgrades |

## Verification

All Gnosis deployments are verified through the Etherscan-compatible GnosisScan
verifier, including implementations, ERC1967 proxies, the Transparent proxy, and
ProxyAdmin. Public verification records are retained in
`contracts/broadcast/*/100/run-latest.json`.

No implementation upgrade transaction has been executed yet. The recorded
onchain changes are deployments, initialization, role handoff, and timelock
configuration.
