"""CLI for prediction ledger and calibration operations."""

import argparse
import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from services.common.cli import print_json
from services.common.database import get_db

from .service import PredictionService


def _uuid_argument(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID") from exc


def _timestamp_argument(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("must include a timezone offset")
    return parsed


def _numeric_20_8_argument(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a NUMERIC(20,8) value") from exc
    if not parsed.is_finite():
        raise argparse.ArgumentTypeError("must be finite")

    maximum = Decimal("999999999999.99999999")
    rounding_boundary = maximum + Decimal("0.000000005")
    if abs(parsed) > rounding_boundary:
        raise argparse.ArgumentTypeError("must fit NUMERIC(20,8)")
    try:
        rounded = parsed.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("must fit NUMERIC(20,8)") from exc
    if abs(rounded) > maximum:
        raise argparse.ArgumentTypeError("must fit NUMERIC(20,8)")
    return parsed


def _bounded_text_argument(label: str, max_length: int):
    def parse(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise argparse.ArgumentTypeError(f"{label} must not be blank")
        if len(normalized) > max_length:
            raise argparse.ArgumentTypeError(f"{label} must be at most {max_length} characters")
        return normalized

    return parse


def main():
    parser = argparse.ArgumentParser(description="Prediction calibration service")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("record-forecast")
    p.add_argument("--output-id", required=True, type=_uuid_argument)
    p = sub.add_parser("record-outcome")
    p.add_argument("--prediction-id", required=True, type=_uuid_argument)
    p.add_argument("--source-table", required=True, type=_bounded_text_argument("source-table", 100))
    p.add_argument("--source-id", required=True, type=_uuid_argument)
    p.add_argument("--actual-at", required=True, type=_timestamp_argument)
    p.add_argument("--actual-value", required=True, type=_numeric_20_8_argument)
    p.add_argument("--unit", required=True, type=_bounded_text_argument("unit", 50))
    p.add_argument("--verified-by", type=_uuid_argument)
    p = sub.add_parser("evaluate")
    p.add_argument("--prediction-id", required=True, type=_uuid_argument)
    p = sub.add_parser("resolve-outcome")
    p.add_argument("--prediction-id", required=True, type=_uuid_argument)
    p = sub.add_parser("verify-outcome")
    p.add_argument("--outcome-id", required=True, type=_uuid_argument)
    p.add_argument("--verified-by", required=True, type=_uuid_argument)
    p = sub.add_parser("calibrate")
    p.add_argument("--model", required=True, type=_bounded_text_argument("model", 200))
    p.add_argument("--version", required=True, type=_bounded_text_argument("version", 100))
    p.add_argument("--metric", required=True, type=_bounded_text_argument("metric", 100))
    p = sub.add_parser("outside-view")
    p.add_argument("--prediction-id", required=True, type=_uuid_argument)
    p.add_argument("--reference-class-id", required=True, type=_uuid_argument)
    p.add_argument("--selection-rationale", required=True)
    p.add_argument("--deviation-rationale")
    p.add_argument("--disconfirming-evidence")
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    service = PredictionService(get_db())
    if args.command == "record-forecast":
        result = service.record_forecast_output(args.output_id)
    elif args.command == "record-outcome":
        result = service.record_outcome(args.prediction_id, args.source_table, args.source_id,
                                        args.actual_at, args.actual_value,
                                        args.unit, args.verified_by)
    elif args.command == "evaluate":
        result = service.evaluate(args.prediction_id)
    elif args.command == "resolve-outcome":
        result = service.resolve_forecast_outcome(args.prediction_id)
    elif args.command == "verify-outcome":
        result = service.verify_outcome(args.outcome_id, args.verified_by)
    elif args.command == "calibrate":
        result = service.assess_calibration(args.model, args.version, args.metric)
    else:
        result = service.compare_outside_view(args.prediction_id, args.reference_class_id,
                                              args.selection_rationale, args.deviation_rationale,
                                              args.disconfirming_evidence)
    print_json(result)
