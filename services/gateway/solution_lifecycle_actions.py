"""Tenant-scoped, human-reviewed solution lifecycle actions."""

from __future__ import annotations

import json
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
