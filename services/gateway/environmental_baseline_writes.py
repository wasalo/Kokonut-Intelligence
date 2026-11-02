"""Location-scoped environmental-baseline capture through a bounded RPC."""

from __future__ import annotations

import json
import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context

_METRIC_NAME = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")
_MAX_BASELINE_VALUE = Decimal("99999999.9999")
_QUANTUM = Decimal("0.0001")


class EnvironmentalBaselineCaptureInvalid(ValueError):
    """A baseline capture is malformed or outside its supported bounds."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _uuid(value: object, label: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise EnvironmentalBaselineCaptureInvalid(f"Invalid {label} identifier") from exc


def _text(value: object, field: str, maximum: int, *, optional: bool = False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise EnvironmentalBaselineCaptureInvalid(f"Invalid {field}")
    normalized = value.strip()
    if len(normalized) > maximum or _CONTROL_CHARACTER.search(value):
        raise EnvironmentalBaselineCaptureInvalid(f"Invalid {field}")
    return normalized or None


def _number(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise EnvironmentalBaselineCaptureInvalid("baseline_value must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise EnvironmentalBaselineCaptureInvalid("baseline_value must be finite")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise EnvironmentalBaselineCaptureInvalid("baseline_value must be numeric") from exc
    if (
        not number.is_finite()
        or abs(number) > _MAX_BASELINE_VALUE
        or number != number.quantize(_QUANTUM)
    ):
        raise EnvironmentalBaselineCaptureInvalid(
            "baseline_value exceeds NUMERIC(12,4) bounds"
        )
    return number


def _date(value: object) -> date:
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    if isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError as exc:
            raise EnvironmentalBaselineCaptureInvalid(
                "measurement_date must use YYYY-MM-DD"
            ) from exc
        if result.isoformat() == value:
            return result
    raise EnvironmentalBaselineCaptureInvalid("measurement_date must use YYYY-MM-DD")


def _normalize_payload(payload: object) -> tuple:
    expected = {
        "request_id", "plot_id", "metric_name", "baseline_value", "unit",
        "measurement_date", "measurement_method", "source", "evidence_urls", "notes",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise EnvironmentalBaselineCaptureInvalid("Baseline capture fields are invalid")

    request_id = _uuid(payload["request_id"], "request")
    plot_id = _uuid(payload["plot_id"], "plot", optional=True)
    metric_name = _text(payload["metric_name"], "metric_name", 100)
    if not metric_name or not _METRIC_NAME.fullmatch(metric_name.lower()):
        raise EnvironmentalBaselineCaptureInvalid("metric_name must be a lowercase identifier")
    metric_name = metric_name.lower()
    baseline_value = _number(payload["baseline_value"])
    unit = _text(payload["unit"], "unit", 50, optional=True)
    measurement_date = _date(payload["measurement_date"])
    measurement_method = _text(payload["measurement_method"], "measurement_method", 100)
    if not measurement_method:
        raise EnvironmentalBaselineCaptureInvalid("measurement_method is required")
    source = _text(payload["source"], "source", 255, optional=True)
    notes = _text(payload["notes"], "notes", 2000, optional=True)

    evidence_urls = payload["evidence_urls"]
    if not isinstance(evidence_urls, list) or len(evidence_urls) > 10:
        raise EnvironmentalBaselineCaptureInvalid("evidence_urls must contain at most 10 URLs")
    normalized_urls = []
    for url in evidence_urls:
        if (
            not isinstance(url, str)
            or not url.startswith(("http://", "https://"))
            or len(url) > 2048
            or _CONTROL_CHARACTER.search(url)
            or any(character.isspace() for character in url)
        ):
            raise EnvironmentalBaselineCaptureInvalid("evidence_urls contains an invalid URL")
        normalized_urls.append(url)

    return (
        request_id,
        plot_id,
        metric_name,
        baseline_value,
        unit,
        measurement_date,
        measurement_method,
        source,
        normalized_urls,
        notes,
    )


def _receipt(row) -> dict:
    if row is None or row[0] is None:
        raise RuntimeError("Environmental baseline capture returned no receipt")
    result = row[0]
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (TypeError, ValueError, RecursionError) as exc:
            raise RuntimeError("Environmental baseline capture returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Environmental baseline capture returned an invalid receipt")
    return result


def capture_location_environmental_baseline(
    operator_id: str,
    location_id: str,
    payload: object,
    *,
    connection_factory: Callable | None = None,
) -> dict:
    """Capture one measurement in the exact-location operator transaction.

    Validation is completed before database access. PostgreSQL checks the
    signed operator grant and plot lineage, inserts the baseline and replay
    receipt atomically, and returns the original receipt on an exact retry.
    """
    operator_id = _uuid(operator_id, "operator")
    location_id = _uuid(location_id, "location")
    normalized = _normalize_payload(payload)
    connection = (connection_factory or _connection_factory())()
    committed = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="environmental_baseline",
            action="create",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT kokonut_security.capture_location_environmental_baseline(
                           %s::uuid, %s::uuid, %s::uuid, %s::text, %s::numeric,
                           %s::text, %s::date, %s::text, %s::text, %s::text[], %s::text
                       )""",
                (location_id, *normalized),
            )
            result = _receipt(cursor.fetchone())

        expected = {
            "location_id": location_id,
            "plot_id": normalized[1],
            "metric_name": normalized[2],
            "baseline_value": normalized[3],
            "unit": normalized[4],
            "measurement_date": normalized[5].isoformat(),
            "measurement_method": normalized[6],
            "source": normalized[7],
            "status": "recorded",
        }
        try:
            baseline_id = _uuid(result.get("baseline_id"), "baseline")
            response_location_id = _uuid(result.get("location_id"), "location")
            response_plot_id = _uuid(result["plot_id"], "plot", optional=True)
            response_value = Decimal(str(result.get("baseline_value")))
        except (EnvironmentalBaselineCaptureInvalid, KeyError, InvalidOperation, ValueError) as exc:
            raise RuntimeError("Environmental baseline receipt does not match the request") from exc
        actual = {
            "location_id": response_location_id,
            "plot_id": response_plot_id,
            "metric_name": result.get("metric_name"),
            "baseline_value": response_value,
            "unit": result.get("unit"),
            "measurement_date": result.get("measurement_date"),
            "measurement_method": result.get("measurement_method"),
            "source": result.get("source"),
            "status": result.get("status"),
        }
        if actual != expected or not isinstance(result.get("replayed"), bool):
            raise RuntimeError("Environmental baseline receipt does not match the request")
        result["baseline_id"] = baseline_id
        result["location_id"] = response_location_id
        result["plot_id"] = response_plot_id
        result["baseline_value"] = response_value
        connection.commit()
        committed = True
        return result
    finally:
        if not committed:
            connection.rollback()
        connection.close()
