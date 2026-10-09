# credit_class

`services.credit_class` — Credit Class / Batch Hierarchy: Protocol methodology and issuance tracking.

## CLI Usage

```bash
python3 -m services.credit_class.cli --help
```

## Modules

- `balance` — Credit Balance: per-account balance tracking for tradable/retired/escrowed credits.
- `basket` — Credit Basket: deposit credits → receive fungible basket tokens.
- `batch_manager` — Credit batch management: issuance, retirement, and balance tracking.
- `bridge` — Cross-chain bridge: send/receive credits across chains.
- `class_manager` — Credit class management: methodology and protocol definitions.
- `cli` — CLI for credit class, batch, and entity operations.
- `enrollment` — Project Credit Class Enrollment: apply → approve/reject/terminate workflow.
- `entities` — Credit class entity management: cobenefits, registries, programs, protocols, methodologies, buffer pools.
- `fees` — Marketplace fee collection and distribution.
- `marketplace` — Credit Marketplace: sell orders, buy orders, escrow, fees.
- `params` — Ecocredit module parameters.

## Files

11 Python modules
