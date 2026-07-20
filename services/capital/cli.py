"""Capital accounting CLI (Keynes-inspired, constructive only).

Read-only diagnostics plus DRAFT-only credit proposals. Settlement/redemption
are human-approved and out of scope here.
"""

from __future__ import annotations

import argparse

from services.capital import accounting_report, capacity, capture, credit, diversion
from services.common.cli import print_json, run
from services.common.database import get_db


def cmd_capacity(location_id: str) -> None:
    conn = get_db()
    try:
        out = capacity.assess_capacity(conn, location_id)
    finally:
        conn.close()
    print_json(out)


def cmd_diversion(location_id: str, period_start: str = None, period_end: str = None) -> None:
    conn = get_db()
    try:
        out = diversion.compute_diversion_index(conn, location_id, period_start, period_end)
    finally:
        conn.close()
    print_json(out)


def cmd_capture(location_id: str) -> None:
    conn = get_db()
    try:
        out = capture.capture_risk(conn, location_id)
    finally:
        conn.close()
    print_json(out)


def cmd_credit_propose(
    location_id: str,
    source_type: str,
    amount: float,
    unit: str = "usd",
    contributor: str = None,
    redeemable: str = "regenerative_investment",
    idempotency_key: str = None,
) -> None:
    conn = get_db()
    try:
        out = credit.propose_credit(
            conn, location_id, source_type, amount,
            unit=unit, contributor_party_id=contributor,
            redeemable_against=redeemable, idempotency_key=idempotency_key,
        )
        conn.commit()
    finally:
        conn.close()
    print_json(out)


def cmd_credit_list(location_id: str) -> None:
    conn = get_db()
    try:
        out = credit.list_draft_credits(conn, location_id)
    finally:
        conn.close()
    print_json(out)


def cmd_credit_capacity(location_id: str) -> None:
    conn = get_db()
    try:
        out = credit.credit_capacity(conn, location_id)
    finally:
        conn.close()
    print_json(out)


def cmd_report(location_id: str, period_start: str = None, period_end: str = None) -> None:
    conn = get_db()
    try:
        out = accounting_report.build_capital_accounting(conn, location_id, period_start, period_end)
    finally:
        conn.close()
    print_json(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Capital accounting (8 Forms of Capital, Keynes-inspired).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("capacity", help="Output-capacity & mobilization per Form of Capital.")
    pc.add_argument("--location-id", required=True)
    pc.set_defaults(func=lambda a: cmd_capacity(a.location_id))

    pd = sub.add_parser("diversion", help="Consumption-vs-reinvestment diversion index.")
    pd.add_argument("--location-id", required=True)
    pd.add_argument("--period-start", default=None)
    pd.add_argument("--period-end", default=None)
    pd.set_defaults(func=lambda a: cmd_diversion(a.location_id, a.period_start, a.period_end))

    pcap = sub.add_parser("capture", help="Value-leakage / capture-risk signal.")
    pcap.add_argument("--location-id", required=True)
    pcap.set_defaults(func=lambda a: cmd_capture(a.location_id))

    pcr = sub.add_parser("credit", help="Deferred regenerative credit ledger (DRAFT-only).")
    cr_sub = pcr.add_subparsers(dest="crcmd", required=True)
    cr_prop = cr_sub.add_parser("propose", help="Propose a DRAFT credit (withheld, deferred claim).")
    cr_prop.add_argument("--location-id", required=True)
    cr_prop.add_argument("--source-type", required=True,
                         choices=["carbon_credit_surplus", "cooperative_surplus", "federation_underwrite"])
    cr_prop.add_argument("--amount", type=float, required=True)
    cr_prop.add_argument("--unit", default="usd")
    cr_prop.add_argument("--contributor", default=None)
    cr_prop.add_argument("--redeemable", default="regenerative_investment",
                         choices=["regenerative_investment", "shared_dividend", "stewardship_grant"])
    cr_prop.add_argument("--idempotency-key", default=None)
    cr_prop.set_defaults(func=lambda a: cmd_credit_propose(
        a.location_id, a.source_type, a.amount, a.unit, a.contributor, a.redeemable, a.idempotency_key))
    cr_list = cr_sub.add_parser("list", help="List draft credits for a location.")
    cr_list.add_argument("--location-id", required=True)
    cr_list.set_defaults(func=lambda a: cmd_credit_list(a.location_id))
    cr_cap = cr_sub.add_parser("capacity", help="Read-only drafted-credit capacity (network deficit analog).")
    cr_cap.add_argument("--location-id", required=True)
    cr_cap.set_defaults(func=lambda a: cmd_credit_capacity(a.location_id))

    pr = sub.add_parser("report", help="Composite capital-accounting report.")
    pr.add_argument("--location-id", required=True)
    pr.add_argument("--period-start", default=None)
    pr.add_argument("--period-end", default=None)
    pr.set_defaults(func=lambda a: cmd_report(a.location_id, a.period_start, a.period_end))

    return p


def main() -> None:
    args = build_parser().parse_args()
    run(args.func, args)


if __name__ == "__main__":
    main()
