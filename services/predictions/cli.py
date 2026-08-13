"""CLI for prediction ledger and calibration operations."""

import argparse
from datetime import datetime

from services.common.cli import print_json
from services.common.database import get_db

from .service import PredictionService


def main():
    parser = argparse.ArgumentParser(description="Prediction calibration service")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("record-forecast")
    p.add_argument("--output-id", required=True)
    p = sub.add_parser("record-outcome")
    p.add_argument("--prediction-id", required=True)
    p.add_argument("--source-table", required=True)
    p.add_argument("--source-id", required=True)
    p.add_argument("--actual-at", required=True)
    p.add_argument("--actual-value", required=True, type=float)
    p.add_argument("--unit", required=True)
    p.add_argument("--verified-by")
    p = sub.add_parser("evaluate")
    p.add_argument("--prediction-id", required=True)
    p = sub.add_parser("resolve-outcome")
    p.add_argument("--prediction-id", required=True)
    p = sub.add_parser("verify-outcome")
    p.add_argument("--outcome-id", required=True)
    p.add_argument("--verified-by", required=True)
    p = sub.add_parser("calibrate")
    p.add_argument("--model", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--metric", required=True)
    p = sub.add_parser("outside-view")
    p.add_argument("--prediction-id", required=True)
    p.add_argument("--reference-class-id", required=True)
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
                                        datetime.fromisoformat(args.actual_at), args.actual_value,
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
