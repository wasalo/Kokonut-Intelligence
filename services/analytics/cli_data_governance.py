"""Data governance (consent, portability, retention) CLI.

Extracted from services.analytics.data_governance so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_data_governance --help
"""

from datetime import datetime

from ..common.commands import CommandLine
from .data_governance import (
    check_consent,
    create_sharing_agreement,
    enforce_retention_policies,
    fulfill_portability,
    get_access_audit,
    get_consent_status,
    get_governance_summary,
    get_portability_requests,
    get_sharing_agreements,
    log_access,
    record_consent,
    request_portability,
    set_retention_policy,
    withdraw_consent,
)

# ==
# CLI
# ============================================================

cli = CommandLine("data_governance", "Data governance & interoperability")


def _cmd_record_consent(db, a):
    exp = datetime.fromisoformat(a.expires_at) if a.expires_at else None
    return record_consent(
        db, a.farmer_id, a.data_category, a.scope,
        status=a.status, method=a.method,
        location_id=a.location_id, expires_at=exp,
        evidence_ref=a.evidence_ref, legal_basis=a.legal_basis,
    )


def _cmd_log_access(db, a):
    return log_access(
        db, a.accessor_id, a.data_category, a.resource_type,
        a.access_type, purpose=a.purpose,
        resource_id=a.resource_id, location_id=a.location_id,
        accessor_role=a.accessor_role, accessor_type=a.accessor_type,
        access_method=a.access_method, consent_id=a.consent_id,
        status=a.status, denial_reason=a.denial_reason,
        records_affected=a.records_affected,
    )


def _cmd_request_portability(db, a):
    cats = a.data_categories.split(",") if a.data_categories else None
    return request_portability(
        db, a.farmer_id, format_type=a.format_type,
        scope=a.scope, data_categories=cats,
        location_id=a.location_id,
        requested_by=a.requested_by,
        authorization_ref=a.authorization_ref,
        include_metadata=a.include_metadata,
    )


def _cmd_fulfill_portability(db, a):
    return fulfill_portability(
        db, a.request_id, file_path=a.file_path,
        output_hash=a.output_hash,
        output_size_bytes=a.output_size,
        record_count=a.record_count,
        owner_id=a.owner_id,
        fulfilled_by=a.fulfilled_by,
        authorization_ref=a.authorization_ref,
    )


def _cmd_create_agreement(db, a):
    cats = a.data_categories.split(",")
    return create_sharing_agreement(
        db, a.provider_id, a.consumer_id, cats, a.purpose,
        provider_type=a.provider_type, consumer_type=a.consumer_type,
        legal_basis=a.legal_basis, commercial_use=a.commercial_use,
        retention_days=a.retention_days,
    )


def _cmd_set_retention(db, a):
    return set_retention_policy(
        db, a.data_category, a.retention_days,
        action=a.action, entity_type=a.entity_type,
        location_id=a.location_id, policy_owner=a.policy_owner,
    )


cli.subcommand("record-consent", "Record consent grant/withdrawal") \
    .add("--farmer-id", required=True) \
    .add("--data-category", required=True) \
    .add("--scope", required=True) \
    .add("--status", default="granted", choices=["granted", "withdrawn", "pending"]) \
    .add("--method", default="digital_form") \
    .add("--location-id") \
    .add("--expires-at", help="Expiry datetime ISO format") \
    .add("--evidence-ref") \
    .add("--legal-basis") \
    .add("--json", action="store_true") \
    .run(_cmd_record_consent)

cli.subcommand("withdraw-consent", "Withdraw consent") \
    .add("--consent-id", required=True) \
    .add("--reason") \
    .add("--actor-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: withdraw_consent(db, a.consent_id, reason=a.reason, actor_id=a.actor_id))

cli.subcommand("consent-status", "Get consent status per category") \
    .add("--farmer-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_consent_status(db, a.farmer_id))

cli.subcommand("check-consent", "Check specific consent") \
    .add("--farmer-id", required=True) \
    .add("--data-category", required=True) \
    .add("--scope", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: check_consent(db, a.farmer_id, a.data_category, a.scope))

cli.subcommand("log-access", "Log data access event") \
    .add("--accessor-id", required=True) \
    .add("--data-category", required=True) \
    .add("--resource-type", required=True) \
    .add("--access-type", required=True,
         choices=["read", "write", "export", "share", "delete", "list", "aggregate", "download"]) \
    .add("--purpose") \
    .add("--resource-id") \
    .add("--location-id") \
    .add("--accessor-role") \
    .add("--accessor-type", default="user") \
    .add("--access-method") \
    .add("--consent-id") \
    .add("--status", default="success", choices=["success", "denied", "partial", "error"]) \
    .add("--denial-reason") \
    .add("--records-affected", type=int, default=0) \
    .add("--json", action="store_true") \
    .run(_cmd_log_access)

cli.subcommand("access-audit", "Get access audit trail") \
    .add("--farmer-id", required=True) \
    .add("--days", type=int, default=30) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_access_audit(db, a.farmer_id, days=a.days))

cli.subcommand("request-portability", "Request data export") \
    .add("--farmer-id", required=True) \
    .add("--format", dest="format_type", default="json",
         choices=["json", "csv", "geojson", "xml", "rdf_turtle", "jsonld", "parquet", "excel"]) \
    .add("--scope", default="all", choices=["all", "location", "category", "filtered"]) \
    .add("--data-categories", help="Comma-separated categories") \
    .add("--location-id") \
    .add("--requested-by") \
    .add("--authorization-ref") \
    .add("--include-metadata", action="store_true", default=True) \
    .add("--json", action="store_true") \
    .run(_cmd_request_portability)

cli.subcommand("fulfill-portability", "Mark portability request as fulfilled") \
    .add("--request-id", required=True) \
    .add("--file-path") \
    .add("--output-hash") \
    .add("--output-size", type=int) \
    .add("--record-count", type=int, default=0) \
    .add("--owner-id", required=True) \
    .add("--fulfilled-by", required=True) \
    .add("--authorization-ref", required=True) \
    .add("--json", action="store_true") \
    .run(_cmd_fulfill_portability)

cli.subcommand("portability-requests", "List portability requests") \
    .add("--farmer-id", required=True) \
    .add("--actor-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_portability_requests(db, a.farmer_id, actor_id=a.actor_id))

cli.subcommand("create-agreement", "Create data sharing agreement") \
    .add("--provider-id", required=True) \
    .add("--consumer-id", required=True) \
    .add("--data-categories", required=True, help="Comma-separated categories") \
    .add("--purpose", required=True) \
    .add("--provider-type", default="farmer") \
    .add("--consumer-type", default="organization") \
    .add("--legal-basis") \
    .add("--commercial-use", action="store_true") \
    .add("--retention-days", type=int) \
    .add("--json", action="store_true") \
    .run(_cmd_create_agreement)

cli.subcommand("sharing-agreements", "List sharing agreements") \
    .add("--farmer-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_sharing_agreements(db, a.farmer_id))

cli.subcommand("set-retention", "Set retention policy") \
    .add("--data-category", required=True) \
    .add("--retention-days", type=int, required=True) \
    .add("--action", default="soft_delete",
         choices=["soft_delete", "hard_delete", "anonymize", "archive", "none"]) \
    .add("--entity-type") \
    .add("--location-id") \
    .add("--policy-owner") \
    .add("--json", action="store_true") \
    .run(_cmd_set_retention)

cli.subcommand("enforce-retention", "Run governed retention sweep") \
    .add("--actor", required=True) \
    .add("--dry-run", action="store_true") \
    .add("--json", action="store_true") \
    .run(lambda db, a: enforce_retention_policies(db, a.actor, dry_run=a.dry_run))

cli.subcommand("governance-summary", "Aggregated governance metrics") \
    .add("--location-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_governance_summary(db, a.location_id))


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()

