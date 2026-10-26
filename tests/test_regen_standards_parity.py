"""Keep local Regen-facing metadata vocabulary aligned with SQL constraints."""

import re
from pathlib import Path

from services.linkml.jsonld import to_jsonld_document

ROOT = Path(__file__).parents[1]
CLAIM_SCHEMA = ROOT / "services/linkml/schemas/impact_claim.linkml.yaml"
BASE_CLAIM_SQL = ROOT / "schemas/postgres/031_impact_claims_and_cids.sql"
REGEN_SQL = ROOT / "schemas/postgres/112_regen_standards_parity.sql"


def _yaml_permissible_values(source: str, name: str, indent: int) -> set[str]:
    field_indent = " " * indent
    field = re.search(
        rf"(?ms)^{field_indent}{re.escape(name)}:\n(?P<body>.*?)(?=^{field_indent}[A-Za-z_][\w]*:\n|^\S|\Z)",
        source,
    )
    assert field, f"missing YAML field or enum: {name}"
    value_indent = " " * (indent + 2)
    values = re.search(
        rf"(?ms)^{value_indent}permissible_values:\s*\n(?P<values>.*?)(?=^{field_indent}[A-Za-z_][\w]*:\n|^\S|\Z)",
        field.group("body"),
    )
    assert values, f"missing permissible_values for {name}"
    return set(re.findall(rf"(?m)^{' ' * (indent + 4)}([A-Za-z_][\w]*):", values.group("values")))


def _sql_constraint_values(source: str, name: str) -> set[str]:
    constraint = re.search(
        rf"(?is)ADD CONSTRAINT\s+{re.escape(name)}\s+CHECK\s*\((.*?)\)\s*;",
        source,
    )
    assert constraint, f"missing SQL constraint: {name}"
    return set(re.findall(r"'([^']+)'", constraint.group(1)))


def test_kokonut_claim_record_kind_matches_database_constraint():
    schema = CLAIM_SCHEMA.read_text()
    migration = BASE_CLAIM_SQL.read_text()

    assert _yaml_permissible_values(schema, "claim_type", 6) == _sql_constraint_values(
        migration, "chk_impact_claim_type"
    )


def test_kokonut_claim_category_matches_database_constraint():
    schema = CLAIM_SCHEMA.read_text()
    migration = BASE_CLAIM_SQL.read_text()

    assert _yaml_permissible_values(schema, "claim_category", 6) == _sql_constraint_values(
        migration, "chk_impact_claim_category"
    )


def test_kokonut_governance_status_matches_database_constraint():
    schema = CLAIM_SCHEMA.read_text()
    migration = BASE_CLAIM_SQL.read_text()

    assert _yaml_permissible_values(schema, "status", 6) == _sql_constraint_values(
        migration, "chk_impact_claim_lifecycle"
    )


def test_regen_claim_type_and_verification_enums_match_database_constraints():
    schema = CLAIM_SCHEMA.read_text()
    migration = REGEN_SQL.read_text()

    assert _yaml_permissible_values(schema, "ClaimType", 2) == _sql_constraint_values(
        migration, "chk_claim_type_enum"
    )
    assert _yaml_permissible_values(schema, "VerificationStatus", 2) == _sql_constraint_values(
        migration, "chk_verification_status"
    )


def test_claim_schema_separates_regen_types_from_kokonut_workflow_state():
    schema = CLAIM_SCHEMA.read_text()

    assert "class_uri: rfs:Claim" in schema
    assert "slot_uri: kokonut:claimRecordType" in schema
    assert "slot_uri: rfs:hasClaimType" in schema
    assert "slot_uri: rfs:verificationStatus" in schema
    assert "slot_uri: kokonut:governanceStatus" in schema


def test_project_and_credit_class_declare_regen_class_uris():
    project = (ROOT / "services/linkml/schemas/project.linkml.yaml").read_text()
    credit_class = (ROOT / "services/linkml/schemas/credit_class.linkml.yaml").read_text()

    assert "class_uri: rfs:ProjectInfo" in project
    assert "class_uri: rfs:CreditClassInfo" in credit_class


def test_jsonld_document_preserves_regen_class_uri():
    document = to_jsonld_document(
        "rfs:ProjectInfo",
        {"name": "Kokonut Genesis"},
        iri="kokonut:location:genesis:v1",
    )

    assert document["@type"] == "rfs:ProjectInfo"
    assert document["@id"] == "kokonut:location:genesis:v1"
