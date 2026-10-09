"""Traceability (batches, custody, provenance, certs) CLI.

Extracted from services.analytics.traceability so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_traceability --help
"""

from ..common.commands import CommandLine
from .traceability import (
    create_produce_batch,
    get_batch_provenance,
    get_batch_status,
    get_certification_status,
    get_cold_chain_log,
    list_batches,
    log_provenance_event,
    record_custody_transfer,
    record_food_safety,
    record_quality_inspection,
    trace_backward,
    trace_forward,
    verify_certification,
)

# ============================================================
# CLI
# ============================================================

cli = CommandLine("traceability", "Supply chain traceability")


def _cmd_create_batch(db, a):
    return create_produce_batch(
        db, a.location_id, a.crop, a.quantity,
        harvest_date=a.harvest_date, variety=a.variety,
        organic=a.organic, unit=a.unit,
        field_id=a.field_id, notes=a.notes,
    )


def _cmd_custody(db, a):
    return record_custody_transfer(
        db, a.batch_id, a.from_actor, a.to_actor,
        transfer_type=a.transfer_type, location=a.location,
        quantity=a.quantity, notes=a.notes,
    )


def _cmd_quality(db, a):
    return record_quality_inspection(
        db, a.batch_id, a.inspection_type, a.result,
        grade=a.grade, inspector=a.inspector, notes=a.notes,
    )


def _cmd_certification(db, a):
    return verify_certification(
        db, a.batch_id, a.cert_type, a.cert_number,
        a.issuer, expiry_date=a.expiry, notes=a.notes,
    )


def _cmd_provenance(db, a):
    return log_provenance_event(
        db, a.batch_id, a.event_type, a.actor,
        location=a.location, description=a.description,
        evidence_url=a.evidence_url,
    )


def _cmd_provenance_log(db, a):
    return get_batch_provenance(db, a.batch_id)


def _cmd_status(db, a):
    return get_batch_status(db, a.batch_id)


def _cmd_list(db, a):
    return list_batches(
        db, location_id=a.location_id,
        status=a.status, limit=a.limit,
    )


def _cmd_food_safety(db, a):
    return record_food_safety(
        db, a.batch_id, a.check_type, a.result,
        temperature=a.temperature, inspector=a.inspector,
        notes=a.notes,
    )


def _cmd_certs(db, a):
    return get_certification_status(db, a.location_id)


def _cmd_trace_forward(db, a):
    return trace_forward(db, a.batch_id)


def _cmd_trace_backward(db, a):
    return trace_backward(db, a.batch_id)


def _cmd_cold_chain(db, a):
    return get_cold_chain_log(db, a.batch_id)


cli.subcommand("create-batch", "Create produce batch") \
    .add("--location-id", required=True) \
    .add("--crop", required=True, help="Crop name") \
    .add("--quantity", type=float, required=True) \
    .add("--harvest-date", help="Harvest date YYYY-MM-DD") \
    .add("--variety") \
    .add("--organic", action="store_true") \
    .add("--unit", default="kg") \
    .add("--field-id") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_create_batch)

cli.subcommand("custody", "Record custody transfer") \
    .add("--batch-id", required=True) \
    .add("--from", dest="from_actor", required=True) \
    .add("--to", dest="to_actor", required=True) \
    .add("--type", dest="transfer_type", default="sale") \
    .add("--location") \
    .add("--quantity", type=float) \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_custody)

cli.subcommand("quality", "Record quality inspection") \
    .add("--batch-id", required=True) \
    .add("--type", dest="inspection_type", required=True) \
    .add("--result", required=True) \
    .add("--grade") \
    .add("--inspector") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_quality)

cli.subcommand("certification", "Verify certification") \
    .add("--batch-id", required=True) \
    .add("--type", dest="cert_type", required=True) \
    .add("--cert-number", required=True) \
    .add("--issuer", required=True) \
    .add("--expiry", help="Expiry date YYYY-MM-DD") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_certification)

cli.subcommand("provenance", "Log provenance event") \
    .add("--batch-id", required=True) \
    .add("--event", dest="event_type", required=True) \
    .add("--actor", required=True) \
    .add("--location") \
    .add("--description") \
    .add("--evidence-url") \
    .add("--json", action="store_true") \
    .run(_cmd_provenance)

cli.subcommand("provenance-log", "Get provenance chain") \
    .add("--batch-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_provenance_log)

cli.subcommand("status", "Get batch status") \
    .add("--batch-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_status)

cli.subcommand("list", "List batches") \
    .add("--location-id") \
    .add("--status") \
    .add("--limit", type=int, default=50) \
    .add("--json", action="store_true") \
    .run(_cmd_list)

cli.subcommand("food-safety", "Record food safety check") \
    .add("--batch-id", required=True) \
    .add("--type", dest="check_type", required=True) \
    .add("--result", required=True) \
    .add("--temperature", type=float) \
    .add("--inspector") \
    .add("--notes") \
    .add("--json", action="store_true") \
    .run(_cmd_food_safety)

cli.subcommand("certs", "Get certification status") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_certs)

cli.subcommand("trace-forward", "Trace downstream") \
    .add("--batch-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_trace_forward)

cli.subcommand("trace-backward", "Trace to origin") \
    .add("--batch-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_trace_backward)

cli.subcommand("cold-chain", "Get cold chain log") \
    .add("--batch-id", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_cold_chain)


def main(argv=None):
    return cli.run(argv)


if __name__ == "__main__":
    main()

