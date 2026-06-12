"""Kokonut EAS schema definitions for Celo and multi-chain attestation."""

from __future__ import annotations

from typing import Any

KOKONUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "kokonut-mrv": {
        "schema": "string locationId, string farmId, string cropType, string activityType, uint256 quantity, string unit, uint256 measurementDate, string evidenceHash, string payloadCid",
        "revocable": True,
        "description": "Kokonut MRV claim attestation for farm monitoring, reporting, and verification",
        "claim_type": "mrv",
    },
    "kokonut-impact": {
        "schema": "string locationId, string metric, int256 value, string unit, string period, string evidenceHash, string payloadCid",
        "revocable": True,
        "description": "Environmental impact attestation for ecological outcomes",
        "claim_type": "impact",
    },
    "kokonut-financial": {
        "schema": "string locationId, string period, uint256 noi, uint256 revenue, uint256 costs, string currency, string evidenceHash",
        "revocable": True,
        "description": "Financial summary attestation for farm economic performance",
        "claim_type": "financial",
    },
    "kokonut-harvest": {
        "schema": "string locationId, string cropCycleId, uint256 quantity, string unit, string qualityGrade, uint256 harvestDate, string evidenceHash",
        "revocable": True,
        "description": "Harvest verification attestation for crop production records",
        "claim_type": "harvest",
    },
    "kokonut-compliance": {
        "schema": "string locationId, string framework, string requirement, bool compliant, string evidenceHash, string notes",
        "revocable": True,
        "description": "Partner compliance and audit trail attestation",
        "claim_type": "compliance",
    },
}


def get_schema_definition(name: str) -> dict[str, Any]:
    """Return a Kokonut schema definition by name."""
    schema = KOKONUT_SCHEMAS.get(name)
    if not schema:
        raise ValueError(f"Unknown Kokonut schema: {name}. Available: {list(KOKONUT_SCHEMAS)}")
    return schema


def get_schema_text(name: str) -> str:
    """Return the EAS schema text for a named schema."""
    return get_schema_definition(name)["schema"]


def list_schemas() -> list[str]:
    """Return all available Kokonut schema names."""
    return list(KOKONUT_SCHEMAS.keys())


def prepare_mrv_attestation_data(
    location_id: str,
    farm_id: str,
    crop_type: str,
    activity_type: str,
    quantity: float,
    unit: str,
    measurement_date: int,
    evidence_hash: str,
    payload_cid: str,
) -> list[dict[str, Any]]:
    """Prepare data fields for a kokonut-mrv attestation."""
    return [
        {"name": "locationId", "type": "string", "value": location_id},
        {"name": "farmId", "type": "string", "value": farm_id},
        {"name": "cropType", "type": "string", "value": crop_type},
        {"name": "activityType", "type": "string", "value": activity_type},
        {"name": "quantity", "type": "uint256", "value": int(quantity)},
        {"name": "unit", "type": "string", "value": unit},
        {"name": "measurementDate", "type": "uint256", "value": measurement_date},
        {"name": "evidenceHash", "type": "string", "value": evidence_hash},
        {"name": "payloadCid", "type": "string", "value": payload_cid},
    ]


def prepare_impact_attestation_data(
    location_id: str,
    metric: str,
    value: int,
    unit: str,
    period: str,
    evidence_hash: str,
    payload_cid: str,
) -> list[dict[str, Any]]:
    """Prepare data fields for a kokonut-impact attestation."""
    return [
        {"name": "locationId", "type": "string", "value": location_id},
        {"name": "metric", "type": "string", "value": metric},
        {"name": "value", "type": "int256", "value": value},
        {"name": "unit", "type": "string", "value": unit},
        {"name": "period", "type": "string", "value": period},
        {"name": "evidenceHash", "type": "string", "value": evidence_hash},
        {"name": "payloadCid", "type": "string", "value": payload_cid},
    ]


def prepare_financial_attestation_data(
    location_id: str,
    period: str,
    noi: int,
    revenue: int,
    costs: int,
    currency: str,
    evidence_hash: str,
) -> list[dict[str, Any]]:
    """Prepare data fields for a kokonut-financial attestation."""
    return [
        {"name": "locationId", "type": "string", "value": location_id},
        {"name": "period", "type": "string", "value": period},
        {"name": "noi", "type": "uint256", "value": noi},
        {"name": "revenue", "type": "uint256", "value": revenue},
        {"name": "costs", "type": "uint256", "value": costs},
        {"name": "currency", "type": "string", "value": currency},
        {"name": "evidenceHash", "type": "string", "value": evidence_hash},
    ]


def prepare_harvest_attestation_data(
    location_id: str,
    crop_cycle_id: str,
    quantity: float,
    unit: str,
    quality_grade: str,
    harvest_date: int,
    evidence_hash: str,
) -> list[dict[str, Any]]:
    """Prepare data fields for a kokonut-harvest attestation."""
    return [
        {"name": "locationId", "type": "string", "value": location_id},
        {"name": "cropCycleId", "type": "string", "value": crop_cycle_id},
        {"name": "quantity", "type": "uint256", "value": int(quantity)},
        {"name": "unit", "type": "string", "value": unit},
        {"name": "qualityGrade", "type": "string", "value": quality_grade},
        {"name": "harvestDate", "type": "uint256", "value": harvest_date},
        {"name": "evidenceHash", "type": "string", "value": evidence_hash},
    ]


def prepare_compliance_attestation_data(
    location_id: str,
    framework: str,
    requirement: str,
    compliant: bool,
    evidence_hash: str,
    notes: str,
) -> list[dict[str, Any]]:
    """Prepare data fields for a kokonut-compliance attestation."""
    return [
        {"name": "locationId", "type": "string", "value": location_id},
        {"name": "framework", "type": "string", "value": framework},
        {"name": "requirement", "type": "string", "value": requirement},
        {"name": "compliant", "type": "bool", "value": compliant},
        {"name": "evidenceHash", "type": "string", "value": evidence_hash},
        {"name": "notes", "type": "string", "value": notes},
    ]
