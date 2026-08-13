"""CLI for governed technology roadmaps."""

from __future__ import annotations

import argparse
import sys

from services.analytics.technology_roadmap import (
    add_alternative, add_area, add_driver, add_requirement,
    create_roadmap, get_roadmap_detail, list_roadmaps,
    recommend_alternatives, review_roadmap,
)
from services.common.cli import print_json


def _out(data):
    print_json(data)


def main():
    parser = argparse.ArgumentParser(description="Technology Roadmap CLI")
    sub = parser.add_subparsers(dest="command")

    create = sub.add_parser("create")
    create.add_argument("name")
    create.add_argument("--description", default="")
    create.add_argument("--entity-type", default="platform", choices=["platform", "organization", "location"])
    create.add_argument("--horizon-start")
    create.add_argument("--horizon-end")
    create.add_argument("--detail-level", default="portfolio", choices=["executive", "portfolio", "delivery"])
    create.add_argument("--sponsor")
    create.add_argument("--owner")
    create.set_defaults(func=lambda a: create_roadmap(
        a.name, description=a.description, entity_type=a.entity_type,
        planning_horizon_start=a.horizon_start, planning_horizon_end=a.horizon_end,
        detail_level=a.detail_level, sponsor=a.sponsor, owner=a.owner,
    ))

    listing = sub.add_parser("list")
    listing.add_argument("--status")
    listing.add_argument("--entity-type")
    listing.set_defaults(func=lambda a: list_roadmaps(status=a.status, entity_type=a.entity_type))

    detail = sub.add_parser("show")
    detail.add_argument("roadmap_id")
    detail.set_defaults(func=lambda a: get_roadmap_detail(a.roadmap_id))

    requirement = sub.add_parser("requirement")
    requirement.add_argument("roadmap_id")
    requirement.add_argument("title")
    requirement.add_argument("--description", default="")
    requirement.add_argument("--need-type", default="business")
    requirement.add_argument("--priority", type=int, default=3)
    requirement.add_argument("--target-value", type=float)
    requirement.add_argument("--unit")
    requirement.add_argument("--target-date")
    requirement.add_argument("--capability-id")
    requirement.set_defaults(func=lambda a: add_requirement(
        a.roadmap_id, a.title, description=a.description, need_type=a.need_type,
        priority=a.priority, target_value=a.target_value, unit=a.unit,
        target_date=a.target_date, capability_id=a.capability_id,
    ))

    area = sub.add_parser("area")
    area.add_argument("roadmap_id")
    area.add_argument("name")
    area.add_argument("--description", default="")
    area.add_argument("--order", type=int, default=1)
    area.set_defaults(func=lambda a: add_area(a.roadmap_id, a.name, description=a.description, sequence_order=a.order))

    driver = sub.add_parser("driver")
    driver.add_argument("area_id")
    driver.add_argument("name")
    driver.add_argument("--requirement-id")
    driver.add_argument("--metric-key")
    driver.add_argument("--target-value", type=float)
    driver.add_argument("--unit")
    driver.add_argument("--target-date")
    driver.add_argument("--weight", type=float, default=1.0)
    driver.set_defaults(func=lambda a: add_driver(
        a.area_id, a.name, requirement_id=a.requirement_id, metric_key=a.metric_key,
        target_value=a.target_value, unit=a.unit, target_date=a.target_date, weight=a.weight,
    ))

    alternative = sub.add_parser("alternative")
    alternative.add_argument("driver_id")
    alternative.add_argument("name")
    alternative.add_argument("--description", default="")
    alternative.add_argument("--maturity-status", default="candidate")
    alternative.add_argument("--maturity-date")
    alternative.add_argument("--estimated-cost", type=float)
    alternative.add_argument("--confidence", type=float)
    alternative.add_argument("--recommendation", default="candidate")
    alternative.add_argument("--rationale", default="")
    alternative.set_defaults(func=lambda a: add_alternative(
        a.driver_id, a.name, description=a.description, maturity_status=a.maturity_status,
        expected_maturity_date=a.maturity_date, estimated_cost=a.estimated_cost,
        confidence=a.confidence, recommendation=a.recommendation,
        decision_rationale=a.rationale,
    ))

    review = sub.add_parser("review")
    review.add_argument("roadmap_id")
    review.add_argument("result", choices=["approved", "needs_revision", "rejected", "superseded"])
    review.add_argument("--reviewed-by")
    review.add_argument("--notes", default="")
    review.set_defaults(func=lambda a: review_roadmap(a.roadmap_id, a.result, reviewed_by=a.reviewed_by, notes=a.notes))

    recommend = sub.add_parser("recommend")
    recommend.add_argument("roadmap_id")
    recommend.set_defaults(func=lambda a: recommend_alternatives(a.roadmap_id))

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    result = args.func(args)
    if result is None:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    _out(result)


if __name__ == "__main__":
    main()
