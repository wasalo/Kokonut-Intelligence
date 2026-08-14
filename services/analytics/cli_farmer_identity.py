"""Farmer identity registry (profiles, KYC, roles, consent) CLI.

Extracted from services.analytics.farmer_identity so the domain module stays focused on
queries/business logic. Reachable via:

    python -m services.analytics.cli_farmer_identity --help
"""

from ..common.commands import CommandLine
from .farmer_identity import (
    add_credential,
    assign_role,
    create_kyc,
    create_profile,
    record_data_sharing_consent,
    register_device,
    update_profile,
    verify_kyc,
)

# ============================================================
# CLI
# ============================================================

cli = CommandLine("farmer_identity", "Farmer identity & access management")


def _cmd_create_profile(db, a):
    dob = date.fromisoformat(a.dob) if a.dob else None
    return create_profile(
        db, a.first_name,
        last_name=a.last_name,
        date_of_birth=dob,
        gender=a.gender,
        phone=a.phone,
        email=a.email,
        national_id_type=a.national_id_type,
        national_id_number=a.national_id_number,
        national_id_country=a.national_id_country,
        location_id=a.location_id,
        village=a.village,
        district=a.district,
        province=a.province,
        country=a.country,
        postal_code=a.postal_code,
        farm_size_ha=a.farm_size,
        primary_crops=a.crops,
        farming_type=a.farming_type,
        years_farming=a.years_farming,
    )


def _cmd_update_profile(db, a):
    updates = {}
    for field in ("first_name", "last_name", "gender", "phone", "email",
                  "national_id_type", "national_id_number", "national_id_country",
                  "village", "district", "province", "country", "postal_code",
                  "farming_type", "status"):
        val = getattr(a, field.replace("-", "_"), None)
        if val is not None:
            updates[field] = val
    if a.dob:
        updates["date_of_birth"] = date.fromisoformat(a.dob)
    if a.farm_size is not None:
        updates["farm_size_ha"] = a.farm_size
    if a.crops is not None:
        updates["primary_crops"] = a.crops
    if a.years_farming is not None:
        updates["years_farming"] = a.years_farming
    return update_profile(db, a.farmer_id, updates)


def _cmd_add_credential(db, a):
    issued = date.fromisoformat(a.issued_date) if a.issued_date else None
    expiry = date.fromisoformat(a.expiry_date) if a.expiry_date else None
    return add_credential(
        db, a.farmer_id, a.credential_type, a.credential_name,
        issuing_authority=a.issuing_authority,
        credential_number=a.credential_number,
        credential_url=a.credential_url,
        issued_date=issued,
        expiry_date=expiry,
    )


def _cmd_create_kyc(db, a):
    return create_kyc(
        db, a.farmer_id, a.verification_method,
        document_type=a.document_type,
        document_url=a.document_url,
        document_hash=a.document_hash,
        provider=a.provider,
        did_identifier=a.did_identifier,
        credential_jwt=a.credential_jwt,
    )


def _cmd_verify_kyc(db, a):
    return verify_kyc(
        db, a.kyc_id, a.status,
        verified_by=a.verified_by,
        notes=a.notes,
        confidence_score=a.confidence,
    )


def _cmd_assign_role(db, a):
    expires = datetime.fromisoformat(a.expires_at) if a.expires_at else None
    return assign_role(
        db, a.farmer_id, a.role,
        scope=a.scope,
        location_id=a.location_id,
        permissions=a.permissions,
        expires_at=expires,
        assigned_by=a.assigned_by,
    )


def _cmd_record_consent(db, a):
    return record_data_sharing_consent(
        db, a.farmer_id, a.data_type, a.recipient_type,
        recipient_id=a.recipient_id,
        recipient_name=a.recipient_name,
        purpose=a.purpose,
        legal_basis=a.legal_basis,
        retention_days=a.retention_days,
        is_reciprocal=a.reciprocal,
        consent_given=not a.no_consent,
        data_scope=a.data_scope,
    )


def _cmd_register_device(db, a):
    return register_device(
        db, a.farmer_id, a.device_id, a.device_type,
        location_id=a.location_id,
        device_name=a.device_name,
        os_type=a.os_type,
        os_version=a.os_version,
        app_version=a.app_version,
        has_camera=a.camera,
        has_gps=a.gps,
        has_offline=not a.no_offline,
        storage_mb=a.storage_mb,
    )


cli.subcommand("create-profile", "Create farmer profile") \
    .add("--first-name", required=True) \
    .add("--last-name") \
    .add("--dob", help="Date of birth YYYY-MM-DD") \
    .add("--gender") \
    .add("--phone") \
    .add("--email") \
    .add("--national-id-type") \
    .add("--national-id-number") \
    .add("--national-id-country") \
    .add("--location-id") \
    .add("--village") \
    .add("--district") \
    .add("--province") \
    .add("--country") \
    .add("--postal-code") \
    .add("--farm-size", type=float, help="Farm size in hectares") \
    .add("--crops", nargs="+", help="Primary crops") \
    .add("--farming-type") \
    .add("--years-farming", type=int) \
    .add("--json", action="store_true") \
    .run(_cmd_create_profile)

cli.subcommand("update-profile", "Update farmer profile") \
    .add("--farmer-id", required=True) \
    .add("--first-name") \
    .add("--last-name") \
    .add("--dob", help="Date of birth YYYY-MM-DD") \
    .add("--gender") \
    .add("--phone") \
    .add("--email") \
    .add("--national-id-type") \
    .add("--national-id-number") \
    .add("--national-id-country") \
    .add("--village") \
    .add("--district") \
    .add("--province") \
    .add("--country") \
    .add("--postal-code") \
    .add("--farm-size", type=float) \
    .add("--crops", nargs="+") \
    .add("--farming-type") \
    .add("--years-farming", type=int) \
    .add("--status") \
    .add("--json", action="store_true") \
    .run(_cmd_update_profile)

cli.subcommand("get-profile", "Get farmer profile") \
    .add("--farmer-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_profile(db, a.farmer_id))

cli.subcommand("list-farmers", "List farmers") \
    .add("--location-id") \
    .add("--status", default="active") \
    .add("--limit", type=int, default=100) \
    .add("--offset", type=int, default=0) \
    .add("--json", action="store_true") \
    .run(lambda db, a: list_farmers(db, a.location_id, a.status, a.limit, a.offset))

cli.subcommand("add-credential", "Add credential") \
    .add("--farmer-id", required=True) \
    .add("--type", required=True, dest="credential_type") \
    .add("--name", required=True, dest="credential_name") \
    .add("--issuing-authority") \
    .add("--number", dest="credential_number") \
    .add("--url", dest="credential_url") \
    .add("--issued-date", help="Issued date YYYY-MM-DD") \
    .add("--expiry-date", help="Expiry date YYYY-MM-DD") \
    .add("--json", action="store_true") \
    .run(_cmd_add_credential)

cli.subcommand("verify-credential", "Verify credential") \
    .add("--credential-id", required=True) \
    .add("--verified-by") \
    .add("--json", action="store_true") \
    .run(lambda db, a: verify_credential(db, a.credential_id, a.verified_by))

cli.subcommand("get-credentials", "Get credentials") \
    .add("--farmer-id", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_credentials(db, a.farmer_id))

cli.subcommand("create-kyc", "Create KYC record") \
    .add("--farmer-id", required=True) \
    .add("--method", required=True, dest="verification_method") \
    .add("--document-type") \
    .add("--document-url") \
    .add("--document-hash") \
    .add("--provider") \
    .add("--did-identifier") \
    .add("--credential-jwt") \
    .add("--json", action="store_true") \
    .run(_cmd_create_kyc)

cli.subcommand("verify-kyc", "Verify KYC") \
    .add("--kyc-id", required=True) \
    .add("--status", required=True, choices=["approved", "rejected"]) \
    .add("--verified-by") \
    .add("--notes") \
    .add("--confidence", type=float) \
    .add("--json", action="store_true") \
    .run(_cmd_verify_kyc)

cli.subcommand("assign-role", "Assign role") \
    .add("--farmer-id", required=True) \
    .add("--role", required=True) \
    .add("--scope", default="location") \
    .add("--location-id") \
    .add("--permissions", nargs="+") \
    .add("--expires-at", help="ISO datetime") \
    .add("--assigned-by") \
    .add("--json", action="store_true") \
    .run(_cmd_assign_role)

cli.subcommand("check-permission", "Check permission") \
    .add("--farmer-id", required=True) \
    .add("--resource", required=True) \
    .add("--action", required=True) \
    .add("--json", action="store_true") \
    .run(lambda db, a: check_permission(db, a.farmer_id, a.resource, a.action))

cli.subcommand("record-consent", "Record data sharing consent") \
    .add("--farmer-id", required=True) \
    .add("--data-type", required=True) \
    .add("--recipient-type", required=True) \
    .add("--recipient-id") \
    .add("--recipient-name") \
    .add("--purpose") \
    .add("--legal-basis", default="consent") \
    .add("--retention-days", type=int, default=365) \
    .add("--reciprocal", action="store_true") \
    .add("--no-consent", action="store_true") \
    .add("--data-scope") \
    .add("--json", action="store_true") \
    .run(_cmd_record_consent)

cli.subcommand("register-device", "Register device") \
    .add("--farmer-id", required=True) \
    .add("--device-id", required=True) \
    .add("--device-type", required=True) \
    .add("--location-id") \
    .add("--device-name") \
    .add("--os-type") \
    .add("--os-version") \
    .add("--app-version") \
    .add("--camera", action="store_true") \
    .add("--gps", action="store_true") \
    .add("--no-offline", action="store_true") \
    .add("--storage-mb", type=int) \
    .add("--json", action="store_true") \
    .run(_cmd_register_device)

cli.subcommand("access-matrix", "Get access matrix") \
    .add("--location-id") \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_access_matrix(db, a.location_id))

cli.subcommand("directory", "Get farmer directory") \
    .add("--location-id") \
    .add("--json", action="store_true") \
    .run(lambda db, a: get_farmer_directory(db, a.location_id))


def main(argv=None):
    cli.run(argv)


if __name__ == "__main__":
    main()

