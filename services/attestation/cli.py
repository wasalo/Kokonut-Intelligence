"""EAS Attestation CLI for Kokonut Intelligence.

Usage:
    python3 -m services.attestation.cli schema register --name kokonut-mrv --chain celo
    python3 -m services.attestation.cli schema list
    python3 -m services.attestation.cli attest --schema 0x... --recipient 0x... --data '{}' --chain celo
    python3 -m services.attestation.cli offchain-attest --schema 0x... --recipient 0x... --data '{}' --chain celo
    python3 -m services.attestation.cli revoke --schema 0x... --uid 0x... --chain celo
    python3 -m services.attestation.cli query --uid 0x... --chain celo
    python3 -m services.attestation.cli info --chain celo
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kokonut EAS Attestation CLI",
        prog="python3 -m services.attestation.cli",
    )
    sub = parser.add_subparsers(dest="command")

    # --- schema ---
    schema_p = sub.add_parser("schema", help="Schema management")
    schema_sub = schema_p.add_subparsers(dest="schema_command")

    reg_p = schema_sub.add_parser("register", help="Register a Kokonut schema onchain")
    reg_p.add_argument("--name", required=True, help="Schema name (e.g. kokonut-mrv)")
    reg_p.add_argument("--chain", default="celo", help="Target chain (default: celo)")
    reg_p.add_argument("--resolver", default="", help="Resolver address (default: EAS_RESOLVER_ADDRESS env)")
    reg_p.add_argument("--private-key", default=None, help="Private key (default: ATTESTER_PRIVATE_KEY env)")

    schema_sub.add_parser("list", help="List available Kokonut schema definitions")

    get_p = schema_sub.add_parser("get", help="Get schema info from onchain")
    get_p.add_argument("--uid", required=True, help="Schema UID")
    get_p.add_argument("--chain", default="celo", help="Target chain")

    # --- attest ---
    att_p = sub.add_parser("attest", help="Create an onchain attestation")
    att_p.add_argument("--schema", required=True, help="Schema UID (0x...)")
    att_p.add_argument("--recipient", required=True, help="Recipient address")
    att_p.add_argument("--data", required=True, help="JSON data fields: [{name, type, value}, ...]")
    att_p.add_argument("--chain", default="celo", help="Target chain")
    att_p.add_argument("--revocable", action="store_true", default=True, help="Revocable (default: true)")
    att_p.add_argument("--ref-uid", default="", help="Reference attestation UID")
    att_p.add_argument("--private-key", default=None, help="Private key")

    # --- offchain-attest ---
    off_p = sub.add_parser("offchain-attest", help="Create a signed offchain attestation (no gas)")
    off_p.add_argument("--schema", required=True, help="Schema UID (0x...)")
    off_p.add_argument("--recipient", required=True, help="Recipient address")
    off_p.add_argument("--data", required=True, help="JSON data fields")
    off_p.add_argument("--chain", default="celo", help="Target chain")
    off_p.add_argument("--private-key", default=None, help="Private key")

    # --- revoke ---
    rev_p = sub.add_parser("revoke", help="Revoke an onchain attestation")
    rev_p.add_argument("--schema", required=True, help="Schema UID (0x...)")
    rev_p.add_argument("--uid", required=True, help="Attestation UID to revoke")
    rev_p.add_argument("--chain", default="celo", help="Target chain")
    rev_p.add_argument("--private-key", default=None, help="Private key")

    # --- query ---
    q_p = sub.add_parser("query", help="Query an attestation from onchain")
    q_p.add_argument("--uid", required=True, help="Attestation UID")
    q_p.add_argument("--chain", default="celo", help="Target chain")

    # --- info ---
    info_p = sub.add_parser("info", help="Show chain config and attester info")
    info_p.add_argument("--chain", default="celo", help="Target chain")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "schema":
            _handle_schema(args)
        elif args.command == "attest":
            _handle_attest(args)
        elif args.command == "offchain-attest":
            _handle_offchain_attest(args)
        elif args.command == "revoke":
            _handle_revoke(args)
        elif args.command == "query":
            _handle_query(args)
        elif args.command == "info":
            _handle_info(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _handle_schema(args: argparse.Namespace) -> None:
    if args.schema_command == "list":
        from .schemas import KOKONUT_SCHEMAS
        for name, defn in KOKONUT_SCHEMAS.items():
            print(f"  {name}")
            print(f"    Schema:    {defn['schema']}")
            print(f"    Revocable: {defn['revocable']}")
            print(f"    Type:      {defn['claim_type']}")
            print()

    elif args.schema_command == "register":
        from .publisher import register_kokonut_schemas
        from .schemas import KOKONUT_SCHEMAS
        if args.name not in KOKONUT_SCHEMAS:
            print(f"Unknown schema: {args.name}. Available: {list(KOKONUT_SCHEMAS)}", file=sys.stderr)
            sys.exit(1)
        results = register_kokonut_schemas(
            chain=args.chain,
            resolver_address=args.resolver,
            private_key=args.private_key,
        )
        print(json.dumps(results, indent=2))

    elif args.schema_command == "get":
        from .publisher import get_schema
        result = get_schema(args.uid, args.chain)
        print(json.dumps(result, indent=2))

    else:
        print("Usage: schema {list|register|get}", file=sys.stderr)
        sys.exit(1)


def _handle_attest(args: argparse.Namespace) -> None:
    from .publisher import publish_attestation
    data = json.loads(args.data)
    result = publish_attestation(
        schema_name=args.schema,
        recipient=args.recipient,
        data=data,
        chain=args.chain,
        private_key=args.private_key,
        revocable=args.revocable,
        ref_uid=args.ref_uid,
    )
    print(json.dumps(result, indent=2))


def _handle_offchain_attest(args: argparse.Namespace) -> None:
    from .offchain import sign_offchain_attestation
    data = json.loads(args.data)
    result = sign_offchain_attestation(
        schema_uid=args.schema,
        recipient=args.recipient,
        data=data,
        chain=args.chain,
        private_key=args.private_key,
    )
    print(json.dumps(result, indent=2, default=str))


def _handle_revoke(args: argparse.Namespace) -> None:
    from .publisher import revoke_attestation
    result = revoke_attestation(
        schema_name=args.schema,
        attestation_uid=args.uid,
        chain=args.chain,
        private_key=args.private_key,
    )
    print(json.dumps(result, indent=2))


def _handle_query(args: argparse.Namespace) -> None:
    from .publisher import get_attestation
    result = get_attestation(args.uid, args.chain)
    print(json.dumps(result, indent=2))


def _handle_info(args: argparse.Namespace) -> None:
    from .config import get_chain_config, KOKONUT_MULTISIG, ATTESTER_PRIVATE_KEY
    from .signer import EASSigner

    config = get_chain_config(args.chain)
    print(f"Chain: {args.chain}")
    print(f"Chain ID: {config['chain_id']}")
    print(f"RPC URL: {config['rpc_url']}")
    print(f"EAS: {config['eas_address']}")
    print(f"SchemaRegistry: {config['schema_registry_address']}")
    print(f"Explorer: {config['explorer']}")
    print(f"Kokonut Multisig: {KOKONUT_MULTISIG}")

    if ATTESTER_PRIVATE_KEY:
        try:
            signer = EASSigner(args.chain)
            print(f"Attester: {signer.address}")
            print(f"Balance: {signer.get_balance_eth():.6f} native token")
        except Exception as e:
            print(f"Attester: Error - {e}")
    else:
        print("Attester: Not configured (set ATTESTER_PRIVATE_KEY)")


if __name__ == "__main__":
    main()
