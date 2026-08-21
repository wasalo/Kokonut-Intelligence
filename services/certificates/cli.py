"""CLI for certificate operations."""

from __future__ import annotations

import argparse
import sys

from services.common.cli import print_json
from services.common.database import get_connection
from services.common.cli import print_json

def cmd_generate(args):
    with get_connection() as conn:
        from services.certificates.generator import generate_certificate
        result = generate_certificate(conn, args.retirement_id)
        print_json(result)


def cmd_verify(args):
    with get_connection() as conn:
        from services.certificates.generator import verify_certificate
        result = verify_certificate(conn, args.certificate_number)
        print_json(result)


def cmd_list(args):
    with get_connection() as conn:
        result = conn.execute(
            conn.text(
                "SELECT id, certificate_number, retired_tonnes, beneficiary_name, status, issued_at "
                "FROM retirement_certificate WHERE location_id = :lid ORDER BY issued_at DESC"
            ),
            {"lid": args.location_id},
        ).mappings()
        certs = [dict(r) for r in result]
        for c in certs:
            print(f"  [{c['status']}] {c['certificate_number']} — {c['retired_tonnes']} tCO2e → {c['beneficiary_name']}")
        print(f"\n{len(certs)} certificates")


def main():
    parser = argparse.ArgumentParser(description="Certificate CLI")
    sub = parser.add_subparsers(dest="command")

    p_gen = sub.add_parser("generate", help="Generate retirement certificate")
    p_gen.add_argument("--retirement-id", required=True)
    p_gen.set_defaults(func=cmd_generate)

    p_verify = sub.add_parser("verify", help="Verify certificate")
    p_verify.add_argument("--certificate-number", required=True)
    p_verify.set_defaults(func=cmd_verify)

    p_list = sub.add_parser("list", help="List certificates")
    p_list.add_argument("--location-id", required=True)
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
