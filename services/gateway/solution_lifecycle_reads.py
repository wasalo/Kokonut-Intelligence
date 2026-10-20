"""Location-scoped, aggregate-only Kernel projections for solution lifecycle."""

from __future__ import annotations

import json
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class SolutionLifecycleReadInvalid(ValueError):
    """A solution lifecycle read identifier or page value is invalid."""


class SolutionLifecycleResponseTooLarge(ValueError):
    """A bounded solution lifecycle page exceeds the response budget."""


class SolutionLifecycleReviewNotFound(LookupError):
    """A pending exact-location solution lifecycle review item was not found."""


class SolutionLifecycleRecordNotFound(LookupError):
    """An exact-location solution lifecycle record was not found."""


_MAX_READ_PAGE_SIZE = 50
_MAX_READ_RESPONSE_BYTES = 262_144


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise SolutionLifecycleReadInvalid(f"Invalid {field} identifier") from exc


def _page_value(value: int | str, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise SolutionLifecycleReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SolutionLifecycleReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        ) from exc
    if str(parsed) != str(value).strip() or not minimum <= parsed <= maximum:
        raise SolutionLifecycleReadInvalid(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    return parsed


def _mapping(cursor, row) -> dict:
    return dict(zip((column.name for column in (cursor.description or ())), row))


def get_location_solution_lifecycle_summary(
    operator_id: str,
    location_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return aggregate lifecycle health for solutions explicitly linked to a location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT kokonut_security.location_solution_lifecycle_summary(%s::uuid)",
                (location_id,),
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError("Solution lifecycle summary returned no result")
            summary = row[0]
            if isinstance(summary, str):
                import json

                summary = json.loads(summary)
            return {"location_id": location_id, **summary}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_gates(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded gate items for solutions explicitly scoped to a location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_solution_gates(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "gates": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution lifecycle gate page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_solution_gate_review(
    operator_id: str,
    location_id: str,
    gate_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return private evidence for one exact-origin gate review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    gate_id = _normalize_uuid(gate_id, "gate")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
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
                """SELECT * FROM kokonut_security.location_solution_gate_review(
                           %s::uuid, %s::uuid
                       )""",
                (location_id, gate_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise SolutionLifecycleReviewNotFound(
                    "Location-origin solution gate was not found"
                )
            result = _mapping(cursor, row)
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution gate review detail exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_solution_experiment_review(
    operator_id: str,
    location_id: str,
    experiment_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded private evidence for one pending exact-origin experiment review."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    experiment_id = _normalize_uuid(experiment_id, "experiment")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
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
                """SELECT * FROM kokonut_security.location_solution_experiment_review(
                           %s::uuid, %s::uuid
                       )""",
                (location_id, experiment_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise SolutionLifecycleReviewNotFound(
                    "Pending exact-location solution experiment review was not found"
                )
            result = _mapping(cursor, row)
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution experiment review detail exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_experiments(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded experiment status for solutions explicitly scoped to a location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_solution_experiments(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "experiments": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution lifecycle experiment page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_funding(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded funding and tranche lifecycle labels for location solutions."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_solution_funding(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "funding": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution lifecycle funding page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_funding_review_queue(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return submitted funding cases for an exact-location human reviewer."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
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
                """SELECT * FROM kokonut_security.list_location_solution_funding_review_queue(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "funding_cases": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution lifecycle funding review page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_solution_funding_review_detail(
    operator_id: str,
    location_id: str,
    funding_case_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded private terms for one submitted exact-location funding case."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    funding_case_id = _normalize_uuid(funding_case_id, "funding case")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
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
                """SELECT * FROM kokonut_security.get_location_solution_funding_review_detail(
                           %s::uuid, %s::uuid
                       )""",
                (location_id, funding_case_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise SolutionLifecycleReviewNotFound(
                    "Submitted funding case was not found"
                )
            result = _mapping(cursor, row)
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution lifecycle funding review detail exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_solution_funding_tranche_review_detail(
    operator_id: str,
    location_id: str,
    funding_case_id: str,
    tranche_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded private terms for one exact-location funding tranche."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    funding_case_id = _normalize_uuid(funding_case_id, "funding case")
    tranche_id = _normalize_uuid(tranche_id, "tranche")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
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
                """SELECT * FROM kokonut_security.get_location_solution_funding_tranche_review_detail(
                           %s::uuid, %s::uuid, %s::uuid
                       )""",
                (location_id, funding_case_id, tranche_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise SolutionLifecycleReviewNotFound(
                    "Exact-location funding tranche was not found"
                )
            result = _mapping(cursor, row)
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution funding tranche review detail exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_funding_targets(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded exact-location-origin solutions for funding drafts."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_solution_funding_targets(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "solutions": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution funding target page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_adoption(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded adoption program status and privacy-suppressed event counts."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_solution_adoption(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "programs": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution lifecycle adoption page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_solution_adoption_event_summary(
    operator_id: str,
    location_id: str,
    program_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return small-cohort-suppressed progress phases for one adoption program."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    program_id = _normalize_uuid(program_id, "adoption program")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.get_location_solution_adoption_event_summary(
                           %s::uuid, %s::uuid
                       )""",
                (location_id, program_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise SolutionLifecycleRecordNotFound(
                    "Exact-location adoption program was not found"
                )
            summary = _mapping(cursor, row)
        result = {"location_id": location_id, **summary}
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution adoption event summary exceeds 256 KiB"
            )
        return result
    except Exception as exc:
        connection.rollback()
        if getattr(exc, "pgcode", None) == "P0002":
            raise SolutionLifecycleRecordNotFound(
                "Exact-location adoption program was not found"
            ) from exc
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_scale_gates(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return location-scoped scale gate status and approval presence."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_solution_scale_gates(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "scale_gates": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution scale-gate page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_replications(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded status for replications targeting a granted location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_solution_replications(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "replications": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution replication page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_learning(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded learning status grounded in reviewed location replications."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_solution_learning(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "learning": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution learning page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_retirements(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded retirement metadata for solutions originated at a location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_solution_retirements(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "retirements": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution retirement page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_retirement_candidates(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded retirement proposal choices originating at a location."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="solution_lifecycle",
            action="read",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.list_location_solution_retirement_candidates(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "solutions": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution retirement candidate page exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def list_location_solution_retirement_review_queue(
    operator_id: str,
    location_id: str,
    *,
    limit: int | str = 25,
    offset: int | str = 0,
    connection_factory: Callable | None = None,
) -> dict:
    """Return the bounded pending retirement queue for a scoped human reviewer."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    page_size = _page_value(limit, "Limit", 1, _MAX_READ_PAGE_SIZE)
    page_offset = _page_value(offset, "Offset", 0, 10000)
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
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
                """SELECT * FROM kokonut_security.list_location_solution_retirement_review_queue(
                           %s::uuid, %s::integer, %s::integer
                       )""",
                (location_id, page_size + 1, page_offset),
            )
            rows = [_mapping(cursor, row) for row in cursor.fetchall()]
        has_more = len(rows) > page_size
        result = {
            "location_id": location_id,
            "offset": page_offset,
            "retirements": rows[:page_size],
            "has_more": has_more,
            "next_offset": page_offset + page_size if has_more else None,
        }
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution retirement review queue exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def get_location_solution_retirement_review_detail(
    operator_id: str,
    location_id: str,
    retirement_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return bounded proposal detail only to a reviewer with exact location scope."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    retirement_id = _normalize_uuid(retirement_id, "retirement")
    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
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
                """SELECT * FROM kokonut_security.get_location_solution_retirement_review_detail(
                           %s::uuid, %s::uuid
                       )""",
                (location_id, retirement_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise SolutionLifecycleReviewNotFound(
                    "Pending location-origin retirement review was not found"
                )
            result = {"location_id": location_id, **_mapping(cursor, row)}
        size = len(json.dumps(result, default=str, separators=(",", ":")).encode("utf-8"))
        if size > _MAX_READ_RESPONSE_BYTES:
            raise SolutionLifecycleResponseTooLarge(
                "Solution retirement review detail exceeds 256 KiB"
            )
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
