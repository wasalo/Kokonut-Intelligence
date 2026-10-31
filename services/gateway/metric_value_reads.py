"""Location-scoped metric review reads through a bounded database function.

The final migration must provide
``kokonut_security.list_location_metric_values(UUID location_id, TEXT cursor,
INTEGER limit) RETURNS JSONB``. The function requires the signed
``metric_value:read`` context, reads only rows for the exact current location,
orders them by ``computed_at DESC, id DESC``, treats the canonical decimal
cursor as an offset capped at 10,000, clamps page size to 1–100, and returns
the cursor and limit unchanged. The exact page contains ``location_id,
cursor, limit, next_cursor, has_more, items``; each item contains only metric
value ID/key/display name, period dates, value/unit, draft-or-verified status,
and computed/verified timestamps. It must not return source record IDs,
metadata, reviewer identity, verification notes, or other row fields.
"""

from __future__ import annotations

import json
import re
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import TenantContextDenied, set_operator_tenant_context
from services.gateway.metric_value_contracts import MetricValueListResponse


class MetricValueReadInvalid(ValueError):
    """The location or pagination request is invalid."""


class MetricValueReadNotFound(LookupError):
    """The location-scoped metric list is unavailable."""


class MetricValueReadReceiptInvalid(RuntimeError):
    """The bounded list function returned invalid or overbroad data."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: object, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise MetricValueReadInvalid(f"Invalid {label} identifier") from exc


def _cursor(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"(0|[1-9][0-9]*)", value):
        raise MetricValueReadInvalid("cursor must be a canonical decimal offset")
    if int(value) > 10_000:
        raise MetricValueReadInvalid("cursor exceeds the 10,000-row boundary")
    return value


def _function_error(exc) -> None:
    sqlstate = getattr(exc, "pgcode", None)
    if sqlstate == "42501":
        raise TenantContextDenied("Metric read requires a current location grant") from exc
    if sqlstate == "P0002":
        raise MetricValueReadNotFound("Metric list is unavailable in this location") from exc
    if sqlstate in {"22003", "22023", "23514"}:
        raise MetricValueReadInvalid("Metric read parameters are invalid") from exc
    raise exc


def list_location_metric_values(
    operator_id: str,
    location_id: str,
    cursor: str,
    limit: int,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Return the private, identity-minimized review page for one location."""
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    cursor = _cursor(cursor)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise MetricValueReadInvalid("limit must be an integer between 1 and 100")

    connection = (connection_factory or _connection_factory())()
    committed = False
    try:
        with connection.cursor() as db_cursor:
            db_cursor.execute("SET LOCAL statement_timeout = '8s'")
            db_cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="metric_value",
            action="read",
        )
        with connection.cursor() as db_cursor:
            try:
                db_cursor.execute(
                    """SELECT kokonut_security.list_location_metric_values(
                               %s::uuid, %s::text, %s::integer
                           )""",
                    (location_id, cursor, limit),
                )
            except Exception as exc:
                _function_error(exc)
            row = db_cursor.fetchone()
        if row is None or row[0] is None:
            raise MetricValueReadNotFound("Metric list is unavailable")
        payload = row[0]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError, RecursionError) as exc:
                raise MetricValueReadReceiptInvalid("Metric page JSON is invalid") from exc
        if not isinstance(payload, dict):
            raise MetricValueReadReceiptInvalid("Metric page must be an object")
        try:
            page = MetricValueListResponse.model_validate(payload)
        except Exception as exc:
            raise MetricValueReadReceiptInvalid("Metric page failed contract validation") from exc
        if page.location_id != UUID(location_id) or page.cursor != cursor or page.limit != limit:
            raise MetricValueReadReceiptInvalid("Metric page does not match request scope")
        connection.commit()
        committed = True
        return page.model_dump(mode="json")
    finally:
        if not committed:
            connection.rollback()
        connection.close()
