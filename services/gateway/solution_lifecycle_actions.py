"""Tenant-scoped, human-reviewed solution lifecycle actions."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class SolutionLifecycleActionInvalid(ValueError):
    """A solution lifecycle action identifier or payload is invalid."""


RETIREMENT_TYPES = frozenset({
    "unsafe",
    "ineffective",
    "too_costly",
    "superseded",
    "not_adopted",
    "context_invalidated",
    "evidence_withdrawn",
    "maintenance_failure",
    "governance_breach",
    "mission_complete",
})
LEARNING_TYPES = frozenset({
    "validated_assumption",
    "invalidated_assumption",
    "implementation",
    "adoption",
    "safety",
    "economic",
    "equity",
    "context_transfer",
})
LEARNING_CONFIDENCE = frozenset({"high", "moderate", "low", "insufficient_evidence"})
LEARNING_TRANSFERABILITY = frozenset({"high", "medium", "low", "unknown"})
REPLICATION_COMPLETION_OUTCOMES = frozenset({"successful", "failed", "mixed", "inconclusive"})
EXPERIMENT_OUTCOMES = frozenset({
    "validated",
    "invalidated",
    "inconclusive",
    "requires_replication",
})
SOLUTION_STAGES = frozenset({
    "discovered", "triaged", "framed", "experiment_ready", "testing",
    "validated", "investment_ready", "funded", "pilot_active",
    "adoption_ready", "adopting", "scaled", "maintained", "paused",
    "superseded", "retired", "failed",
})
NONPROMOTION_SOLUTION_STAGES = frozenset({
    "discovered", "triaged", "framed", "experiment_ready", "testing",
    "investment_ready", "pilot_active", "adopting", "maintained",
    "paused", "failed",
})
FUNDING_CAPITAL_STAGES = frozenset({
    "discovery", "experiment", "pilot", "replication", "scale", "maintenance",
})
FUNDING_INSTRUMENTS = frozenset({
    "grant", "budget", "bounty", "loan", "investment", "community_fund", "in_kind",
})
_MAX_FUNDING_AMOUNT = Decimal("9999999999999.99")
SOLUTION_TYPES = frozenset({
    "practice", "policy", "technology", "service", "governance",
    "business_model", "ecological_intervention", "data_product", "other",
})
SOLUTION_RISK_CLASSES = frozenset({"low", "medium", "high", "critical"})
SOLUTION_REVERSIBILITY = frozenset({"high", "medium", "low", "unknown"})
_SOLUTION_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{1,159}$")
_EXPERIMENT_METRIC_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
_EXPERIMENT_CONSENT_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,29}$")
_EXPERIMENT_UNIT_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
_EXPERIMENT_PROTOCOL_FIELDS = frozenset({
    "hypothesis", "null_hypothesis", "baseline_definition", "treatment_definition",
    "comparator_definition", "unit_of_analysis", "sample_plan", "primary_metric_keys",
    "secondary_metric_keys", "minimum_detectable_effect", "confidence_target",
    "duration_days", "stopping_rules", "rollback_plan", "safety_boundaries",
    "consent_requirements",
})
_EXPERIMENT_NON_PERSONAL_BASIS_CODES = frozenset({
    "environmental_measurement",
    "non_personal_operational_measurement",
    "infrastructure_measurement",
})
SOLUTION_GATE_PROMOTIONS = {
    "testing": "validated",
    "investment_ready": "funded",
    "pilot_active": "adoption_ready",
    "adopting": "scaled",
}


def _normalize_funding_amount(value, field: str, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if isinstance(value, bool):
        raise SolutionLifecycleActionInvalid(f"{field} must be a finite amount with cent precision")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid(
            f"{field} must be a finite amount with cent precision"
        ) from exc
    if not amount.is_finite():
        raise SolutionLifecycleActionInvalid(f"{field} must be a finite amount")
    if abs(amount) > _MAX_FUNDING_AMOUNT:
        raise SolutionLifecycleActionInvalid(f"{field} is outside the supported amount range")
    if amount != amount.quantize(Decimal("0.01")):
        raise SolutionLifecycleActionInvalid(f"{field} must use no more than two decimal places")
    return format(amount, ".2f")


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise SolutionLifecycleActionInvalid(f"Invalid {field} identifier") from exc


def _normalize_experiment_consent_requirements(value: dict) -> dict:
    """Require an explicit participant-consent policy in every protocol draft."""
    participant_consent_required = value.get("participant_consent_required")
    if participant_consent_required is True:
        if set(value) != {
            "participant_consent_required", "purpose", "consent_version",
        }:
            raise SolutionLifecycleActionInvalid(
                "Participant consent requirements must contain only purpose and consent version"
            )
        purpose = value.get("purpose")
        if not isinstance(purpose, str) or not 1 <= len(purpose.strip()) <= 255 or "\x00" in purpose:
            raise SolutionLifecycleActionInvalid(
                "Participant consent purpose must contain 1 to 255 characters"
            )
        consent_version = value.get("consent_version")
        if (
            not isinstance(consent_version, str)
            or not _EXPERIMENT_CONSENT_VERSION_RE.fullmatch(consent_version)
        ):
            raise SolutionLifecycleActionInvalid(
                "Participant consent version must be a bounded identifier"
            )
        return {
            "participant_consent_required": True,
            "purpose": purpose.strip(),
            "consent_version": consent_version,
        }

    if participant_consent_required is False:
        if set(value) != {"participant_consent_required", "non_personal_basis"}:
            raise SolutionLifecycleActionInvalid(
                "Non-participant protocols must declare one approved non-personal basis"
            )
        basis = value.get("non_personal_basis")
        if (
            not isinstance(basis, str)
            or basis not in _EXPERIMENT_NON_PERSONAL_BASIS_CODES
        ):
            raise SolutionLifecycleActionInvalid(
                "Non-personal basis must be environmental, operational, or infrastructure measurement"
            )
        return {
            "participant_consent_required": False,
            "non_personal_basis": basis,
        }

    raise SolutionLifecycleActionInvalid(
        "Consent requirements must explicitly declare whether participant consent is required"
    )


def _normalize_experiment_analysis_policy(sample_plan: dict, stopping_rules: dict, metric_keys: set[str]):
    sample_plan = dict(sample_plan)
    minimum_sample = sample_plan.get("minimum_sample", 2)
    if isinstance(minimum_sample, bool) or not isinstance(minimum_sample, int) \
            or not 2 <= minimum_sample <= 10000:
        raise SolutionLifecycleActionInvalid(
            "Sample plan minimum_sample must be a whole number from 2 through 10000"
        )
    sample_plan["minimum_sample"] = minimum_sample

    stopping_rules = dict(stopping_rules)
    directions = stopping_rules.get("benefit_direction_by_metric", {})
    if not isinstance(directions, dict) or set(directions) != metric_keys:
        raise SolutionLifecycleActionInvalid(
            "Stopping rules must set benefit_direction_by_metric for every declared metric"
        )
    if any(
        not isinstance(direction, str) or direction not in {"higher", "lower"}
        for direction in directions.values()
    ):
        raise SolutionLifecycleActionInvalid(
            "Metric benefit directions must be higher or lower"
        )
    stopping_rules["benefit_direction_by_metric"] = {
        key: directions[key] for key in sorted(metric_keys)
    }

    benefit_threshold = stopping_rules.get("benefit_threshold", 0)
    if isinstance(benefit_threshold, bool) or not isinstance(benefit_threshold, (int, float)) \
            or not math.isfinite(benefit_threshold) or abs(benefit_threshold) > 1_000_000:
        raise SolutionLifecycleActionInvalid(
            "Stopping-rule benefit_threshold must be a finite supported number"
        )
    stopping_rules["benefit_threshold"] = benefit_threshold

    posterior_threshold = stopping_rules.get("posterior_threshold", 0.9)
    if isinstance(posterior_threshold, bool) or not isinstance(posterior_threshold, (int, float)) \
            or not math.isfinite(posterior_threshold) or not 0.5 < posterior_threshold < 1:
        raise SolutionLifecycleActionInvalid(
            "Stopping-rule posterior_threshold must be greater than 0.5 and less than 1"
        )
    stopping_rules["posterior_threshold"] = posterior_threshold

    safety_event_limit = stopping_rules.get("safety_event_limit")
    if safety_event_limit is not None and (
        isinstance(safety_event_limit, bool)
        or not isinstance(safety_event_limit, int)
        or not 0 <= safety_event_limit <= 100000
    ):
        raise SolutionLifecycleActionInvalid(
            "Stopping-rule safety_event_limit must be a whole number from 0 through 100000"
        )
    stopping_rules["safety_event_limit"] = safety_event_limit
    return sample_plan, stopping_rules


def create_location_solution(
    operator_id: str,
    location_id: str,
    request_id: str,
    canonical_key: str,
    name: str,
    solution_type: str,
    problem_statement: str,
    rationale: str,
    evidence: list,
    *,
    theory_of_change: str | None = None,
    baseline_alternative: str | None = None,
    risk_class: str = "medium",
    reversibility: str = "medium",
    acknowledged: bool = False,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a discovered solution whose canonical origin is one granted location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(canonical_key, str):
        raise SolutionLifecycleActionInvalid("Canonical key must be text")
    canonical_key = canonical_key.strip()
    if not _SOLUTION_KEY_RE.fullmatch(canonical_key):
        raise SolutionLifecycleActionInvalid(
            "Canonical key must be 2 to 160 lowercase letters, digits, dots, underscores, colons, or hyphens"
        )
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 255 or "\x00" in name:
        raise SolutionLifecycleActionInvalid("Solution name must contain 1 to 255 characters")
    name = name.strip()
    if not isinstance(solution_type, str) or solution_type not in SOLUTION_TYPES:
        raise SolutionLifecycleActionInvalid("Invalid solution type")
    if (
        not isinstance(problem_statement, str)
        or not 1 <= len(problem_statement.strip()) <= 8000
        or "\x00" in problem_statement
    ):
        raise SolutionLifecycleActionInvalid(
            "Problem statement must contain 1 to 8000 characters"
        )
    problem_statement = problem_statement.strip()
    if theory_of_change is not None and (
        not isinstance(theory_of_change, str)
        or len(theory_of_change) > 4000
        or "\x00" in theory_of_change
    ):
        raise SolutionLifecycleActionInvalid("Theory of change must be at most 4000 characters")
    if baseline_alternative is not None and (
        not isinstance(baseline_alternative, str)
        or len(baseline_alternative) > 4000
        or "\x00" in baseline_alternative
    ):
        raise SolutionLifecycleActionInvalid("Baseline alternative must be at most 4000 characters")
    if not isinstance(risk_class, str) or risk_class not in SOLUTION_RISK_CLASSES:
        raise SolutionLifecycleActionInvalid("Invalid solution risk class")
    if not isinstance(reversibility, str) or reversibility not in SOLUTION_REVERSIBILITY:
        raise SolutionLifecycleActionInvalid("Invalid solution reversibility")
    if not isinstance(rationale, str) or not 10 <= len(rationale.strip()) <= 4000 or "\x00" in rationale:
        raise SolutionLifecycleActionInvalid(
            "Creation rationale must contain between 10 and 4000 characters"
        )
    rationale = rationale.strip()
    if not isinstance(evidence, list) or len(evidence) > 100:
        raise SolutionLifecycleActionInvalid("Creation evidence must be a list of at most 100 items")
    try:
        encoded_evidence = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Creation evidence must contain JSON values") from exc
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Creation evidence exceeds the 64 KiB limit")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Solution creation requires explicit acknowledgement")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_location_solution(
                           %s::uuid, %s::uuid, %s::text, %s::text, %s::text,
                           %s::text, %s::text, %s::text, %s::text, %s::text,
                           %s::text, %s::jsonb, %s::boolean
                       )""",
                (
                    location_id, request_id, canonical_key, name, solution_type,
                    problem_statement, theory_of_change, baseline_alternative,
                    risk_class, reversibility, rationale, encoded_evidence,
                    acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Location solution creation returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_location_solution_adoption_program(
    operator_id: str,
    location_id: str,
    solution_id: str,
    request_id: str,
    adoption_pathway: str,
    *,
    local_adaptation_policy: str | None = None,
    acknowledged: bool = False,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a draft adoption program for an exact-location solution."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    solution_id = _normalize_uuid(solution_id, "solution")
    request_id = _normalize_uuid(request_id, "request")
    if (
        not isinstance(adoption_pathway, str)
        or not 1 <= len(adoption_pathway.strip()) <= 2000
        or "\x00" in adoption_pathway
    ):
        raise SolutionLifecycleActionInvalid(
            "Adoption pathway must contain 1 to 2,000 characters"
        )
    adoption_pathway = adoption_pathway.strip()
    try:
        if len(adoption_pathway.encode("utf-8")) > 4000:
            raise SolutionLifecycleActionInvalid(
                "Adoption pathway must fit within 4 KiB"
            )
    except UnicodeEncodeError as exc:
        raise SolutionLifecycleActionInvalid(
            "Adoption pathway must be valid UTF-8 text"
        ) from exc
    if local_adaptation_policy is not None:
        if not isinstance(local_adaptation_policy, str) or len(local_adaptation_policy) > 4000:
            raise SolutionLifecycleActionInvalid(
                "Local adaptation policy must be at most 4,000 characters"
            )
        if "\x00" in local_adaptation_policy:
            raise SolutionLifecycleActionInvalid(
                "Local adaptation policy cannot contain a null character"
            )
        try:
            if len(local_adaptation_policy.encode("utf-8")) > 8000:
                raise SolutionLifecycleActionInvalid(
                    "Local adaptation policy must fit within 8 KiB"
                )
        except UnicodeEncodeError as exc:
            raise SolutionLifecycleActionInvalid(
                "Local adaptation policy must be valid UTF-8 text"
            ) from exc
        local_adaptation_policy = local_adaptation_policy.strip() or None
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Adoption program draft requires acknowledgement that review and readiness are separate"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_location_solution_adoption_program(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text, %s::boolean
                       )""",
                (
                    location_id, solution_id, request_id, adoption_pathway,
                    local_adaptation_policy, acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Adoption program creation returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def submit_location_solution_adoption_program(
    operator_id: str,
    location_id: str,
    program_id: str,
    request_id: str,
    *,
    acknowledged: bool = False,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit a creator-owned adoption-program draft for independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    program_id = _normalize_uuid(program_id, "adoption program")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Adoption program submission requires acknowledgement that review does not launch adoption"
        )
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection, operator_id=operator_id, location_id=location_id,
            resource="solution_lifecycle", action="submit",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.submit_location_solution_adoption_program(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean
                       )""",
                (location_id, program_id, request_id, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Adoption program submission returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _get_location_solution_adoption_program_page(
    operator_id: str,
    location_id: str,
    *,
    limit: int,
    offset: int,
    action: str,
    function_name: str,
    response_key: str,
    connection_factory: Callable | None = None,
) -> dict:
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 25:
        raise SolutionLifecycleActionInvalid("Adoption program page size must be between 1 and 25")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise SolutionLifecycleActionInvalid("Adoption program page offset is invalid")
    page_functions = {
        "location_solution_adoption_program_drafts": (
            "drafts", "submit",
        ),
        "location_solution_adoption_program_review_queue": (
            "programs", "review",
        ),
    }
    if function_name not in page_functions:
        raise SolutionLifecycleActionInvalid("Adoption program page is invalid")
    response_key, action = page_functions[function_name]
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(connection, operator_id=operator_id, location_id=location_id,
                                    resource="solution_lifecycle", action=action)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM kokonut_security."
                + function_name
                + "(%s::uuid, %s::integer, %s::integer)",
                (location_id, limit + 1, offset),
            )
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
        items = [dict(zip(columns, row, strict=False)) for row in rows[:limit]]
        has_more = len(rows) > limit
        connection.commit()
        return {
            response_key: items,
            "has_more": has_more,
            "next_offset": offset + len(items) if has_more else None,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_location_solution_adoption_program_drafts(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 10,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List only the caller's own exact-location unsubmitted program drafts."""
    return _get_location_solution_adoption_program_page(
        operator_id, location_id, limit=limit, offset=offset, action="submit",
        function_name="location_solution_adoption_program_drafts",
        response_key="drafts", connection_factory=connection_factory,
    )


def get_location_solution_adoption_program_review_queue(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 10,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """List bounded submitted program details while excluding self-authored work."""
    return _get_location_solution_adoption_program_page(
        operator_id, location_id, limit=limit, offset=offset, action="review",
        function_name="location_solution_adoption_program_review_queue",
        response_key="programs", connection_factory=connection_factory,
    )


def review_location_solution_adoption_program(
    operator_id: str,
    location_id: str,
    program_id: str,
    request_id: str,
    decision: str,
    review_note: str,
    *,
    acknowledged: bool = False,
    connection_factory: Callable | None = None,
) -> dict:
    """Record an independent approval or redesign decision for one program."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    program_id = _normalize_uuid(program_id, "adoption program")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(decision, str) or decision not in {"enablement_ready", "redesign"}:
        raise SolutionLifecycleActionInvalid("Adoption program review decision is invalid")
    if not isinstance(review_note, str) or not 1 <= len(review_note.strip()) <= 2000:
        raise SolutionLifecycleActionInvalid(
            "Adoption program review note must contain 1 to 2,000 characters"
        )
    if "\x00" in review_note:
        raise SolutionLifecycleActionInvalid("Adoption program review note cannot contain a null character")
    try:
        if len(review_note.encode("utf-8")) > 4000:
            raise SolutionLifecycleActionInvalid("Adoption program review note must fit within 4 KiB")
    except UnicodeEncodeError as exc:
        raise SolutionLifecycleActionInvalid("Adoption program review note must be valid UTF-8 text") from exc
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Adoption program review requires acknowledgement that readiness and launch remain separate"
        )
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection, operator_id=operator_id, location_id=location_id,
            resource="solution_lifecycle", action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.review_location_solution_adoption_program(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text, %s::boolean
                       )""",
                (location_id, program_id, request_id, decision, review_note.strip(), acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Adoption program review returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def submit_location_solution_adopter_readiness(
    operator_id: str,
    location_id: str,
    solution_id: str,
    request_id: str,
    current_level,
    required_level,
    *,
    remediation_plan: str | None = None,
    acknowledged: bool = False,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit an exact-location readiness assessment for independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    solution_id = _normalize_uuid(solution_id, "solution")
    request_id = _normalize_uuid(request_id, "request")
    normalized_levels: list[str] = []
    for value, field in (
        (current_level, "Current readiness level"),
        (required_level, "Required readiness level"),
    ):
        if isinstance(value, bool):
            raise SolutionLifecycleActionInvalid(f"{field} must be a finite number")
        try:
            level = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise SolutionLifecycleActionInvalid(f"{field} must be a finite number") from exc
        if not level.is_finite() or level < 0 or level > Decimal("999.999"):
            raise SolutionLifecycleActionInvalid(f"{field} is outside the supported range")
        if level != level.quantize(Decimal("0.001")):
            raise SolutionLifecycleActionInvalid(f"{field} must use no more than three decimal places")
        normalized_levels.append(format(level, ".3f"))
    if remediation_plan is not None:
        if not isinstance(remediation_plan, str) or len(remediation_plan) > 4000:
            raise SolutionLifecycleActionInvalid("Remediation plan must be at most 4,000 characters")
        if "\x00" in remediation_plan:
            raise SolutionLifecycleActionInvalid("Remediation plan cannot contain a null character")
        try:
            if len(remediation_plan.encode("utf-8")) > 8000:
                raise SolutionLifecycleActionInvalid("Remediation plan must fit within 8 KiB")
        except UnicodeEncodeError as exc:
            raise SolutionLifecycleActionInvalid("Remediation plan must be valid UTF-8 text") from exc
        remediation_plan = remediation_plan.strip() or None
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Readiness submission requires acknowledgement that an independent review is required"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.submit_location_solution_adopter_readiness(
                           %s::uuid, %s::uuid, %s::uuid, %s::numeric, %s::numeric, %s::text, %s::boolean
                       )""",
                (
                    location_id, solution_id, request_id, normalized_levels[0],
                    normalized_levels[1], remediation_plan, acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Readiness assessment returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_location_solution_adopter_readiness_review_queue(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Read a bounded queue of assessments this human can independently review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise SolutionLifecycleActionInvalid("Readiness review page size must be between 1 and 100")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise SolutionLifecycleActionInvalid("Readiness review page offset is invalid")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.location_solution_adopter_readiness_review_queue(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, limit + 1, offset),
            )
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
        assessments = [dict(zip(columns, row, strict=False)) for row in rows[:limit]]
        has_more = len(rows) > limit
        connection.commit()
        return {
            "assessments": assessments,
            "has_more": has_more,
            "next_offset": offset + len(assessments) if has_more else None,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_solution_adopter_readiness(
    operator_id: str,
    location_id: str,
    assessment_id: str,
    request_id: str,
    decision: str,
    review_note: str,
    *,
    acknowledged: bool = False,
    connection_factory: Callable | None = None,
) -> dict:
    """Independently decide whether a current readiness assessment is accepted."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    assessment_id = _normalize_uuid(assessment_id, "assessment")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(decision, str) or decision not in {"ready", "remediating", "rejected"}:
        raise SolutionLifecycleActionInvalid("Readiness review decision is invalid")
    if not isinstance(review_note, str) or not 1 <= len(review_note.strip()) <= 2000:
        raise SolutionLifecycleActionInvalid("Readiness review note must contain 1 to 2,000 characters")
    if "\x00" in review_note:
        raise SolutionLifecycleActionInvalid("Readiness review note cannot contain a null character")
    try:
        if len(review_note.encode("utf-8")) > 4000:
            raise SolutionLifecycleActionInvalid("Readiness review note must fit within 4 KiB")
    except UnicodeEncodeError as exc:
        raise SolutionLifecycleActionInvalid("Readiness review note must be valid UTF-8 text") from exc
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Readiness review requires acknowledgement that this decision is independent"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.review_location_solution_adopter_readiness(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text, %s::boolean
                       )""",
                (location_id, assessment_id, request_id, decision, review_note.strip(), acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Readiness review returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


_CONFIGURATION_COMPARABILITY = {
    "comparable", "partially_comparable", "not_comparable",
}


def _encode_location_solution_configuration(
    invariant_components: dict,
    configurable_components: dict,
    prohibited_components: dict,
    local_assumptions: dict,
    comparability_class: str,
    evidence_impact: str,
) -> tuple[str, str, str, str, str, str]:
    components = (
        (invariant_components, "invariant components"),
        (configurable_components, "configurable components"),
        (prohibited_components, "prohibited components"),
        (local_assumptions, "local assumptions"),
    )
    encoded_components = []

    def validate_json_text(value: object) -> None:
        if isinstance(value, str):
            if "\x00" in value:
                raise SolutionLifecycleActionInvalid(
                    "Configuration components cannot contain null characters"
                )
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise SolutionLifecycleActionInvalid(
                    "Configuration components must be valid UTF-8"
                ) from exc
        elif isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise SolutionLifecycleActionInvalid(
                        "Configuration component object keys must be text"
                    )
                validate_json_text(key)
                validate_json_text(item)
        elif isinstance(value, list):
            for item in value:
                validate_json_text(item)
        elif value is not None and not isinstance(value, (bool, int, float)):
            raise SolutionLifecycleActionInvalid(
                "Configuration components must contain JSON values"
            )

    for value, name in components:
        if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
            raise SolutionLifecycleActionInvalid(f"Configuration {name} must be a JSON object with text keys")
        validate_json_text(value)
        try:
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise SolutionLifecycleActionInvalid(f"Configuration {name} must contain JSON values") from exc
        encoded_components.append(encoded)
    try:
        total_size = len(json.dumps(
            [json.loads(item) for item in encoded_components],
            ensure_ascii=False, allow_nan=False, separators=(",", ":"),
        ).encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise SolutionLifecycleActionInvalid("Configuration components must be valid UTF-8") from exc
    if total_size > 65536:
        raise SolutionLifecycleActionInvalid("Configuration components exceed the 64 KiB limit")
    invariant_keys = set(invariant_components)
    configurable_keys = set(configurable_components)
    prohibited_keys = set(prohibited_components)
    if invariant_keys & (configurable_keys | prohibited_keys):
        raise SolutionLifecycleActionInvalid("Invariant components cannot also be configurable or prohibited")
    if configurable_keys & prohibited_keys:
        raise SolutionLifecycleActionInvalid("A component cannot be both configurable and prohibited")
    if not isinstance(comparability_class, str) or comparability_class not in _CONFIGURATION_COMPARABILITY:
        raise SolutionLifecycleActionInvalid("Configuration comparability class is invalid")
    if not isinstance(evidence_impact, str) or not 1 <= len(evidence_impact.strip()) <= 4000:
        raise SolutionLifecycleActionInvalid("Configuration evidence impact must contain 1 to 4,000 characters")
    if "\x00" in evidence_impact:
        raise SolutionLifecycleActionInvalid("Configuration evidence impact cannot contain a null character")
    try:
        if len(evidence_impact.encode("utf-8")) > 8000:
            raise SolutionLifecycleActionInvalid("Configuration evidence impact must fit within 8 KiB")
    except UnicodeEncodeError as exc:
        raise SolutionLifecycleActionInvalid("Configuration evidence impact must be valid UTF-8 text") from exc
    return (
        *encoded_components,
        comparability_class,
        evidence_impact.strip(),
    )


def create_location_solution_configuration_draft(
    operator_id: str,
    location_id: str,
    solution_id: str,
    request_id: str,
    invariant_components: dict,
    configurable_components: dict,
    prohibited_components: dict,
    local_assumptions: dict,
    comparability_class: str,
    evidence_impact: str,
    *,
    acknowledged: bool = False,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a versioned exact-location configuration draft."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    solution_id = _normalize_uuid(solution_id, "solution")
    request_id = _normalize_uuid(request_id, "request")
    encoded = _encode_location_solution_configuration(
        invariant_components, configurable_components, prohibited_components,
        local_assumptions, comparability_class, evidence_impact,
    )
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Configuration draft requires acknowledgement of independent review")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection, operator_id=operator_id, location_id=location_id,
            resource="solution_lifecycle", action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_location_solution_configuration_draft(
                           %s::uuid, %s::uuid, %s::uuid, %s::jsonb, %s::jsonb,
                           %s::jsonb, %s::jsonb, %s::text, %s::text, %s::boolean
                       )""",
                (
                    location_id, solution_id, request_id, encoded[0], encoded[1],
                    encoded[2], encoded[3], encoded[4], encoded[5], acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Configuration draft creation returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_location_solution_configuration_drafts(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 10,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Read the authenticated operator's unsubmitted configuration drafts."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 25:
        raise SolutionLifecycleActionInvalid("Configuration draft page size must be between 1 and 25")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise SolutionLifecycleActionInvalid("Configuration draft page offset is invalid")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection, operator_id=operator_id, location_id=location_id,
            resource="solution_lifecycle", action="submit",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.location_solution_configuration_drafts(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, limit + 1, offset),
            )
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
        drafts = [dict(zip(columns, row, strict=False)) for row in rows[:limit]]
        has_more = len(rows) > limit
        connection.commit()
        return {
            "drafts": drafts,
            "has_more": has_more,
            "next_offset": offset + len(drafts) if has_more else None,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def submit_location_solution_configuration(
    operator_id: str,
    location_id: str,
    configuration_id: str,
    request_id: str,
    *,
    acknowledged: bool = False,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit a creator-owned configuration draft for independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    configuration_id = _normalize_uuid(configuration_id, "configuration")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Configuration submission requires explicit acknowledgement")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection, operator_id=operator_id, location_id=location_id,
            resource="solution_lifecycle", action="submit",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.submit_location_solution_configuration(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean
                       )""",
                (location_id, configuration_id, request_id, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Configuration submission returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_location_solution_configuration_review_queue(
    operator_id: str,
    location_id: str,
    *,
    limit: int = 10,
    offset: int = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Read a bounded location-scoped queue of independently reviewable configurations."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 25:
        raise SolutionLifecycleActionInvalid("Configuration review page size must be between 1 and 25")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise SolutionLifecycleActionInvalid("Configuration review page offset is invalid")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection, operator_id=operator_id, location_id=location_id,
            resource="solution_lifecycle", action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.location_solution_configuration_review_queue(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, limit + 1, offset),
            )
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
        configurations = [dict(zip(columns, row, strict=False)) for row in rows[:limit]]
        has_more = len(rows) > limit
        connection.commit()
        return {
            "configurations": configurations,
            "has_more": has_more,
            "next_offset": offset + len(configurations) if has_more else None,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_solution_configuration(
    operator_id: str,
    location_id: str,
    configuration_id: str,
    request_id: str,
    decision: str,
    review_note: str,
    *,
    acknowledged: bool = False,
    connection_factory: Callable | None = None,
) -> dict:
    """Independently approve or reject an immutable submitted configuration."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    configuration_id = _normalize_uuid(configuration_id, "configuration")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(decision, str) or decision not in {"approved", "rejected"}:
        raise SolutionLifecycleActionInvalid("Configuration review decision is invalid")
    if not isinstance(review_note, str) or not 1 <= len(review_note.strip()) <= 2000:
        raise SolutionLifecycleActionInvalid("Configuration review note must contain 1 to 2,000 characters")
    if "\x00" in review_note:
        raise SolutionLifecycleActionInvalid("Configuration review note cannot contain a null character")
    try:
        if len(review_note.encode("utf-8")) > 4000:
            raise SolutionLifecycleActionInvalid("Configuration review note must fit within 4 KiB")
    except UnicodeEncodeError as exc:
        raise SolutionLifecycleActionInvalid("Configuration review note must be valid UTF-8 text") from exc
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Configuration review requires acknowledgement of independent review")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection, operator_id=operator_id, location_id=location_id,
            resource="solution_lifecycle", action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.review_location_solution_configuration(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text, %s::boolean
                       )""",
                (location_id, configuration_id, request_id, decision, review_note.strip(), acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Configuration review returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_location_solution_gate(
    operator_id: str,
    location_id: str,
    solution_id: str,
    request_id: str,
    to_stage: str,
    criterion: str,
    required_evidence_maturity: int | None,
    required_experiment_count: int,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create one immutable, exact-origin promotion gate in draft state."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    solution_id = _normalize_uuid(solution_id, "solution")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(to_stage, str) or to_stage not in SOLUTION_GATE_PROMOTIONS.values():
        raise SolutionLifecycleActionInvalid("Unsupported solution promotion target")
    if not isinstance(criterion, str) or not 10 <= len(criterion.strip()) <= 2000 or "\x00" in criterion:
        raise SolutionLifecycleActionInvalid(
            "Gate criterion must contain 10 to 2,000 characters and fit within 4 KiB"
        )
    try:
        criterion_bytes = criterion.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SolutionLifecycleActionInvalid("Gate criterion must be valid UTF-8 text") from exc
    if len(criterion_bytes) > 4000:
        raise SolutionLifecycleActionInvalid(
            "Gate criterion must contain 10 to 2,000 characters and fit within 4 KiB"
        )
    criterion = criterion.strip()
    if required_evidence_maturity is not None and (
        isinstance(required_evidence_maturity, bool)
        or not isinstance(required_evidence_maturity, int)
        or not 1 <= required_evidence_maturity <= 6
    ):
        raise SolutionLifecycleActionInvalid(
            "Required evidence maturity must be an integer from 1 to 6"
        )
    if (
        isinstance(required_experiment_count, bool)
        or not isinstance(required_experiment_count, int)
        or not 0 <= required_experiment_count <= 100
    ):
        raise SolutionLifecycleActionInvalid(
            "Required experiment count must be an integer from 0 to 100"
        )
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Gate creation requires acknowledgement that independent review is required"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_location_solution_gate(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text,
                           %s::integer, %s::integer, %s::boolean
                       )""",
                (
                    location_id, solution_id, request_id, to_stage, criterion,
                    required_evidence_maturity, required_experiment_count,
                    acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Location solution gate creation returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_location_solution_experiment(
    operator_id: str,
    location_id: str,
    solution_id: str,
    request_id: str,
    protocol: dict,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create an immutable experiment protocol draft for an exact-origin solution."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    solution_id = _normalize_uuid(solution_id, "solution")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(protocol, dict) or not set(protocol).issubset(_EXPERIMENT_PROTOCOL_FIELDS):
        raise SolutionLifecycleActionInvalid("Experiment protocol fields are invalid")

    normalized = {}
    required_text = (
        ("hypothesis", 4000),
        ("baseline_definition", 4000),
        ("treatment_definition", 4000),
        ("unit_of_analysis", 255),
        ("rollback_plan", 4000),
    )
    for field, maximum in required_text:
        value = protocol.get(field)
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum or "\x00" in value:
            raise SolutionLifecycleActionInvalid(
                f"{field.replace('_', ' ').capitalize()} must contain 1 to {maximum} characters"
            )
        normalized[field] = value.strip()
    for field in ("null_hypothesis", "comparator_definition"):
        value = protocol.get(field)
        if value is not None:
            if not isinstance(value, str) or len(value) > 4000 or "\x00" in value:
                raise SolutionLifecycleActionInvalid(
                    f"{field.replace('_', ' ').capitalize()} must be at most 4000 characters"
                )
            normalized[field] = value.strip() or None

    for field in ("sample_plan", "stopping_rules", "safety_boundaries", "consent_requirements"):
        value = protocol.get(field, {})
        if not isinstance(value, dict):
            raise SolutionLifecycleActionInvalid(
                f"{field.replace('_', ' ').capitalize()} must be a JSON object"
            )
        normalized[field] = (
            _normalize_experiment_consent_requirements(value)
            if field == "consent_requirements"
            else value
        )

    metric_sets = {}
    for field in ("primary_metric_keys", "secondary_metric_keys"):
        values = protocol.get(field, [])
        if not isinstance(values, list) or len(values) > 50:
            raise SolutionLifecycleActionInvalid(
                f"{field.replace('_', ' ').capitalize()} must contain at most 50 metric keys"
            )
        if any(not isinstance(value, str) or not _EXPERIMENT_METRIC_KEY_RE.fullmatch(value)
               for value in values):
            raise SolutionLifecycleActionInvalid(
                f"{field.replace('_', ' ').capitalize()} contains an invalid metric key"
            )
        if len(values) != len(set(values)):
            raise SolutionLifecycleActionInvalid(
                f"{field.replace('_', ' ').capitalize()} must contain unique metric keys"
            )
        metric_sets[field] = set(values)
        normalized[field] = values
    if metric_sets["primary_metric_keys"] & metric_sets["secondary_metric_keys"]:
        raise SolutionLifecycleActionInvalid(
            "Primary and secondary experiment metric keys must be distinct"
        )
    sample_plan, stopping_rules = _normalize_experiment_analysis_policy(
        normalized["sample_plan"],
        normalized["stopping_rules"],
        metric_sets["primary_metric_keys"] | metric_sets["secondary_metric_keys"],
    )
    normalized["sample_plan"] = sample_plan
    normalized["stopping_rules"] = stopping_rules

    effect = protocol.get("minimum_detectable_effect")
    if effect is not None:
        if isinstance(effect, bool) or not isinstance(effect, (int, float)) \
                or not math.isfinite(effect) or abs(effect) > 1_000_000_000_000:
            raise SolutionLifecycleActionInvalid("Minimum detectable effect is outside the supported range")
        normalized["minimum_detectable_effect"] = effect
    confidence = protocol.get("confidence_target")
    if confidence is not None:
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) \
                or not math.isfinite(confidence) or not 0.5 <= confidence <= 1:
            raise SolutionLifecycleActionInvalid("Confidence target must be from 0.5 through 1")
        normalized["confidence_target"] = confidence
    duration = protocol.get("duration_days")
    if duration is not None:
        if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 3650:
            raise SolutionLifecycleActionInvalid("Duration must be an integer from 1 through 3650 days")
        normalized["duration_days"] = duration

    try:
        encoded_protocol = json.dumps(
            normalized, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Experiment protocol must contain JSON values") from exc
    if len(encoded_protocol.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Experiment protocol exceeds the 64 KiB limit")
    for field in ("sample_plan", "stopping_rules", "safety_boundaries", "consent_requirements"):
        if len(json.dumps(normalized[field], ensure_ascii=False, allow_nan=False,
                          separators=(",", ":")).encode("utf-8")) > 8192:
            raise SolutionLifecycleActionInvalid(
                f"{field.replace('_', ' ').capitalize()} exceeds the 8 KiB limit"
            )
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Experiment draft creation requires acknowledgement that review and execution are separate"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.create_location_solution_experiment(
                           %s::uuid, %s::uuid, %s::uuid, %s::jsonb, %s::boolean
                       )""",
                (location_id, solution_id, request_id, encoded_protocol, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Location solution experiment creation returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def submit_location_solution_experiment_protocol(
    operator_id: str,
    location_id: str,
    experiment_id: str,
    request_id: str,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit an owner-authored experiment draft for separate protocol review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    experiment_id = _normalize_uuid(experiment_id, "experiment")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Experiment submission requires explicit acknowledgement"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="submit",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.submit_location_solution_experiment_protocol(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean
                       )""",
                (location_id, experiment_id, request_id, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Experiment protocol submission returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def approve_location_solution_experiment_protocol(
    operator_id: str,
    location_id: str,
    experiment_id: str,
    request_id: str,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Independently approve one submitted protocol without starting it."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    experiment_id = _normalize_uuid(experiment_id, "experiment")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Protocol approval requires explicit acknowledgement"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.approve_location_solution_experiment_protocol(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean
                       )""",
                (location_id, experiment_id, request_id, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Experiment protocol approval returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def start_location_solution_experiment(
    operator_id: str,
    location_id: str,
    experiment_id: str,
    request_id: str,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Start an independently approved experiment without asserting consent."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    experiment_id = _normalize_uuid(experiment_id, "experiment")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Experiment start requires explicit acknowledgement"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="transition",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.start_location_solution_experiment(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean
                       )""",
                (location_id, experiment_id, request_id, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Experiment start returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def record_location_solution_experiment_observation(
    operator_id: str,
    location_id: str,
    experiment_id: str,
    request_id: str,
    metric_key: str,
    value: int | float | Decimal | None,
    arm: str,
    unit_ref: str | None,
    adverse_event: bool,
    evidence: dict | list,
    participant_link_id: str | None,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record one observation under exact location scope and current consent."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    experiment_id = _normalize_uuid(experiment_id, "experiment")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(metric_key, str) or not _EXPERIMENT_METRIC_KEY_RE.fullmatch(metric_key):
        raise SolutionLifecycleActionInvalid("Observation metric key is invalid")
    if not isinstance(adverse_event, bool):
        raise SolutionLifecycleActionInvalid("Adverse-event flag must be true or false")
    if value is not None:
        if isinstance(value, bool):
            raise SolutionLifecycleActionInvalid("Observation value must be a finite number")
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise SolutionLifecycleActionInvalid(
                "Observation value must be a finite number"
            ) from exc
        if not decimal_value.is_finite():
            raise SolutionLifecycleActionInvalid("Observation value must be a finite number")
        if abs(decimal_value) > Decimal("1000000000000"):
            raise SolutionLifecycleActionInvalid(
                "Observation value is outside the supported range"
            )
        encoded_value = format(decimal_value, "f")
    else:
        encoded_value = None
        if adverse_event is not True:
            raise SolutionLifecycleActionInvalid(
                "A missing observation value is allowed only for an adverse event"
            )
    if not isinstance(arm, str) or arm not in {"baseline", "treatment", "comparator"}:
        raise SolutionLifecycleActionInvalid("Observation arm is invalid")
    if unit_ref is not None and (
        not isinstance(unit_ref, str)
        or not _EXPERIMENT_UNIT_REF_RE.fullmatch(unit_ref)
    ):
        raise SolutionLifecycleActionInvalid(
            "Unit reference must be a short opaque identifier"
        )
    if not isinstance(evidence, (dict, list)):
        raise SolutionLifecycleActionInvalid("Observation evidence must be a JSON object or array")
    try:
        encoded_evidence = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Observation evidence must contain JSON values") from exc
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Observation evidence exceeds the 64 KiB limit")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Observation capture requires explicit acknowledgement")
    if participant_link_id is not None:
        participant_link_id = _normalize_uuid(participant_link_id, "participant link")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="collect",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.capture_location_solution_experiment_observation(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::numeric,
                           %s::text, %s::text, %s::boolean, %s::jsonb,
                           %s::uuid, %s::boolean
                       )""",
                (
                    location_id, experiment_id, request_id, metric_key,
                    encoded_value, arm, unit_ref, adverse_event, encoded_evidence,
                    participant_link_id, acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Experiment observation capture returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def analyze_location_solution_experiment(
    operator_id: str,
    location_id: str,
    experiment_id: str,
    request_id: str,
    metric_key: str,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Persist one protocol-bound sequential analysis without changing lifecycle state."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    experiment_id = _normalize_uuid(experiment_id, "experiment")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(metric_key, str) or not _EXPERIMENT_METRIC_KEY_RE.fullmatch(metric_key):
        raise SolutionLifecycleActionInvalid("Analysis metric key is invalid")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Experiment analysis requires explicit acknowledgement")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="analyze",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.analyze_location_solution_experiment(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::boolean
                       )""",
                (location_id, experiment_id, request_id, metric_key, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Experiment analysis returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def complete_location_solution_experiment(
    operator_id: str,
    location_id: str,
    experiment_id: str,
    request_id: str,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Close data collection only after every primary metric reaches a current stopping boundary."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    experiment_id = _normalize_uuid(experiment_id, "experiment")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Experiment completion requires explicit acknowledgement")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="transition",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.complete_location_solution_experiment(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean
                       )""",
                (location_id, experiment_id, request_id, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Experiment completion returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def record_location_solution_gate_evaluation(
    operator_id: str,
    location_id: str,
    gate_id: str,
    request_id: str,
    passed: bool,
    observed: dict,
    evidence: list,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Append an attributed evaluation for an exact location-origin gate."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    gate_id = _normalize_uuid(gate_id, "gate")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(passed, bool):
        raise SolutionLifecycleActionInvalid("Gate evaluation result must be true or false")
    if not isinstance(observed, dict):
        raise SolutionLifecycleActionInvalid("Gate observed values must be a JSON object")
    if not isinstance(evidence, list) or not evidence or len(evidence) > 100:
        raise SolutionLifecycleActionInvalid("Gate evidence must be a nonempty list of at most 100 items")
    try:
        encoded_observed = json.dumps(
            observed, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        encoded_evidence = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Gate evaluation values must contain JSON data") from exc
    if len(encoded_observed.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Gate observed values exceed the 64 KiB limit")
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Gate evidence exceeds the 64 KiB limit")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.record_location_solution_gate_evaluation(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean, %s::jsonb, %s::jsonb
                       )""",
                (
                    location_id,
                    gate_id,
                    request_id,
                    passed,
                    encoded_observed,
                    encoded_evidence,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution gate evaluation returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def submit_location_solution_scale_gate_assessment(
    operator_id: str,
    location_id: str,
    gate_id: str,
    request_id: str,
    measured_value: str,
    sample_size: int,
    reported_pass: bool | None,
    evidence_refs: list,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit one location-scoped scale-gate assessment for independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    gate_id = _normalize_uuid(gate_id, "scale gate")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(measured_value, str) or not 1 <= len(measured_value.strip()) <= 1000:
        raise SolutionLifecycleActionInvalid("Measured value must contain 1 to 1,000 characters")
    if isinstance(sample_size, bool) or not isinstance(sample_size, int) or not 1 <= sample_size <= 10_000_000:
        raise SolutionLifecycleActionInvalid("Sample size must be an integer from 1 to 10,000,000")
    if reported_pass is not None and not isinstance(reported_pass, bool):
        raise SolutionLifecycleActionInvalid("Reported gate result must be true, false, or null")
    if not isinstance(evidence_refs, list) or not evidence_refs or len(evidence_refs) > 100:
        raise SolutionLifecycleActionInvalid("Assessment evidence must contain 1 to 100 references")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Scale-gate assessment acknowledgement is required")
    try:
        encoded_evidence = json.dumps(
            evidence_refs, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Assessment evidence must contain JSON data") from exc
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Assessment evidence exceeds the 64 KiB limit")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.submit_location_solution_scale_gate_assessment(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::integer,
                           %s::boolean, %s::jsonb
                       )""",
                (
                    location_id, gate_id, request_id, measured_value.strip(),
                    sample_size, reported_pass, encoded_evidence,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Scale-gate assessment returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_solution_scale_gate_assessment(
    operator_id: str,
    location_id: str,
    assessment_id: str,
    request_id: str,
    decision: str,
    review_reason: str | None,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record an independent human decision for a pending scale-gate assessment."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    assessment_id = _normalize_uuid(assessment_id, "assessment")
    request_id = _normalize_uuid(request_id, "request")
    if decision not in {"accepted", "rejected"}:
        raise SolutionLifecycleActionInvalid("Scale-gate decision must be accepted or rejected")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Scale-gate review acknowledgement is required")
    if review_reason is not None and (
        not isinstance(review_reason, str)
        or not review_reason.strip()
        or len(review_reason) > 4000
    ):
        raise SolutionLifecycleActionInvalid("Scale-gate review note is limited to 4,000 characters")
    if decision == "rejected" and (
        review_reason is None or len(review_reason.strip()) < 10
    ):
        raise SolutionLifecycleActionInvalid("A rejection reason of at least 10 characters is required")
    normalized_reason = review_reason.strip() if review_reason is not None else None

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.review_location_solution_scale_gate_assessment(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text
                       )""",
                (location_id, assessment_id, request_id, decision, normalized_reason),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Scale-gate review returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def approve_location_solution_gate(
    operator_id: str,
    location_id: str,
    gate_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Approve a passing location-origin gate by a distinct active reviewer."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    gate_id = _normalize_uuid(gate_id, "gate")
    request_id = _normalize_uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.approve_location_solution_gate(
                           %s::uuid, %s::uuid, %s::uuid
                       )""",
                (location_id, gate_id, request_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution gate approval returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_solution_experiment(
    operator_id: str,
    location_id: str,
    experiment_id: str,
    request_id: str,
    outcome: str,
    primary_results: dict,
    secondary_results: dict,
    limitations: str | None,
    evidence: list,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record one independent human result review for a completed location experiment."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    experiment_id = _normalize_uuid(experiment_id, "experiment")
    request_id = _normalize_uuid(request_id, "request")
    if outcome not in EXPERIMENT_OUTCOMES:
        raise SolutionLifecycleActionInvalid("Experiment review outcome is invalid")
    if not isinstance(primary_results, dict) or not isinstance(secondary_results, dict):
        raise SolutionLifecycleActionInvalid("Experiment results must be JSON objects")
    if limitations is not None and (
        not isinstance(limitations, str) or len(limitations) > 4000
    ):
        raise SolutionLifecycleActionInvalid("Experiment limitations must be at most 4000 characters")
    if not isinstance(evidence, list) or len(evidence) > 100:
        raise SolutionLifecycleActionInvalid("Experiment evidence must be a list of at most 100 items")
    try:
        encoded_primary = json.dumps(
            primary_results, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        encoded_secondary = json.dumps(
            secondary_results, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        encoded_evidence = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Experiment review values must contain JSON data") from exc
    if any(len(value.encode("utf-8")) > 65536 for value in (
        encoded_primary, encoded_secondary, encoded_evidence
    )):
        raise SolutionLifecycleActionInvalid("Experiment review values exceed the 64 KiB limit")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.review_location_solution_experiment(
                           %s::uuid, %s::uuid, %s::uuid, %s::text,
                           %s::jsonb, %s::jsonb, %s::text, %s::jsonb
                       )""",
                (
                    location_id,
                    experiment_id,
                    request_id,
                    outcome,
                    encoded_primary,
                    encoded_secondary,
                    limitations,
                    encoded_evidence,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution experiment review returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def propose_location_solution_funding(
    operator_id: str,
    location_id: str,
    solution_id: str,
    request_id: str,
    capital_stage: str,
    funding_instrument: str,
    requested_amount,
    minimum_viable_amount,
    maximum_authorized_amount,
    currency: str,
    risk_adjusted_expected_value,
    public_goods_value,
    community_share,
    downside_exposure,
    rationale: str,
    evidence: list,
    tranches: list,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create an exact-location funding draft and proposed tranches only."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    solution_id = _normalize_uuid(solution_id, "solution")
    request_id = _normalize_uuid(request_id, "request")
    if capital_stage not in FUNDING_CAPITAL_STAGES:
        raise SolutionLifecycleActionInvalid("Funding capital stage is invalid")
    if funding_instrument not in FUNDING_INSTRUMENTS:
        raise SolutionLifecycleActionInvalid("Funding instrument is invalid")
    amounts = (
        _normalize_funding_amount(requested_amount, "Requested amount", required=True),
        _normalize_funding_amount(minimum_viable_amount, "Minimum viable amount"),
        _normalize_funding_amount(maximum_authorized_amount, "Maximum authorized amount"),
        _normalize_funding_amount(risk_adjusted_expected_value, "Risk-adjusted expected value"),
        _normalize_funding_amount(public_goods_value, "Public-goods value"),
        _normalize_funding_amount(community_share, "Community share"),
        _normalize_funding_amount(downside_exposure, "Downside exposure"),
    )
    requested = Decimal(amounts[0])
    minimum = Decimal(amounts[1]) if amounts[1] is not None else None
    maximum = Decimal(amounts[2]) if amounts[2] is not None else None
    if requested < 0:
        raise SolutionLifecycleActionInvalid("Requested amount must be nonnegative")
    if minimum is not None and minimum < 0:
        raise SolutionLifecycleActionInvalid("Minimum viable amount must be nonnegative")
    if maximum is not None and maximum < requested:
        raise SolutionLifecycleActionInvalid("Maximum authorized amount cannot be below the request")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise SolutionLifecycleActionInvalid("Minimum viable amount cannot exceed the maximum")
    if not isinstance(currency, str) or re.fullmatch(r"[A-Za-z0-9._-]{2,10}", currency) is None:
        raise SolutionLifecycleActionInvalid("Currency must be a 2 to 10 character code")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 4000:
        raise SolutionLifecycleActionInvalid("Funding rationale must contain 1 to 4000 characters")
    if not isinstance(evidence, list) or len(evidence) > 100:
        raise SolutionLifecycleActionInvalid("Funding evidence must be a list of at most 100 items")
    if not isinstance(tranches, list) or len(tranches) > 50:
        raise SolutionLifecycleActionInvalid("Funding tranches must be a list of at most 50 items")
    try:
        encoded_evidence = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        tranche_parts = []
        tranche_total = Decimal("0")
        tranche_ceiling = maximum if maximum is not None else requested
        for tranche in tranches:
            if not isinstance(tranche, dict) or set(tranche) != {"amount", "milestone_conditions"}:
                raise SolutionLifecycleActionInvalid("Each funding tranche requires amount and milestone_conditions")
            amount = _normalize_funding_amount(
                tranche["amount"], "Tranche amount", required=True
            )
            if Decimal(amount) < 0:
                raise SolutionLifecycleActionInvalid("Tranche amount must be nonnegative")
            conditions = tranche["milestone_conditions"]
            if not isinstance(conditions, dict):
                raise SolutionLifecycleActionInvalid("Tranche milestone conditions must be a JSON object")
            encoded_conditions = json.dumps(
                conditions, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
            if len(encoded_conditions.encode("utf-8")) > 8192:
                raise SolutionLifecycleActionInvalid("Tranche milestone conditions exceed 8 KiB")
            tranche_parts.append(
                f'{{"amount":{amount},"milestone_conditions":{encoded_conditions}}}'
            )
            tranche_total += Decimal(amount)
        encoded_tranches = "[" + ",".join(tranche_parts) + "]"
    except SolutionLifecycleActionInvalid:
        raise
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Funding proposal values must contain JSON data") from exc
    if len(encoded_evidence.encode("utf-8")) > 65536 or len(encoded_tranches.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Funding evidence and tranches must fit within 64 KiB")
    if tranche_total > tranche_ceiling:
        raise SolutionLifecycleActionInvalid("Proposed tranche total exceeds the funding case ceiling")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.propose_location_solution_funding(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text,
                           %s::numeric, %s::numeric, %s::numeric, %s::text,
                           %s::numeric, %s::numeric, %s::numeric, %s::numeric,
                           %s::text, %s::jsonb, %s::jsonb
                       )""",
                (
                    location_id, solution_id, request_id, capital_stage,
                    funding_instrument, *amounts[:3], currency, *amounts[3:],
                    rationale, encoded_evidence, encoded_tranches,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Funding proposal returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def submit_location_solution_funding(
    operator_id: str,
    location_id: str,
    funding_case_id: str,
    request_id: str,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit one Kernel-created exact-location funding draft for review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    funding_case_id = _normalize_uuid(funding_case_id, "funding case")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Funding submission requires explicit acknowledgement"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="submit",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.submit_location_solution_funding(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean
                       )""",
                (location_id, funding_case_id, request_id, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Funding submission returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def approve_location_solution_funding(
    operator_id: str,
    location_id: str,
    funding_case_id: str,
    request_id: str,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Independently approve one submitted exact-location funding case."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    funding_case_id = _normalize_uuid(funding_case_id, "funding case")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Funding approval requires explicit acknowledgement"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.approve_location_solution_funding(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean
                       )""",
                (location_id, funding_case_id, request_id, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Funding approval returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def approve_location_solution_funding_tranche(
    operator_id: str,
    location_id: str,
    funding_case_id: str,
    tranche_id: str,
    request_id: str,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Independently approve one proposed tranche without releasing funds."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    funding_case_id = _normalize_uuid(funding_case_id, "funding case")
    tranche_id = _normalize_uuid(tranche_id, "tranche")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Funding tranche approval requires explicit acknowledgement"
        )

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.approve_location_solution_funding_tranche(
                           %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::boolean
                       )""",
                (location_id, funding_case_id, tranche_id, request_id, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Funding tranche approval returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def transition_location_solution_gate(
    operator_id: str,
    location_id: str,
    gate_id: str,
    request_id: str,
    rationale: str,
    evidence: list,
    rollback_plan: str | None = None,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Advance a location-origin solution through an approved passing gate."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    gate_id = _normalize_uuid(gate_id, "gate")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(rationale, str) or not 10 <= len(rationale.strip()) <= 4000:
        raise SolutionLifecycleActionInvalid(
            "Transition rationale must contain between 10 and 4000 characters"
        )
    if not isinstance(evidence, list) or not evidence or len(evidence) > 100:
        raise SolutionLifecycleActionInvalid(
            "Transition evidence must be a nonempty list of at most 100 items"
        )
    if rollback_plan is not None and (
        not isinstance(rollback_plan, str) or len(rollback_plan) > 4000
    ):
        raise SolutionLifecycleActionInvalid(
            "Transition rollback plan must be at most 4000 characters"
        )
    try:
        encoded_evidence = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid(
            "Transition evidence must contain JSON values"
        ) from exc
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Transition evidence exceeds the 64 KiB limit")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="transition",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.transition_location_solution_gate(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::jsonb, %s::text
                       )""",
                (
                    location_id,
                    gate_id,
                    request_id,
                    rationale.strip(),
                    encoded_evidence,
                    rollback_plan,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution gate transition returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def transition_location_solution_stage(
    operator_id: str,
    location_id: str,
    solution_id: str,
    expected_from_stage: str,
    to_stage: str,
    request_id: str,
    rationale: str,
    evidence: list,
    rollback_plan: str | None = None,
    acknowledged: bool = False,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record an acknowledged exact-location non-promotion stage transition."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    solution_id = _normalize_uuid(solution_id, "solution")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(expected_from_stage, str) or expected_from_stage not in SOLUTION_STAGES:
        raise SolutionLifecycleActionInvalid("Invalid expected solution stage")
    if not isinstance(to_stage, str) or to_stage not in NONPROMOTION_SOLUTION_STAGES:
        raise SolutionLifecycleActionInvalid(
            "Promotion and retirement stages require their dedicated workflows"
        )
    if expected_from_stage == to_stage:
        raise SolutionLifecycleActionInvalid("A solution cannot transition to its current stage")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Stage transition requires explicit acknowledgement")
    if not isinstance(rationale, str) or not 10 <= len(rationale.strip()) <= 4000:
        raise SolutionLifecycleActionInvalid(
            "Transition rationale must contain between 10 and 4000 characters"
        )
    if not isinstance(evidence, list) or not evidence or len(evidence) > 100:
        raise SolutionLifecycleActionInvalid(
            "Transition evidence must be a nonempty list of at most 100 items"
        )
    if rollback_plan is not None and (
        not isinstance(rollback_plan, str) or len(rollback_plan) > 4000
    ):
        raise SolutionLifecycleActionInvalid(
            "Transition rollback plan must be at most 4000 characters"
        )
    try:
        encoded_evidence = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid(
            "Transition evidence must contain JSON values"
        ) from exc
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Transition evidence exceeds the 64 KiB limit")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="transition",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.transition_location_solution_stage(
                           %s::uuid, %s::uuid, %s::text, %s::text, %s::uuid,
                           %s::text, %s::jsonb, %s::text, %s::boolean
                       )""",
                (
                    location_id,
                    solution_id,
                    expected_from_stage,
                    to_stage,
                    request_id,
                    rationale.strip(),
                    encoded_evidence,
                    rollback_plan,
                    acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution stage transition returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def approve_location_solution_retirement(
    operator_id: str,
    location_id: str,
    retirement_id: str,
    request_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Approve a location-originated retirement with an idempotent review receipt."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    retirement_id = _normalize_uuid(retirement_id, "retirement")
    request_id = _normalize_uuid(request_id, "request")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.approve_location_solution_retirement(
                           %s::uuid, %s::uuid, %s::uuid
                       )""",
                (location_id, retirement_id, request_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution retirement approval returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def transition_location_solution_retirement(
    operator_id: str,
    location_id: str,
    retirement_id: str,
    request_id: str,
    action: str,
    note: str,
    evidence_refs: list,
    effective_at: str | None,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Advance an approved exact-location retirement with an immutable receipt."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    retirement_id = _normalize_uuid(retirement_id, "retirement")
    request_id = _normalize_uuid(request_id, "request")
    if action not in {"migration_started", "sunset", "post_retirement_review"}:
        raise SolutionLifecycleActionInvalid("Unsupported retirement transition")
    if not isinstance(note, str) or not 10 <= len(note.strip()) <= 4000:
        raise SolutionLifecycleActionInvalid("Retirement transition note must contain 10 to 4,000 characters")
    if not isinstance(evidence_refs, list) or not evidence_refs or len(evidence_refs) > 100:
        raise SolutionLifecycleActionInvalid("Retirement transition requires 1 to 100 evidence references")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Retirement transition acknowledgement is required")
    try:
        encoded_evidence = json.dumps(
            evidence_refs, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Retirement evidence must contain JSON values") from exc
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Retirement evidence exceeds the 64 KiB limit")

    normalized_effective_at = None
    if action == "migration_started":
        if not isinstance(effective_at, str) or not effective_at.strip():
            raise SolutionLifecycleActionInvalid("A timezone-aware sunset effective date is required")
        try:
            parsed_effective_at = datetime.fromisoformat(
                effective_at.strip().replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise SolutionLifecycleActionInvalid("Sunset effective date must be a valid ISO timestamp") from exc
        if parsed_effective_at.tzinfo is None or parsed_effective_at.utcoffset() is None:
            raise SolutionLifecycleActionInvalid("Sunset effective date must include a timezone")
        normalized_effective_at = parsed_effective_at.astimezone(timezone.utc).isoformat()
    elif effective_at is not None:
        raise SolutionLifecycleActionInvalid("Only migration start accepts an effective date")

    connection = (connection_factory or _connection_factory())()
    scope_action = "review" if action == "post_retirement_review" else "transition"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action=scope_action,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.transition_location_solution_retirement(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text,
                           %s::jsonb, %s::timestamptz
                       )""",
                (
                    location_id, retirement_id, request_id, action, note.strip(),
                    encoded_evidence, normalized_effective_at,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution retirement transition returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def propose_location_solution_retirement(
    operator_id: str,
    location_id: str,
    solution_id: str,
    request_id: str,
    retirement_type: str,
    trigger_reason: str,
    evidence_refs: list,
    migration_plan: str,
    replacement_solution_id: str | None = None,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a location-originated retirement proposal with an idempotent receipt."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    solution_id = _normalize_uuid(solution_id, "solution")
    request_id = _normalize_uuid(request_id, "request")
    if replacement_solution_id is not None:
        replacement_solution_id = _normalize_uuid(replacement_solution_id, "replacement solution")
    if not isinstance(retirement_type, str) or retirement_type not in RETIREMENT_TYPES:
        raise SolutionLifecycleActionInvalid("Invalid retirement type")
    if not isinstance(trigger_reason, str) or not trigger_reason.strip() or len(trigger_reason) > 2000:
        raise SolutionLifecycleActionInvalid("Retirement trigger reason is required and must be at most 2000 characters")
    if not isinstance(migration_plan, str) or not migration_plan.strip() or len(migration_plan) > 4000:
        raise SolutionLifecycleActionInvalid("Retirement migration plan is required and must be at most 4000 characters")
    if not isinstance(evidence_refs, list) or not evidence_refs or len(evidence_refs) > 100:
        raise SolutionLifecycleActionInvalid("Retirement evidence must be a nonempty list of at most 100 items")
    if retirement_type == "superseded" and replacement_solution_id is None:
        raise SolutionLifecycleActionInvalid("Superseded retirement requires a replacement solution")
    try:
        encoded_evidence = json.dumps(
            evidence_refs, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Retirement evidence must contain JSON values") from exc
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Retirement evidence exceeds the 64 KiB limit")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.propose_location_solution_retirement(
                           %s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, %s::uuid
                       )""",
                (
                    location_id,
                    solution_id,
                    request_id,
                    retirement_type,
                    trigger_reason,
                    encoded_evidence,
                    migration_plan,
                    replacement_solution_id,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution retirement proposal returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def propose_location_solution_learning(
    operator_id: str,
    location_id: str,
    replication_id: str,
    request_id: str,
    lesson_type: str,
    finding: str,
    recommended_action: str,
    evidence: list,
    *,
    confidence: str = "moderate",
    transferability: str = "unknown",
    affected_assumptions: list | None = None,
    affected_metrics: list | None = None,
    connection_factory: Callable | None = None,
) -> dict:
    """Create an attributed learning proposal from a reviewed location replication."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    replication_id = _normalize_uuid(replication_id, "replication")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(lesson_type, str) or lesson_type not in LEARNING_TYPES:
        raise SolutionLifecycleActionInvalid("Invalid learning lesson type")
    if not isinstance(confidence, str) or confidence not in LEARNING_CONFIDENCE:
        raise SolutionLifecycleActionInvalid("Invalid learning confidence")
    if not isinstance(transferability, str) or transferability not in LEARNING_TRANSFERABILITY:
        raise SolutionLifecycleActionInvalid("Invalid learning transferability")
    for value, name in ((finding, "finding"), (recommended_action, "recommended action")):
        if not isinstance(value, str) or not value.strip() or len(value) > 4000:
            raise SolutionLifecycleActionInvalid(
                f"Learning {name} is required and must be at most 4000 characters"
            )

    def encode_array(value: list | None, name: str, *, required: bool = False) -> str:
        if value is None and not required:
            value = []
        if not isinstance(value, list) or (required and not value) or len(value) > 100:
            qualifier = "a nonempty list" if required else "a list"
            raise SolutionLifecycleActionInvalid(
                f"Learning {name} must be {qualifier} of at most 100 items"
            )
        try:
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise SolutionLifecycleActionInvalid(f"Learning {name} must contain JSON values") from exc
        if len(encoded.encode("utf-8")) > 65536:
            raise SolutionLifecycleActionInvalid(f"Learning {name} exceeds the 64 KiB limit")
        return encoded

    encoded_assumptions = encode_array(affected_assumptions, "affected assumptions")
    encoded_metrics = encode_array(affected_metrics, "affected metrics")
    encoded_evidence = encode_array(evidence, "evidence", required=True)

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.propose_location_solution_learning(
                           %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s,
                           %s::jsonb, %s::jsonb, %s, %s::jsonb
                       )""",
                (
                    location_id,
                    replication_id,
                    request_id,
                    lesson_type,
                    finding,
                    confidence,
                    transferability,
                    encoded_assumptions,
                    encoded_metrics,
                    recommended_action,
                    encoded_evidence,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution learning proposal returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def propose_location_solution_replication(
    operator_id: str,
    location_id: str,
    source_experiment_id: str,
    request_id: str,
    target_context: str,
    adaptation_required: str | None,
    replication_protocol: dict,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Create a draft replication proposal from a validated source experiment."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    source_experiment_id = _normalize_uuid(source_experiment_id, "source experiment")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(target_context, str) or not target_context.strip() or len(target_context) > 2000:
        raise SolutionLifecycleActionInvalid(
            "Replication target context is required and limited to 2,000 characters"
        )
    if adaptation_required is not None and (
        not isinstance(adaptation_required, str)
        or not adaptation_required.strip()
        or len(adaptation_required) > 4000
    ):
        raise SolutionLifecycleActionInvalid(
            "Replication adaptation is optional and limited to 4,000 characters"
        )
    if not isinstance(replication_protocol, dict):
        raise SolutionLifecycleActionInvalid("Replication protocol must be a JSON object")
    try:
        encoded_protocol = json.dumps(
            replication_protocol, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Replication protocol must contain JSON values") from exc
    if len(encoded_protocol.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Replication protocol exceeds the 64 KiB limit")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.propose_location_solution_replication(
                           %s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb
                       )""",
                (
                    location_id,
                    source_experiment_id,
                    request_id,
                    target_context,
                    adaptation_required,
                    encoded_protocol,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution replication proposal returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_solution_replication(
    operator_id: str,
    location_id: str,
    replication_id: str,
    request_id: str,
    decision: str,
    review_reason: str | None,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Record one independent approve/reject decision for a proposed replication."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    replication_id = _normalize_uuid(replication_id, "replication")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(decision, str) or decision not in {"approved", "rejected"}:
        raise SolutionLifecycleActionInvalid("Replication decision must be approved or rejected")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Replication review acknowledgement is required")
    if review_reason is not None and (
        not isinstance(review_reason, str)
        or not review_reason.strip()
        or len(review_reason) > 4000
    ):
        raise SolutionLifecycleActionInvalid("Replication review reason is limited to 4,000 characters")
    if decision == "rejected" and (
        review_reason is None or len(review_reason.strip()) < 10
    ):
        raise SolutionLifecycleActionInvalid("A rejection reason of at least 10 characters is required")
    normalized_reason = review_reason.strip() if review_reason is not None else None

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.review_location_solution_replication(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text, %s::boolean
                       )""",
                (
                    location_id,
                    replication_id,
                    request_id,
                    decision,
                    normalized_reason,
                    acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution replication review returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_solution_replication_completion(
    operator_id: str,
    location_id: str,
    replication_id: str,
    proposal_id: str,
    request_id: str,
    decision: str,
    review_reason: str | None,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Accept or reject a completion report with independent human review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    replication_id = _normalize_uuid(replication_id, "replication")
    proposal_id = _normalize_uuid(proposal_id, "proposal")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(decision, str) or decision not in {"accepted", "rejected"}:
        raise SolutionLifecycleActionInvalid(
            "Completion report decision must be accepted or rejected"
        )
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid(
            "Completion report review acknowledgement is required"
        )
    if review_reason is not None and (
        not isinstance(review_reason, str)
        or not review_reason.strip()
        or len(review_reason) > 4000
    ):
        raise SolutionLifecycleActionInvalid(
            "Completion review reason is limited to 4,000 characters"
        )
    if decision == "rejected" and (
        review_reason is None or len(review_reason.strip()) < 10
    ):
        raise SolutionLifecycleActionInvalid(
            "A rejection reason of at least 10 characters is required"
        )
    normalized_reason = review_reason.strip() if review_reason is not None else None

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.review_location_solution_replication_completion(
                           %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                           %s::text, %s::text, %s::boolean
                       )""",
                (
                    location_id,
                    replication_id,
                    proposal_id,
                    request_id,
                    decision,
                    normalized_reason,
                    acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Replication completion review returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def activate_location_solution_replication(
    operator_id: str,
    location_id: str,
    replication_id: str,
    request_id: str,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Start one approved replication under an exact location transition grant."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    replication_id = _normalize_uuid(replication_id, "replication")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Replication activation acknowledgement is required")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="transition",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.activate_location_solution_replication(
                           %s::uuid, %s::uuid, %s::uuid, %s::boolean
                       )""",
                (location_id, replication_id, request_id, acknowledged),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution replication activation returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def propose_location_solution_replication_completion(
    operator_id: str,
    location_id: str,
    replication_id: str,
    request_id: str,
    outcome: str,
    evidence_maturity: int,
    outcome_summary: str,
    evidence: list,
    *,
    acknowledged: bool,
    connection_factory: Callable | None = None,
) -> dict:
    """Submit a private completion report for independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    replication_id = _normalize_uuid(replication_id, "replication")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Completion report acknowledgement is required")
    if not isinstance(outcome, str) or outcome not in REPLICATION_COMPLETION_OUTCOMES:
        raise SolutionLifecycleActionInvalid("Replication outcome is invalid")
    if isinstance(evidence_maturity, bool) or not isinstance(evidence_maturity, int) or not 1 <= evidence_maturity <= 6:
        raise SolutionLifecycleActionInvalid("Evidence maturity must be an integer from 1 to 6")
    if not isinstance(outcome_summary, str) or not 10 <= len(outcome_summary.strip()) <= 4000:
        raise SolutionLifecycleActionInvalid("Outcome summary must contain 10 to 4,000 non-whitespace characters")
    if not isinstance(evidence, list) or len(evidence) > 100:
        raise SolutionLifecycleActionInvalid("Completion evidence must be a JSON array with at most 100 items")
    try:
        encoded_evidence = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise SolutionLifecycleActionInvalid("Completion evidence must contain JSON values") from exc
    if len(encoded_evidence.encode("utf-8")) > 65536:
        raise SolutionLifecycleActionInvalid("Completion evidence exceeds the 64 KiB limit")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="submit",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.propose_location_solution_replication_completion(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::integer,
                           %s::text, %s::jsonb
                       )""",
                (
                    location_id,
                    replication_id,
                    request_id,
                    outcome,
                    evidence_maturity,
                    outcome_summary.strip(),
                    encoded_evidence,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution replication completion proposal returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def review_location_solution_learning(
    operator_id: str,
    location_id: str,
    learning_record_id: str,
    request_id: str,
    decision: str,
    review_reason: str | None,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Accept or reject one current learning proposal with independent review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    learning_record_id = _normalize_uuid(learning_record_id, "learning record")
    request_id = _normalize_uuid(request_id, "request")
    if not isinstance(decision, str) or decision not in {"accepted", "rejected"}:
        raise SolutionLifecycleActionInvalid("Learning decision must be accepted or rejected")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Learning review acknowledgement is required")
    if review_reason is not None and (
        not isinstance(review_reason, str)
        or not review_reason.strip()
        or len(review_reason) > 4000
    ):
        raise SolutionLifecycleActionInvalid(
            "Learning review reason is limited to 4,000 characters"
        )
    if decision == "rejected" and (
        review_reason is None or len(review_reason.strip()) < 10
    ):
        raise SolutionLifecycleActionInvalid(
            "A rejection reason of at least 10 characters is required"
        )
    normalized_reason = review_reason.strip() if review_reason is not None else None

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="review",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.review_location_solution_learning(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::text, %s::boolean
                       )""",
                (
                    location_id,
                    learning_record_id,
                    request_id,
                    decision,
                    normalized_reason,
                    acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution learning review returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def apply_location_solution_learning(
    operator_id: str,
    location_id: str,
    learning_record_id: str,
    request_id: str,
    applied_to_version: str,
    acknowledged: bool,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Apply accepted learning through the exact-location bounded function."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    learning_record_id = _normalize_uuid(learning_record_id, "learning record")
    request_id = _normalize_uuid(request_id, "request")
    if acknowledged is not True:
        raise SolutionLifecycleActionInvalid("Learning application acknowledgement is required")
    if (
        not isinstance(applied_to_version, str)
        or not 1 <= len(applied_to_version.strip()) <= 80
    ):
        raise SolutionLifecycleActionInvalid(
            "Applied-to version must contain 1 to 80 non-whitespace characters"
        )
    normalized_version = applied_to_version.strip()

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="apply",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.apply_location_solution_learning(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::boolean
                       )""",
                (
                    location_id,
                    learning_record_id,
                    request_id,
                    normalized_version,
                    acknowledged,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Solution learning application returned no result")
            result = _mapping(cursor, row)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
