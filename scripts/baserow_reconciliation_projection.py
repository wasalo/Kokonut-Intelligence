#!/usr/bin/env python3
"""Build a deterministic, allowlisted Baserow projection for scratch rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from scripts.baserow_reconciliation_dry_run import (
    F001_ACTIVITY_KNOWN_OPTION_IDS,
    DryRunError,
    _parse_crosswalk,
    map_f001_activity_selection,
    run_dry_run,
)


DATABASE_ID = "115056"
SOURCE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://kokonut.network/baserow-reconciliation/115056")
TARGET_COLUMNS = {
    "location": ("id", "name", "slug", "description", "country", "region"),
    "farm": ("id", "location_id", "name", "slug", "description", "total_area", "area_unit"),
    "plot": ("id", "farm_id", "name", "slug", "description", "area", "area_unit"),
    "crop": ("id", "name", "scientific_name", "crop_category", "growing_season_days"),
    "farm_task": (
        "id", "location_id", "farm_id", "task_name", "category", "start_date",
        "duration_days", "end_date", "priority", "status", "description", "metadata",
        "source_system", "source_id",
    ),
    "expense_event": (
        "id", "location_id", "farm_id", "farm_task_id", "expense_date", "category",
        "description", "amount", "currency", "notes", "status", "source_system",
        "source_id", "source_raw", "payment_status", "people_impacted_count",
    ),
    "farm_activity": (
        "id", "location_id", "farm_id", "plot_id", "farm_task_id", "activity_type",
        "activity_date", "description", "notes", "duration_minutes", "activity_end_date",
        "activity_type_source_options", "status", "source_system", "source_id",
    ),
    "farm_activity_output": (
        "id", "output_name", "description", "source_system", "source_database_id",
        "source_table_id", "source_row_id",
    ),
    "farm_activity_reported_metric": (
        "id", "indicator_label", "reported_value", "reported_unit", "period_start",
        "period_end", "reported_description", "source_system", "source_database_id",
        "source_table_id", "source_row_id",
    ),
    "farm_activity_reported_metric_output": (
        "reported_metric_id", "output_id", "source_system", "source_database_id",
        "source_table_id", "source_field_id", "source_row_id",
        "source_related_table_id", "source_related_row_id",
    ),
    "farm_activity_plot": (
        "activity_id", "plot_id", "source_system", "source_database_id", "source_table_id",
        "source_field_id", "source_row_id", "source_related_table_id", "source_related_row_id",
    ),
    "farm_activity_output_activity": (
        "output_id", "activity_id", "source_system", "source_database_id", "source_table_id",
        "source_field_id", "source_row_id", "source_related_table_id", "source_related_row_id",
    ),
}
JSONB_VALUE_TYPES = {
    ("farm_task", "metadata"): dict,
    ("expense_event", "source_raw"): dict,
    ("farm_activity", "activity_type_source_options"): list,
}
ALLOWED_TRANSFORMS = {
    "required_text",
    "optional_text",
    "optional_nonnegative_numeric_12_4",
    "required_single_link",
    "optional_weeks_to_integral_days",
    "single_select_option_map",
    "required_nonnegative_numeric_15_4",
    "required_nonnegative_numeric_15_2",
    "optional_source_raw_numeric",
    "single_select_partial_option_map",
    "single_select_label_by_id",
    "activity_name_note",
    "required_date",
    "optional_date",
    "optional_nonnegative_integral",
    "optional_duration_seconds_to_minutes",
    "f001_activity_selection",
    "optional_single_link",
    "optional_single_plot_link",
    "single_select_other_with_source_label",
}
TRANSFORM_SOURCE_TYPES = {
    "required_text": {"text"},
    "optional_text": {"text", "long_text"},
    "optional_nonnegative_numeric_12_4": {"number"},
    "required_single_link": {"link_row"},
    "optional_weeks_to_integral_days": {"number"},
    "single_select_option_map": {"single_select"},
    "required_nonnegative_numeric_15_4": {"number"},
    "required_nonnegative_numeric_15_2": {"number"},
    "optional_source_raw_numeric": {"number"},
    "single_select_partial_option_map": {"single_select"},
    "single_select_label_by_id": {"single_select"},
    "activity_name_note": {"text"},
    "required_date": {"date"},
    "optional_date": {"date"},
    "optional_nonnegative_integral": {"number"},
    "optional_duration_seconds_to_minutes": {"duration"},
    "f001_activity_selection": {"multiple_select"},
    "optional_single_link": {"link_row"},
    "optional_single_plot_link": {"link_row"},
    "single_select_other_with_source_label": {"single_select"},
}
REQUIRED_TARGET_COLUMNS = {
    "location": {"id", "name", "slug"},
    "farm": {"id", "location_id", "name", "slug"},
    "plot": {"id", "farm_id", "name", "slug"},
    "crop": {"id", "name"},
    "farm_task": {
        "id", "location_id", "task_name", "category", "priority", "status", "source_system", "source_id",
    },
    "expense_event": {
        "id", "location_id", "farm_id", "expense_date", "category", "amount", "currency",
        "status", "source_system", "source_id",
    },
    "farm_activity": {
        "id", "location_id", "activity_type", "activity_date", "status", "source_system", "source_id",
    },
    "farm_activity_output": {
        "id", "output_name", "source_system", "source_database_id", "source_table_id", "source_row_id",
    },
    "farm_activity_reported_metric": {
        "id", "indicator_label", "reported_value", "source_system", "source_database_id",
        "source_table_id", "source_row_id",
    },
}
EXPECTED_IDENTITY_COLUMNS = {
    "location": ["name", "region"],
    "farm": ["name", "location_id"],
    "plot": ["name", "farm_id"],
    "crop": ["name", "scientific_name"],
    "farm_activity_output": ["source_system", "source_database_id", "source_table_id", "source_row_id"],
    "farm_activity_reported_metric": ["source_system", "source_database_id", "source_table_id", "source_row_id"],
    "farm_task": ["source_system", "source_id"],
    "expense_event": ["source_system", "source_id"],
    "farm_activity": ["source_system", "source_id"],
}
ALLOWED_CONSTANTS = {
    "location": {"country": "Dominican Republic"},
    "farm": {"area_unit": "square_meters"},
    "plot": {"area_unit": "square_meters"},
    "crop": {},
    "farm_activity_output": {
        "source_system": "baserow", "source_database_id": 115056, "source_table_id": 534165,
    },
    "farm_activity_reported_metric": {
        "source_system": "baserow", "source_database_id": 115056, "source_table_id": 534174,
    },
    "farm_task": {"source_system": "baserow", "status": "pending", "priority": "medium"},
    "expense_event": {"source_system": "baserow", "currency": "DOP", "status": "draft"},
    "farm_activity": {"source_system": "baserow", "status": "draft"},
}

# Snapshot-bound holds: ambiguous source identities are never merged or created.
ROW_QUARANTINE_SNAPSHOT_FINGERPRINT = "f14fab557e6b45fbe6fa89ec46ec1a14d9877b4766d4096fe48a92878da8968e"
ROW_QUARANTINE_OVERRIDES = {
    "317629": {
        "68": "unresolved_canonical_identity",
        "69": "unresolved_canonical_identity",
    },
}


class ProjectionError(ValueError):
    """Raised when the reviewed allowlist is structurally unsafe."""


def _validate_allowlist_document(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ProjectionError("projection allowlist must contain a JSON object")
    source = data.get("source")
    if (
        data.get("schema_version") != 1
        or not isinstance(source, dict)
        or str(source.get("database_id")) != DATABASE_ID
    ):
        raise ProjectionError("allowlist version or source database ID is unsupported")
    if not isinstance(data.get("target_tables"), list):
        raise ProjectionError("allowlist lacks a target_tables list")
    if not isinstance(data.get("relationship_tables", []), list):
        raise ProjectionError("allowlist relationship_tables must be a list")
    if not isinstance(data.get("relationship_checks", []), list):
        raise ProjectionError("allowlist relationship_checks must be a list")
    return data


def load_allowlist(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectionError("could not read or parse the projection allowlist") from exc
    return _validate_allowlist_document(data)


def validate_allowlist(
    export: dict[str, Any], allowlist: dict[str, Any], crosswalk_text: str
) -> None:
    """Require every projection field to match its reviewed crosswalk disposition and target."""
    crosswalk, _ = _parse_crosswalk(crosswalk_text)
    source_tables = {str(table.get("id")): table for table in export.get("tables", [])}
    seen_source_tables: set[str] = set()
    seen_targets: set[str] = set()
    target_by_source = {
        str(spec.get("source_table_id")): spec.get("target_table")
        for spec in allowlist["target_tables"]
    }

    for spec in allowlist["target_tables"]:
        table_id = str(spec.get("source_table_id"))
        target_table = spec.get("target_table")
        if table_id in seen_source_tables or target_table in seen_targets:
            raise ProjectionError("allowlist contains a duplicate source or target table")
        seen_source_tables.add(table_id)
        seen_targets.add(target_table)
        target_by_source[table_id] = target_table
        if table_id not in source_tables or table_id not in crosswalk:
            raise ProjectionError(f"allowlisted source table {table_id} is missing")
        if target_table not in TARGET_COLUMNS:
            raise ProjectionError(f"target table {target_table} is not approved for this rehearsal")
        source_fields = {str(field.get("id")): field for field in source_tables[table_id].get("fields", [])}
        target_columns = set(TARGET_COLUMNS[target_table])
        fields = spec.get("fields")
        if not isinstance(fields, dict):
            raise ProjectionError(f"allowlist fields are invalid for source table {table_id}")
        if spec.get("identity_columns") != EXPECTED_IDENTITY_COLUMNS[target_table]:
            raise ProjectionError(f"identity columns do not match the reviewed policy for {target_table}")
        constants = spec.get("constants", {})
        if constants != ALLOWED_CONSTANTS[target_table]:
            raise ProjectionError(f"constant values do not match the reviewed policy for {target_table}")
        expected_generated = {"id": "uuid5_source_identity"}
        if target_table in {"location", "farm", "plot"}:
            expected_generated["slug"] = "slugify_name_plus_source_identity"
        if target_table in {"farm_activity_output", "farm_activity_reported_metric"}:
            expected_generated["source_row_id"] = "copy_source_row_id"
        if target_table in {"farm_task", "farm_activity", "expense_event"}:
            expected_generated["source_id"] = "baserow_composite_identity"
        generated = spec.get("generated_columns", {})
        if generated != expected_generated:
            raise ProjectionError(f"generated columns do not match the reviewed policy for {target_table}")
        expected_derived = (
            {"location_id": "resolved_farm_location_id"}
            if target_table in {"farm_task", "farm_activity", "expense_event"}
            else {}
        )
        if spec.get("derived_columns", {}) != expected_derived:
            raise ProjectionError(f"derived columns do not match the reviewed policy for {target_table}")

        mapped_columns: list[str] = []
        for field_id, rule in fields.items():
            field_id = str(field_id)
            source_field = source_fields.get(field_id)
            mapping = crosswalk[table_id].get(field_id)
            if source_field is None or mapping is None:
                raise ProjectionError(f"allowlisted source field {table_id}.{field_id} is missing")
            if mapping["disposition"] != rule.get("source_disposition"):
                raise ProjectionError(f"allowlist disposition differs from crosswalk for {table_id}.{field_id}")
            transform = rule.get("transform")
            category_option_map = rule.get("option_map")
            exact_labor_map = (
                isinstance(category_option_map, dict)
                and bool(category_option_map)
                and all(
                    isinstance(option_id, str)
                    and option_id.isdigit()
                    and int(option_id) > 0
                    and target_value == "labor"
                    for option_id, target_value in category_option_map.items()
                )
                and rule.get("source_label") == "Labor"
            )
            partial_category_allowed = (
                table_id == "317575"
                and field_id == "2330114"
                and mapping["disposition"] == "CONDITIONAL"
                and transform == "single_select_partial_option_map"
                and exact_labor_map
                and rule.get("owner_decision_ref") == "exact-Labor-to-labor-2026-10-08"
            )
            source_raw_target_match = re.fullmatch(
                r"`([^`]+)`(?: \(source-record provenance only\))?",
                mapping["target"],
            )
            source_raw_rate_allowed = (
                table_id == "317575"
                and field_id == "3932281"
                and mapping["disposition"] == "PROVENANCE_ONLY"
                and transform == "optional_source_raw_numeric"
                and rule.get("target_column") == "source_raw"
                and rule.get("metadata_path") == "baserow_legacy.usd_dop_rate"
                and source_raw_target_match is not None
                and source_raw_target_match.group(1) == "expense_event.source_raw.baserow_legacy.usd_dop_rate"
            )
            if mapping["disposition"] not in {"CANDIDATE", "RELATIONSHIP"} and not (
                partial_category_allowed or source_raw_rate_allowed
            ):
                raise ProjectionError(
                    f"blocking source disposition is not projectable for {table_id}.{field_id}"
                )
            if transform == "single_select_partial_option_map" and not partial_category_allowed:
                raise ProjectionError(f"partial select mapping differs from owner approval for {table_id}.{field_id}")
            if transform == "optional_source_raw_numeric" and not source_raw_rate_allowed:
                raise ProjectionError(f"source provenance mapping differs from owner approval for {table_id}.{field_id}")
            source_type = str(source_field.get("type"))
            if transform not in ALLOWED_TRANSFORMS:
                raise ProjectionError(f"allowlist transform is unsupported for {table_id}.{field_id}")
            if source_type != mapping["source_type"]:
                raise ProjectionError(f"source field type differs from crosswalk for {table_id}.{field_id}")
            if source_type not in TRANSFORM_SOURCE_TYPES[transform]:
                raise ProjectionError(f"allowlist transform is incompatible with source type for {table_id}.{field_id}")
            if transform == "single_select_option_map":
                options = source_field.get("select_options", source_field.get("options"))
                if not isinstance(options, list):
                    raise ProjectionError(f"source select options are unavailable for {table_id}.{field_id}")
                option_ids: list[str] = []
                for option in options:
                    option_id = option.get("id") if isinstance(option, dict) else None
                    if isinstance(option_id, bool) or not isinstance(option_id, (int, str)) or not str(option_id).isdigit():
                        raise ProjectionError(f"source select option metadata is invalid for {table_id}.{field_id}")
                    option_ids.append(str(option_id))
                if len(option_ids) != len(set(option_ids)):
                    raise ProjectionError(f"source select option IDs are duplicated for {table_id}.{field_id}")
                option_map = rule.get("option_map")
                if not isinstance(option_map, dict) or set(option_map) != set(option_ids):
                    raise ProjectionError(f"option map must cover every source option for {table_id}.{field_id}")
                if any(not isinstance(value, str) or not value.strip() for value in option_map.values()):
                    raise ProjectionError(f"option map contains an invalid target value for {table_id}.{field_id}")
            elif transform == "single_select_partial_option_map":
                options = source_field.get("select_options", source_field.get("options"))
                option_map = rule.get("option_map")
                source_label = rule.get("source_label")
                if (
                    not isinstance(options, list)
                    or not isinstance(option_map, dict)
                    or not option_map
                    or any(value != "labor" for value in option_map.values())
                    or source_label != "Labor"
                ):
                    raise ProjectionError(f"partial category option inventory is invalid for {table_id}.{field_id}")
                option_ids: list[str] = []
                labels_by_id: dict[str, str] = {}
                for option in options:
                    option_id = option.get("id") if isinstance(option, dict) else None
                    label = option.get("value") if isinstance(option, dict) else None
                    if (
                        isinstance(option_id, bool)
                        or not isinstance(option_id, (int, str))
                        or not str(option_id).isdigit()
                        or int(option_id) <= 0
                        or not isinstance(label, str)
                        or not label.strip()
                        or "\x00" in label
                    ):
                        raise ProjectionError(f"source category option metadata is invalid for {table_id}.{field_id}")
                    option_ids.append(str(option_id))
                    labels_by_id[str(option_id)] = label
                if (
                    len(option_ids) != len(set(option_ids))
                    or set(option_map) != {option_id for option_id, label in labels_by_id.items() if label == source_label}
                ):
                    raise ProjectionError(f"approved labor option differs from source metadata for {table_id}.{field_id}")
            elif transform == "single_select_label_by_id":
                options = source_field.get("select_options", source_field.get("options"))
                approved_ids = rule.get("approved_option_ids")
                if (
                    table_id != "317575"
                    or field_id != "4244464"
                    or mapping["disposition"] != "CANDIDATE"
                    or "expense_event.payment_status" not in mapping["target"]
                    or not isinstance(options, list)
                    or not isinstance(approved_ids, list)
                    or not approved_ids
                    or any(not isinstance(value, str) or not value.isdigit() or int(value) <= 0 for value in approved_ids)
                    or len(approved_ids) != len(set(approved_ids))
                ):
                    raise ProjectionError(f"payment-status option policy is invalid for {table_id}.{field_id}")
                labels_by_id: dict[str, str] = {}
                for option in options:
                    option_id = option.get("id") if isinstance(option, dict) else None
                    label = option.get("value") if isinstance(option, dict) else None
                    if (
                        isinstance(option_id, bool)
                        or not isinstance(option_id, (int, str))
                        or not str(option_id).isdigit()
                        or int(option_id) <= 0
                        or not isinstance(label, str)
                        or not label.strip()
                        or "\x00" in label
                        or len(label) > 50
                        or str(option_id) in labels_by_id
                    ):
                        raise ProjectionError(f"payment-status option metadata is invalid for {table_id}.{field_id}")
                    labels_by_id[str(option_id)] = label
                if not set(approved_ids).issubset(labels_by_id):
                    raise ProjectionError(f"approved payment-status option is missing for {table_id}.{field_id}")
            elif transform == "f001_activity_selection":
                options = source_field.get("select_options")
                option_ids: list[str] = []
                labels: list[str] = []
                if not isinstance(options, list) or table_id != "322673" or field_id != "2350134":
                    raise ProjectionError(f"F001 activity option metadata is unavailable for {table_id}.{field_id}")
                for option in options:
                    option_id = option.get("id") if isinstance(option, dict) else None
                    label = option.get("value") if isinstance(option, dict) else None
                    if (
                        isinstance(option_id, bool)
                        or not isinstance(option_id, (int, str))
                        or not str(option_id).isdigit()
                        or int(option_id) <= 0
                        or not isinstance(label, str)
                        or not label.strip()
                        or "\x00" in label
                        or len(label) > 100
                    ):
                        raise ProjectionError(f"F001 activity option metadata is malformed for {table_id}.{field_id}")
                    option_ids.append(str(option_id))
                    labels.append(label)
                if (
                    len(option_ids) != len(set(option_ids))
                    or set(option_ids) != set(F001_ACTIVITY_KNOWN_OPTION_IDS)
                    or len(labels) != len(set(labels))
                    or "option_map" in rule
                    or "farm_activity.activity_type_source_options" not in mapping["target"]
                ):
                    raise ProjectionError(f"F001 activity option inventory differs from the reviewed policy for {table_id}.{field_id}")
            elif transform == "single_select_other_with_source_label":
                options = source_field.get("select_options", source_field.get("options"))
                approved_labels = rule.get("approved_labels")
                option_ids: list[str] = []
                labels: list[str] = []
                if not isinstance(options, list) or not isinstance(approved_labels, list):
                    raise ProjectionError(f"task category option metadata is unavailable for {table_id}.{field_id}")
                for option in options:
                    option_id = option.get("id") if isinstance(option, dict) else None
                    label = option.get("value") if isinstance(option, dict) else None
                    if (
                        isinstance(option_id, bool)
                        or not isinstance(option_id, (int, str))
                        or not str(option_id).isdigit()
                        or int(option_id) <= 0
                        or not isinstance(label, str)
                        or not label.strip()
                        or "\x00" in label
                    ):
                        raise ProjectionError(f"task category option metadata is malformed for {table_id}.{field_id}")
                    option_ids.append(str(option_id))
                    labels.append(label)
                if (
                    table_id != "305801"
                    or field_id != "2202712"
                    or len(option_ids) != len(set(option_ids))
                    or len(labels) != len(set(labels))
                    or set(labels) != set(approved_labels)
                    or any(not isinstance(label, str) for label in approved_labels)
                    or rule.get("target_value") != "other"
                    or rule.get("metadata_path") != "baserow_legacy.category_label"
                    or "farm_task.metadata.baserow_legacy.category_label" not in mapping["target"]
                ):
                    raise ProjectionError(f"task category mapping differs from the reviewed policy for {table_id}.{field_id}")
            elif "option_map" in rule:
                raise ProjectionError(f"option map is only valid for single-select fields {table_id}.{field_id}")
            column = rule.get("target_column")
            if column not in target_columns or f"{target_table}.{column}" not in mapping["target"]:
                raise ProjectionError(f"allowlist target differs from crosswalk for {table_id}.{field_id}")
            mapped_columns.append(column)
            if transform in {"required_single_link", "optional_single_link", "optional_single_plot_link"}:
                if str(source_field.get("link_row_table_id")) != str(rule.get("linked_table_id")):
                    raise ProjectionError(f"allowlist link target differs from source schema for {table_id}.{field_id}")
            if transform == "f001_activity_selection" and "farm_activity.activity_type" not in mapping["target"]:
                raise ProjectionError(f"allowlist target differs from crosswalk for {table_id}.{field_id}")
        if len(mapped_columns) != len(set(mapped_columns)):
            raise ProjectionError(f"allowlist maps multiple source fields to one target column for {target_table}")
        required_source_fields = set(spec.get("required_source_fields", []))
        if not required_source_fields.issubset(set(fields)):
            raise ProjectionError(f"required source fields are not allowlisted for table {table_id}")
        available_columns = set(mapped_columns) | set(constants) | set(generated) | set(expected_derived)
        if not REQUIRED_TARGET_COLUMNS[target_table].issubset(available_columns):
            raise ProjectionError(f"allowlist does not provide required target columns for {target_table}")

        row_filter = spec.get("row_filter")
        if row_filter is not None:
            if row_filter.get("kind") == "linked_from":
                filter_links = [row_filter]
            elif row_filter.get("kind") == "linked_from_any":
                filter_links = row_filter.get("links")
            else:
                filter_links = None
            if not isinstance(filter_links, list) or not filter_links:
                raise ProjectionError(f"row filter is unsupported for {target_table}")
            for link in filter_links:
                filter_source_id = str(link.get("source_table_id"))
                filter_field_id = str(link.get("source_field_id"))
                filter_table = source_tables.get(filter_source_id)
                filter_field = next(
                    (field for field in (filter_table or {}).get("fields", []) if str(field.get("id")) == filter_field_id),
                    None,
                )
                filter_mapping = crosswalk.get(filter_source_id, {}).get(filter_field_id)
                relation_target = link.get("relationship_target")
                approved_relation = any(
                    str(relation.get("source_table_id")) == filter_source_id
                    and str(relation.get("source_field_id")) == filter_field_id
                    and str(relation.get("linked_table_id")) == table_id
                    and (relation_target is None or relation.get("target_table") == relation_target)
                    for relation in allowlist.get("relationship_tables", [])
                )
                support_source_target = target_by_source.get(filter_source_id)
                direct_task_support = (
                    target_table == "farm_task"
                    and support_source_target in {"farm_activity", "expense_event"}
                    and f"{support_source_target}.farm_task_id" in filter_mapping.get("target", "")
                ) if filter_mapping else False
                direct_relationship_check = any(
                    str(check.get("source_table_id")) == filter_source_id
                    and str(check.get("source_field_id")) == filter_field_id
                    for check in allowlist.get("relationship_checks", [])
                )
                if (
                    filter_table is None
                    or filter_field is None
                    or filter_mapping is None
                    or str(filter_field.get("type")) != "link_row"
                    or str(filter_field.get("link_row_table_id")) != table_id
                    or str(link.get("linked_table_id")) != table_id
                    or filter_mapping["disposition"] != "RELATIONSHIP"
                    or not (
                        approved_relation
                        or (relation_target is None and direct_task_support and direct_relationship_check)
                    )
                ):
                    raise ProjectionError(f"row filter must resolve to an approved source relationship for {table_id}")

    for relation in allowlist.get("relationship_tables", []):
        source_table_id = str(relation.get("source_table_id"))
        source_field_id = str(relation.get("source_field_id"))
        linked_table_id = str(relation.get("linked_table_id"))
        reciprocal_table_id = str(relation.get("reciprocal_table_id"))
        reciprocal_field_id = str(relation.get("reciprocal_field_id"))
        target_table = relation.get("target_table")
        source_field = next(
            (field for field in source_tables.get(source_table_id, {}).get("fields", []) if str(field.get("id")) == source_field_id),
            None,
        )
        reciprocal_field = next(
            (field for field in source_tables.get(reciprocal_table_id, {}).get("fields", []) if str(field.get("id")) == reciprocal_field_id),
            None,
        )
        source_mapping = crosswalk.get(source_table_id, {}).get(source_field_id)
        reciprocal_mapping = crosswalk.get(reciprocal_table_id, {}).get(reciprocal_field_id)
        if (
            source_field is None
            or reciprocal_field is None
            or source_mapping is None
            or reciprocal_mapping is None
            or source_mapping["disposition"] != relation.get("source_disposition")
            or source_mapping["disposition"] != "RELATIONSHIP"
            or reciprocal_mapping["disposition"] != "RELATIONSHIP"
            or str(source_field.get("type")) != "link_row"
            or str(reciprocal_field.get("type")) != "link_row"
            or str(source_field.get("link_row_table_id")) != linked_table_id
            or str(reciprocal_field.get("link_row_table_id")) != source_table_id
            or reciprocal_table_id != linked_table_id
            or target_table not in TARGET_COLUMNS
            or target_by_source.get(source_table_id) != relation.get("source_entity_target")
            or target_by_source.get(linked_table_id) != relation.get("related_entity_target")
            or str(target_table) in seen_targets
            or str(target_table) not in source_mapping["target"]
            or str(target_table) not in reciprocal_mapping["target"]
            or relation.get("source_target_column") not in TARGET_COLUMNS.get(str(target_table), ())
            or relation.get("related_target_column") not in TARGET_COLUMNS.get(str(target_table), ())
        ):
            raise ProjectionError("relationship allowlist must match typed reciprocal source and target mappings")

    checked_direct_links: set[tuple[str, str]] = set()
    target_specs_by_source = {
        str(spec.get("source_table_id")): spec for spec in allowlist["target_tables"]
    }
    for check in allowlist.get("relationship_checks", []):
        source_table_id = str(check.get("source_table_id"))
        source_field_id = str(check.get("source_field_id"))
        linked_table_id = str(check.get("linked_table_id"))
        reciprocal_table_id = str(check.get("reciprocal_table_id"))
        reciprocal_field_id = str(check.get("reciprocal_field_id"))
        source_entity_target = str(check.get("source_entity_target"))
        source_target_column = str(check.get("source_target_column"))
        related_entity_target = str(check.get("related_entity_target"))
        source_field = next(
            (field for field in source_tables.get(source_table_id, {}).get("fields", []) if str(field.get("id")) == source_field_id),
            None,
        )
        reciprocal_field = next(
            (field for field in source_tables.get(reciprocal_table_id, {}).get("fields", []) if str(field.get("id")) == reciprocal_field_id),
            None,
        )
        source_spec = target_specs_by_source.get(source_table_id, {})
        source_rule = source_spec.get("fields", {}).get(source_field_id)
        source_mapping = crosswalk.get(source_table_id, {}).get(source_field_id)
        reciprocal_mapping = crosswalk.get(reciprocal_table_id, {}).get(reciprocal_field_id)
        link_key = (source_table_id, source_field_id)
        target_path = f"{source_entity_target}.{source_target_column}"
        if (
            link_key in checked_direct_links
            or source_field is None
            or reciprocal_field is None
            or source_rule is None
            or source_mapping is None
            or reciprocal_mapping is None
            or source_mapping["disposition"] != "RELATIONSHIP"
            or reciprocal_mapping["disposition"] != "RELATIONSHIP"
            or source_rule.get("source_disposition") != "RELATIONSHIP"
            or source_rule.get("target_column") != source_target_column
            or source_rule.get("transform") not in {"required_single_link", "optional_single_link"}
            or str(source_rule.get("linked_table_id")) != linked_table_id
            or str(source_field.get("type")) != "link_row"
            or str(reciprocal_field.get("type")) != "link_row"
            or str(source_field.get("link_row_table_id")) != linked_table_id
            or str(reciprocal_field.get("link_row_table_id")) != source_table_id
            or reciprocal_table_id != linked_table_id
            or target_by_source.get(source_table_id) != source_entity_target
            or target_by_source.get(linked_table_id) != related_entity_target
            or source_target_column not in TARGET_COLUMNS.get(source_entity_target, ())
            or target_path not in source_mapping["target"]
            or target_path not in reciprocal_mapping["target"]
        ):
            raise ProjectionError("direct relationship check must match typed reciprocal source and target mappings")
        checked_direct_links.add(link_key)


def _populated(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _link_ids(value: Any) -> tuple[list[str], int]:
    if not _populated(value):
        return [], 0
    values = value if isinstance(value, list) else [value]
    ids: list[str] = []
    malformed = 0
    for item in values:
        if isinstance(item, dict):
            item = item.get("id", item.get("row_id"))
        if isinstance(item, bool) or not isinstance(item, (int, str)) or not str(item).isdigit():
            malformed += 1
        else:
            ids.append(str(item))
    return ids, malformed


def _relationship_edge_profile(
    source_tables: dict[str, dict[str, Any]],
    source_table_id: str,
    source_field_id: str,
    linked_table_id: str,
    reciprocal_table_id: str,
    reciprocal_field_id: str,
) -> dict[str, Any]:
    source_rows = source_tables[source_table_id].get("rows", [])
    linked_rows = source_tables[linked_table_id].get("rows", [])
    reciprocal_rows = source_tables[reciprocal_table_id].get("rows", [])
    source_row_ids = {
        str(row.get("id")) for row in source_rows
        if row.get("id") is not None and str(row.get("id")).isdigit()
    }
    linked_row_ids = {
        str(row.get("id")) for row in linked_rows
        if row.get("id") is not None and str(row.get("id")).isdigit()
    }
    forward_edges: Counter[tuple[str, str]] = Counter()
    reciprocal_edges: Counter[tuple[str, str]] = Counter()
    reasons: Counter[str] = Counter()
    invalid_source_rows: set[str] = set()

    for row in source_rows:
        source_row_id = str(row.get("id")) if row.get("id") is not None else ""
        if not source_row_id.isdigit():
            reasons["invalid_source_row_id"] += 1
            continue
        ids, malformed = _link_ids(row.get(f"field_{source_field_id}"))
        if malformed:
            reasons["malformed_source_link"] += malformed
            invalid_source_rows.add(source_row_id)
        for linked_row_id in ids:
            forward_edges[(source_row_id, linked_row_id)] += 1

    for row in reciprocal_rows:
        linked_row_id = str(row.get("id")) if row.get("id") is not None else ""
        if not linked_row_id.isdigit():
            reasons["invalid_reciprocal_row_id"] += 1
            continue
        ids, malformed = _link_ids(row.get(f"field_{reciprocal_field_id}"))
        if malformed:
            reasons["malformed_reciprocal_link"] += malformed
        for source_row_id in ids:
            reciprocal_edges[(source_row_id, linked_row_id)] += 1

    valid_edges: set[tuple[str, str]] = set()
    for edge in set(forward_edges) | set(reciprocal_edges):
        source_row_id, linked_row_id = edge
        forward_count = forward_edges.get(edge, 0)
        reciprocal_count = reciprocal_edges.get(edge, 0)
        if source_row_id not in source_row_ids or linked_row_id not in linked_row_ids:
            reasons["dangling_relationship_edge"] += max(1, forward_count, reciprocal_count)
            if source_row_id in source_row_ids:
                invalid_source_rows.add(source_row_id)
            continue
        if forward_count != 1 or reciprocal_count != 1:
            reasons["nonreciprocal_edge"] += max(1, abs(forward_count - reciprocal_count))
            invalid_source_rows.add(source_row_id)
            continue
        valid_edges.add(edge)

    valid_edges = {edge for edge in valid_edges if edge[0] not in invalid_source_rows}
    return {
        "valid_edges": valid_edges,
        "invalid_source_rows": invalid_source_rows,
        "source_edges": sum(forward_edges.values()),
        "reciprocal_edges": sum(reciprocal_edges.values()),
        "reasons": reasons,
    }


def _single_select_option_id(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("id", value.get("option_id"))
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).isdigit():
        return None
    return str(value)


def _text(value: Any, *, required: bool, max_length: int | None = None) -> tuple[str | None, str | None]:
    if not _populated(value):
        return (None, "missing_required_value") if required else (None, None)
    if not isinstance(value, str) or "\x00" in value:
        return None, "invalid_text"
    normalized = value.strip()
    if not normalized:
        return (None, "missing_required_value") if required else (None, None)
    if max_length is not None and len(normalized) > max_length:
        return None, "text_too_long"
    return normalized, None


def _decimal(value: Any, *, scale: int, precision: int) -> tuple[Decimal | None, str | None]:
    if not _populated(value):
        return None, None
    if isinstance(value, bool):
        return None, "invalid_numeric"
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None, "invalid_numeric"
    if not number.is_finite() or number < 0:
        return None, "invalid_numeric"
    normalized = number.normalize()
    actual_scale = max(0, -normalized.as_tuple().exponent)
    integer_digits = max(0, normalized.adjusted() + 1) if number != 0 else 1
    if actual_scale > scale or integer_digits + actual_scale > precision:
        return None, "numeric_precision_or_scale"
    return number, None


def _iso_date(value: Any, *, required: bool) -> tuple[str | None, str | None]:
    if not _populated(value):
        return (None, "missing_required_value") if required else (None, None)
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None, "invalid_date"
    try:
        return date.fromisoformat(value).isoformat(), None
    except ValueError:
        return None, "invalid_date"


def _nonnegative_integral(value: Any) -> tuple[int | None, str | None]:
    number, error = _decimal(value, scale=0, precision=10)
    if error or number is None:
        return None, error
    if number != number.to_integral_value() or number > 2_147_483_647:
        return None, "not_nonnegative_integral"
    return int(number), None


def _duration_seconds_to_minutes(value: Any) -> tuple[int | None, str | None]:
    seconds, error = _decimal(value, scale=0, precision=15)
    if error or seconds is None:
        return None, error
    if seconds % 60 != 0:
        return None, "duration_not_whole_minutes"
    minutes = seconds / 60
    if minutes > 2_147_483_647:
        return None, "duration_out_of_range"
    return int(minutes), None


def _weeks_to_days(value: Any) -> tuple[int | None, str | None]:
    if not _populated(value):
        return None, None
    if isinstance(value, bool):
        return None, "invalid_weeks_to_maturity"
    try:
        weeks = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None, "invalid_weeks_to_maturity"
    if not weeks.is_finite() or weeks <= 0:
        return None, "invalid_weeks_to_maturity"
    days = weeks * 7
    if days != days.to_integral_value() or days > 2_147_483_647:
        return None, "weeks_do_not_convert_to_integer_days"
    return int(days), None


def _slug(name: str, source_table_id: str, source_row_id: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", folded).strip("-") or "source"
    suffix = f"-baserow-{DATABASE_ID}-{source_table_id}-{source_row_id}"
    return f"{base[:255 - len(suffix)].rstrip('-')}{suffix}"


def _target_uuid(source_table_id: str, source_row_id: str, target_table: str) -> str:
    identity = f"baserow:{DATABASE_ID}:{source_table_id}:{source_row_id}:{target_table}"
    return str(uuid.uuid5(SOURCE_NAMESPACE, identity))


def _identity_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, str):
        return unicodedata.normalize("NFKC", value).strip().casefold()
    return str(value).strip().casefold()


def build_projection(export: dict[str, Any], allowlist: dict[str, Any]) -> dict[str, Any]:
    """Build target-shaped rows and aggregate-only quarantine results in memory."""
    if str(export.get("id")) != DATABASE_ID:
        raise ProjectionError(f"source export database ID does not match {DATABASE_ID}")
    source_tables = {str(table.get("id")): table for table in export.get("tables", [])}
    if len(source_tables) != len(export.get("tables", [])):
        raise ProjectionError("source export contains duplicate table IDs")
    configured_row_overrides = ROW_QUARANTINE_OVERRIDES
    if not isinstance(configured_row_overrides, dict):
        raise ProjectionError("snapshot row-quarantine overrides are invalid")
    for table_id, row_overrides in configured_row_overrides.items():
        if (
            not isinstance(table_id, str)
            or not isinstance(row_overrides, dict)
            or not row_overrides
            or any(
                not isinstance(row_id, str)
                or not row_id.isdigit()
                or reason != "unresolved_canonical_identity"
                for row_id, reason in row_overrides.items()
            )
        ):
            raise ProjectionError("snapshot row-quarantine overrides are invalid")
    snapshot_fingerprint = hashlib.sha256(
        json.dumps(export, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if snapshot_fingerprint == ROW_QUARANTINE_SNAPSHOT_FINGERPRINT:
        allowed_source_tables = {str(spec["source_table_id"]) for spec in allowlist["target_tables"]}
        if not set(configured_row_overrides).issubset(allowed_source_tables):
            raise ProjectionError("snapshot row-quarantine overrides target a non-allowlisted source table")
        active_row_overrides = configured_row_overrides
    elif configured_row_overrides:
        raise ProjectionError("source export does not match the snapshot row-quarantine overrides")
    else:
        active_row_overrides = {}
    for table in source_tables.values():
        row_ids = [
            str(row.get("id")) for row in table.get("rows", [])
            if row.get("id") is not None
        ]
        if len(row_ids) != len(set(row_ids)):
            raise ProjectionError("source export contains duplicate source row IDs")

    input_counts = {table_id: len(table.get("rows", [])) for table_id, table in source_tables.items()}
    rows_by_target: dict[str, list[dict[str, Any]]] = {spec["target_table"]: [] for spec in allowlist["target_tables"]}
    for relation in allowlist.get("relationship_tables", []):
        rows_by_target.setdefault(relation["target_table"], [])
    projected_source_ids: dict[str, dict[str, str]] = defaultdict(dict)
    projected_records_by_source: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    projected_records_by_target_id: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    edge_profiles: dict[tuple[str, str], dict[str, Any]] = {}
    for relation in allowlist.get("relationship_tables", []):
        key = (str(relation["source_table_id"]), str(relation["source_field_id"]))
        edge_profiles[key] = _relationship_edge_profile(
            source_tables,
            key[0],
            key[1],
            str(relation["linked_table_id"]),
            str(relation["reciprocal_table_id"]),
            str(relation["reciprocal_field_id"]),
        )
    for check in allowlist.get("relationship_checks", []):
        key = (str(check["source_table_id"]), str(check["source_field_id"]))
        edge_profiles[key] = _relationship_edge_profile(
            source_tables,
            key[0],
            key[1],
            str(check["linked_table_id"]),
            str(check["reciprocal_table_id"]),
            str(check["reciprocal_field_id"]),
        )
    row_reasons: dict[str, Counter[str]] = defaultdict(Counter)
    field_reasons: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    projected_by_source: Counter[str] = Counter()
    filtered_by_source: Counter[str] = Counter()

    def projected_location_id(parent_target_table: str, parent_record: dict[str, Any]) -> Any:
        location_id = parent_record.get("location_id")
        if location_id is not None:
            return location_id
        if parent_target_table == "plot":
            farm_id = parent_record.get("farm_id")
            if not isinstance(farm_id, str):
                return None
            farm_record = projected_records_by_target_id["farm"].get(farm_id)
            return farm_record.get("location_id") if farm_record else None
        return None

    def link_row_has_reciprocity_failure(source_table_id: str, source_field_id: str, source_row_id: str) -> bool:
        profile = edge_profiles.get((source_table_id, source_field_id))
        return bool(profile and source_row_id in profile["invalid_source_rows"])

    for spec in allowlist["target_tables"]:
        source_table_id = str(spec["source_table_id"])
        target_table = spec["target_table"]
        source_rows = source_tables[source_table_id].get("rows", [])
        source_fields = {
            str(field.get("id")): field for field in source_tables[source_table_id].get("fields", [])
        }
        included_source_ids: set[str] | None = None
        row_filter = spec.get("row_filter")
        if row_filter:
            if row_filter.get("kind") == "linked_from":
                filter_links = [row_filter]
            elif row_filter.get("kind") == "linked_from_any":
                filter_links = row_filter.get("links", [])
            else:
                raise ProjectionError(f"row filter is unsupported for {target_table}")
            included_source_ids = set()
            for filter_link in filter_links:
                filter_source_id = str(filter_link["source_table_id"])
                filter_field_id = str(filter_link["source_field_id"])
                profile = edge_profiles.get((filter_source_id, filter_field_id))
                if profile is not None:
                    included_source_ids.update(linked_id for _, linked_id in profile["valid_edges"])
                    continue
                ref_table = source_tables[filter_source_id]
                for ref_row in ref_table.get("rows", []):
                    linked_ids, _ = _link_ids(ref_row.get(f"field_{filter_field_id}"))
                    included_source_ids.update(linked_ids)
        seen_ids: set[str] = set()
        provisional: list[tuple[str, dict[str, Any]]] = []

        for row in source_rows:
            source_row_id = str(row.get("id")) if row.get("id") is not None else ""
            if not source_row_id or source_row_id in seen_ids:
                row_reasons[source_table_id]["missing_or_duplicate_source_row_id"] += 1
                continue
            seen_ids.add(source_row_id)
            quarantine_reason = active_row_overrides.get(source_table_id, {}).get(source_row_id)
            if quarantine_reason:
                row_reasons[source_table_id][quarantine_reason] += 1
                continue
            if included_source_ids is not None and source_row_id not in included_source_ids:
                filtered_by_source[source_table_id] += 1
                continue
            if spec.get("generated_columns", {}).get("source_row_id") == "copy_source_row_id" and not source_row_id.isdigit():
                row_reasons[source_table_id]["invalid_source_row_id"] += 1
                continue
            record: dict[str, Any] = {column: None for column in TARGET_COLUMNS[target_table]}
            if target_table == "farm_task":
                record["metadata"] = {}
            elif target_table == "expense_event":
                record["source_raw"] = {}
            row_error: str | None = None

            for field_id, rule in spec["fields"].items():
                field_id = str(field_id)
                source_value = row.get(f"field_{field_id}")
                transform = rule["transform"]
                target_column = rule["target_column"]
                if transform == "required_text":
                    value, error = _text(source_value, required=True, max_length=255)
                    if error:
                        row_error = error
                        break
                    record[target_column] = value
                elif transform == "activity_name_note":
                    value, error = _text(source_value, required=False)
                    if error:
                        field_reasons[(source_table_id, field_id)][error] += 1
                    elif value is not None:
                        record[target_column] = f"Activity Name: {value}"
                elif transform == "optional_text":
                    value, error = _text(source_value, required=False, max_length=255 if target_column == "scientific_name" else None)
                    if error:
                        field_reasons[(source_table_id, field_id)][error] += 1
                    else:
                        record[target_column] = value
                elif transform in {"required_date", "optional_date"}:
                    value, error = _iso_date(source_value, required=transform == "required_date")
                    if error and transform == "required_date":
                        row_error = error
                        break
                    if error:
                        field_reasons[(source_table_id, field_id)][error] += 1
                    else:
                        record[target_column] = value
                elif transform == "optional_nonnegative_integral":
                    value, error = _nonnegative_integral(source_value)
                    if error:
                        if target_table == "expense_event":
                            row_error = error
                            break
                        field_reasons[(source_table_id, field_id)][error] += 1
                    else:
                        record[target_column] = value
                elif transform == "optional_duration_seconds_to_minutes":
                    value, error = _duration_seconds_to_minutes(source_value)
                    if error:
                        field_reasons[(source_table_id, field_id)][error] += 1
                    else:
                        record[target_column] = value
                elif transform == "optional_nonnegative_numeric_12_4":
                    value, error = _decimal(source_value, scale=4, precision=12)
                    if error:
                        field_reasons[(source_table_id, field_id)][error] += 1
                    else:
                        record[target_column] = value
                elif transform == "required_single_link":
                    if link_row_has_reciprocity_failure(source_table_id, field_id, source_row_id):
                        row_error = "nonreciprocal_relationship"
                        break
                    ids, malformed = _link_ids(source_value)
                    if malformed:
                        row_error = "malformed_link"
                        break
                    if len(ids) != 1:
                        row_error = "missing_or_ambiguous_link"
                        break
                    target_source_table = str(rule["linked_table_id"])
                    resolved = projected_source_ids[target_source_table].get(ids[0])
                    if resolved is None:
                        row_error = "unresolved_parent_link"
                        break
                    record[target_column] = resolved
                    parent_record = projected_records_by_source[target_source_table].get(ids[0])
                    if target_table in {"farm_task", "farm_activity", "expense_event"} and target_column == "farm_id":
                        if parent_record is None or projected_location_id("farm", parent_record) is None:
                            row_error = "unresolved_parent_location"
                            break
                        record["location_id"] = projected_location_id("farm", parent_record)
                elif transform == "optional_single_link":
                    if link_row_has_reciprocity_failure(source_table_id, field_id, source_row_id):
                        row_error = "nonreciprocal_relationship"
                        break
                    ids, malformed = _link_ids(source_value)
                    if malformed:
                        row_error = "malformed_link"
                        break
                    if not ids:
                        record[target_column] = None
                        continue
                    if len(ids) != 1:
                        row_error = "missing_or_ambiguous_link"
                        break
                    target_source_table = str(rule["linked_table_id"])
                    resolved = projected_source_ids[target_source_table].get(ids[0])
                    parent_record = projected_records_by_source[target_source_table].get(ids[0])
                    if resolved is None or parent_record is None:
                        row_error = "unresolved_parent_link"
                        break
                    if target_table in {"farm_activity", "expense_event"} and (
                        parent_record.get("farm_id") != record.get("farm_id")
                        or parent_record.get("location_id") != record.get("location_id")
                    ):
                        row_error = "farm_task_scope_mismatch"
                        break
                    record[target_column] = resolved
                elif transform == "optional_single_plot_link":
                    if link_row_has_reciprocity_failure(source_table_id, field_id, source_row_id):
                        row_error = "nonreciprocal_relationship"
                        break
                    ids, malformed = _link_ids(source_value)
                    if malformed:
                        row_error = "malformed_link"
                        break
                    if len(ids) == 1:
                        target_source_table = str(rule["linked_table_id"])
                        resolved = projected_source_ids[target_source_table].get(ids[0])
                        parent_record = projected_records_by_source[target_source_table].get(ids[0])
                        if resolved is None or parent_record is None:
                            row_error = "unresolved_parent_link"
                            break
                        if (
                            parent_record.get("farm_id") != record.get("farm_id")
                            or projected_location_id("plot", parent_record) != record.get("location_id")
                        ):
                            row_error = "farm_plot_scope_mismatch"
                            break
                        record[target_column] = resolved
                    elif len(ids) > 1:
                        record[target_column] = None
                elif transform == "optional_weeks_to_integral_days":
                    value, error = _weeks_to_days(source_value)
                    if error:
                        field_reasons[(source_table_id, field_id)][error] += 1
                    else:
                        record[target_column] = value
                elif transform == "single_select_option_map":
                    if not _populated(source_value):
                        record[target_column] = None
                        continue
                    option_id = _single_select_option_id(source_value)
                    if option_id is None:
                        row_error = "malformed_single_select_option"
                        break
                    mapped_value = rule["option_map"].get(option_id)
                    if mapped_value is None:
                        row_error = "unmapped_single_select_option"
                        break
                    record[target_column] = mapped_value
                elif transform == "single_select_partial_option_map":
                    if not _populated(source_value):
                        row_error = "missing_required_value"
                        break
                    option_id = _single_select_option_id(source_value)
                    if option_id is None:
                        row_error = "malformed_single_select_option"
                        break
                    mapped_value = rule["option_map"].get(option_id)
                    if mapped_value is None:
                        row_error = "unmapped_single_select_option"
                        break
                    record[target_column] = mapped_value
                elif transform == "single_select_label_by_id":
                    if not _populated(source_value):
                        record[target_column] = None
                        continue
                    option_id = _single_select_option_id(source_value)
                    if option_id is None:
                        row_error = "malformed_single_select_option"
                        break
                    if option_id not in rule["approved_option_ids"]:
                        row_error = "unmapped_single_select_option"
                        break
                    field = source_fields.get(field_id, {})
                    options = field.get("select_options", field.get("options", []))
                    label = next(
                        (
                            option.get("value")
                            for option in options
                            if isinstance(option, dict) and str(option.get("id")) == option_id
                        ),
                        None,
                    )
                    if not isinstance(label, str) or not label.strip() or len(label) > 50 or "\x00" in label:
                        row_error = "invalid_single_select_label"
                        break
                    record[target_column] = label
                elif transform == "f001_activity_selection":
                    field = source_fields.get(field_id, {})
                    options = field.get("select_options", [])
                    option_labels: dict[str, str] = {}
                    for option in options:
                        if not isinstance(option, dict):
                            continue
                        option_id = option.get("id")
                        label = option.get("value")
                        if (
                            isinstance(option_id, (int, str))
                            and not isinstance(option_id, bool)
                            and isinstance(label, str)
                        ):
                            option_labels[str(option_id)] = label
                    try:
                        activity_type, source_options = map_f001_activity_selection(
                            source_value, option_labels
                        )
                    except DryRunError as exc:
                        reason = {
                            "empty activity selection": "missing_required_activity_type",
                            "malformed activity selection": "malformed_activity_type_selection",
                            "unknown activity option": "unknown_activity_option",
                            "invalid activity type label": "invalid_activity_type_label",
                        }.get(str(exc), "invalid_activity_type_selection")
                        row_error = reason
                        break
                    record["activity_type"] = activity_type
                    record["activity_type_source_options"] = source_options
                elif transform == "single_select_other_with_source_label":
                    record[target_column] = rule["target_value"]
                    if _populated(source_value):
                        selected_option_id = _single_select_option_id(source_value)
                        field = source_fields.get(field_id, {})
                        options = field.get("select_options", field.get("options", []))
                        option_labels: dict[str, str] = {}
                        for option in options:
                            if not isinstance(option, dict):
                                continue
                            metadata_option_id = option.get("id")
                            label = option.get("value")
                            if (
                                isinstance(metadata_option_id, (int, str))
                                and not isinstance(metadata_option_id, bool)
                                and isinstance(label, str)
                            ):
                                option_labels[str(metadata_option_id)] = label
                        label = option_labels.get(selected_option_id) if selected_option_id else None
                        if not isinstance(label, str) or label not in rule["approved_labels"]:
                            row_error = "unmapped_task_category_option"
                            break
                        record["metadata"] = {"baserow_legacy": {"category_label": label}}
                elif transform == "required_nonnegative_numeric_15_4":
                    if not _populated(source_value):
                        row_error = "missing_required_value"
                        break
                    value, error = _decimal(source_value, scale=4, precision=15)
                    if error:
                        row_error = error
                        break
                    record[target_column] = value
                elif transform == "required_nonnegative_numeric_15_2":
                    if not _populated(source_value):
                        row_error = "missing_required_value"
                        break
                    value, error = _decimal(source_value, scale=2, precision=15)
                    if error:
                        row_error = error
                        break
                    record[target_column] = value
                elif transform == "optional_source_raw_numeric":
                    if not _populated(source_value):
                        continue
                    value, error = _decimal(source_value, scale=8, precision=15)
                    if error:
                        row_error = error
                        break
                    record["source_raw"] = {
                        "baserow_legacy": {"usd_dop_rate": source_value}
                    }

            if row_error is None and target_table == "farm_activity":
                start_date = record.get("activity_date")
                end_date = record.get("activity_end_date")
                if end_date is not None and start_date is not None and end_date < start_date:
                    row_error = "activity_end_before_start"

            if row_error:
                row_reasons[source_table_id][row_error] += 1
                continue

            record.update(spec.get("constants", {}))
            record["id"] = _target_uuid(source_table_id, source_row_id, target_table)
            if spec.get("generated_columns", {}).get("source_id") == "baserow_composite_identity":
                record["source_id"] = f"baserow:{DATABASE_ID}:{source_table_id}:{source_row_id}"
            if spec.get("generated_columns", {}).get("source_row_id") == "copy_source_row_id":
                record["source_row_id"] = int(source_row_id)
            if spec.get("generated_columns", {}).get("slug") == "slugify_name_plus_source_identity":
                record["slug"] = _slug(record["name"], source_table_id, source_row_id)
            provisional.append((source_row_id, record))

        duplicate_keys: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for source_row_id, record in provisional:
            key = tuple(_identity_value(record.get(column)) for column in spec["identity_columns"])
            duplicate_keys[key].append(source_row_id)
        duplicate_source_ids = {
            source_row_id
            for source_ids in duplicate_keys.values()
            if len(source_ids) > 1
            for source_row_id in source_ids
        }
        if duplicate_source_ids:
            row_reasons[source_table_id]["duplicate_identity_candidate"] += len(duplicate_source_ids)

        for source_row_id, record in provisional:
            if source_row_id in duplicate_source_ids:
                continue
            rows_by_target[target_table].append(record)
            projected_source_ids[source_table_id][source_row_id] = record["id"]
            projected_records_by_source[source_table_id][source_row_id] = record
            projected_records_by_target_id[target_table][record["id"]] = record
            projected_by_source[source_table_id] += 1

    for spec in allowlist["target_tables"]:
        row_filter = spec.get("row_filter")
        if not row_filter:
            continue
        if row_filter.get("kind") == "linked_from":
            filter_links = [row_filter]
        elif row_filter.get("kind") == "linked_from_any":
            filter_links = row_filter.get("links", [])
        else:
            raise ProjectionError(f"row filter is unsupported for {spec['target_table']}")
        source_table_id = str(spec["source_table_id"])
        target_table = str(spec["target_table"])
        required_source_ids: set[str] = set()
        for link in filter_links:
            parent_table_id = str(link["source_table_id"])
            profile = edge_profiles.get((parent_table_id, str(link["source_field_id"])))
            if profile is None:
                continue
            projected_parent_ids = set(projected_source_ids[parent_table_id])
            required_source_ids.update(
                related_row_id
                for parent_row_id, related_row_id in profile["valid_edges"]
                if parent_row_id in projected_parent_ids
            )
        source_id_map = projected_source_ids[source_table_id]
        unsupported_source_ids = set(source_id_map) - required_source_ids
        if not unsupported_source_ids:
            continue
        unsupported_target_ids = {source_id_map[source_id] for source_id in unsupported_source_ids}
        rows_by_target[target_table] = [
            record for record in rows_by_target[target_table]
            if record.get("id") not in unsupported_target_ids
        ]
        for source_id in unsupported_source_ids:
            target_id = source_id_map.pop(source_id)
            projected_records_by_source[source_table_id].pop(source_id, None)
            projected_records_by_target_id[target_table].pop(target_id, None)
        projected_by_source[source_table_id] -= len(unsupported_source_ids)
        filtered_by_source[source_table_id] += len(unsupported_source_ids)

    relationship_reports: list[dict[str, Any]] = []
    for relation in allowlist.get("relationship_tables", []):
        source_table_id = str(relation["source_table_id"])
        source_field_id = str(relation["source_field_id"])
        linked_table_id = str(relation["linked_table_id"])
        profile = edge_profiles[(source_table_id, source_field_id)]
        relationship_reasons: Counter[str] = Counter(profile["reasons"])
        projected_edges = 0

        for source_row_id, related_row_id in sorted(profile["valid_edges"]):
            source_target_id = projected_source_ids[source_table_id].get(source_row_id)
            related_target_id = projected_source_ids[linked_table_id].get(related_row_id)
            if source_target_id is None:
                relationship_reasons["source_entity_row_quarantined"] += 1
                continue
            if related_target_id is None:
                relationship_reasons["related_entity_row_quarantined"] += 1
                continue
            rows_by_target[relation["target_table"]].append({
                relation["source_target_column"]: source_target_id,
                relation["related_target_column"]: related_target_id,
                "source_system": allowlist["source"]["system"],
                "source_database_id": int(allowlist["source"]["database_id"]),
                "source_table_id": int(source_table_id),
                "source_field_id": int(source_field_id),
                "source_row_id": int(source_row_id),
                "source_related_table_id": int(linked_table_id),
                "source_related_row_id": int(related_row_id),
            })
            projected_edges += 1

        relationship_reports.append({
            "source_table_id": source_table_id,
            "source_field_id": source_field_id,
            "target_table": relation["target_table"],
            "source_edges": profile["source_edges"],
            "reciprocal_edges": profile["reciprocal_edges"],
            "projected_edges": projected_edges,
            "quarantined_edges": sum(relationship_reasons.values()),
            "quarantine_reasons": dict(sorted(relationship_reasons.items())),
        })

    direct_relationship_reports = []
    for check in allowlist.get("relationship_checks", []):
        source_table_id = str(check["source_table_id"])
        source_field_id = str(check["source_field_id"])
        profile = edge_profiles[(source_table_id, source_field_id)]
        direct_relationship_reports.append({
            "source_table_id": source_table_id,
            "source_field_id": source_field_id,
            "source_target_table": check["source_entity_target"],
            "source_target_column": check["source_target_column"],
            "related_target_table": check["related_entity_target"],
            "source_edges": profile["source_edges"],
            "reciprocal_edges": profile["reciprocal_edges"],
            "verified_edges": len(profile["valid_edges"]),
            "quarantined_edges": sum(profile["reasons"].values()),
            "quarantine_reasons": dict(sorted(profile["reasons"].items())),
        })

    for target_rows in rows_by_target.values():
        target_rows.sort(key=lambda record: (
            record.get("id", ""),
            record.get("reported_metric_id", ""),
            record.get("output_id", ""),
        ))

    out_of_scope_rows = sum(
        count for table_id, count in input_counts.items() if table_id not in {str(spec["source_table_id"]) for spec in allowlist["target_tables"]}
    )
    allowlisted_source_rows = sum(input_counts.get(str(spec["source_table_id"]), 0) for spec in allowlist["target_tables"])
    quarantined_rows = sum(
        input_counts.get(str(spec["source_table_id"]), 0)
        - projected_by_source[str(spec["source_table_id"])]
        - filtered_by_source[str(spec["source_table_id"])]
        for spec in allowlist["target_tables"]
    )
    canonical_rows = {
        target: [
            {column: (str(value) if isinstance(value, Decimal) else value) for column, value in row.items()}
            for row in rows
        ]
        for target, rows in sorted(rows_by_target.items())
    }
    projection_sha256 = hashlib.sha256(
        json.dumps(canonical_rows, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    report = {
        "report_version": 1,
        "run_type": "allowlisted_scratch_projection",
        "import_authorized": False,
        "summary": {
            "source_table_count": len(source_tables),
            "source_rows": sum(input_counts.values()),
            "allowlisted_source_tables": len(allowlist["target_tables"]),
            "allowlisted_source_rows": allowlisted_source_rows,
            "projected_rows": sum(projected_by_source.values()),
            "quarantined_rows": quarantined_rows,
            "filtered_source_rows": sum(filtered_by_source.values()),
            "out_of_scope_rows": out_of_scope_rows,
            "projected_relationship_edges": sum(item["projected_edges"] for item in relationship_reports),
            "projection_sha256": projection_sha256,
        },
        "tables": [
            {
                "source_table_id": str(spec["source_table_id"]),
                "target_table": spec["target_table"],
                "input_rows": input_counts.get(str(spec["source_table_id"]), 0),
                "projected_rows": projected_by_source[str(spec["source_table_id"])],
                "filtered_rows": filtered_by_source[str(spec["source_table_id"])],
                "quarantined_rows": (
                    input_counts.get(str(spec["source_table_id"]), 0)
                    - projected_by_source[str(spec["source_table_id"])]
                    - filtered_by_source[str(spec["source_table_id"])]
                ),
                "quarantine_reasons": dict(sorted(row_reasons[str(spec["source_table_id"])].items())),
            }
            for spec in allowlist["target_tables"]
        ],
        "field_quarantines": [
            {
                "source_table_id": table_id,
                "source_field_id": field_id,
                "quarantined_cells": sum(reasons.values()),
                "reasons": dict(sorted(reasons.items())),
            }
            for (table_id, field_id), reasons in sorted(field_reasons.items())
        ],
        "relationships": relationship_reports,
        "direct_relationship_checks": direct_relationship_reports,
        "out_of_scope_table_count": len(source_tables) - len(allowlist["target_tables"]),
    }
    return {"rows_by_target": rows_by_target, "report": report, "projection_sha256": projection_sha256}


def _sql_literal(value: Any, *, jsonb_value_type: type | None = None) -> str:
    if value is None:
        return "NULL"
    if jsonb_value_type is not None:
        if not isinstance(value, jsonb_value_type):
            raise ProjectionError("projection contains an invalid JSONB value")
        try:
            serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ProjectionError("projection contains an unsupported JSONB value") from exc
        if "\x00" in serialized:
            raise ProjectionError("projection contains an unsupported JSONB value")
        return f"{_sql_literal(serialized)}::jsonb"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str) or "\x00" in value:
        raise ProjectionError("projection contains an unsupported SQL literal")
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    escaped = escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f"E'{escaped}'"


def build_transaction_sql(rows_by_target: dict[str, list[dict[str, Any]]]) -> str:
    """Create one rollback-only psql script with row-count assertions markers."""
    unknown_targets = set(rows_by_target) - set(TARGET_COLUMNS)
    if unknown_targets:
        raise ProjectionError("projection contains an unapproved target table")
    statements = ["SET standard_conforming_strings = on;"]
    for phase in ("before",):
        for target in TARGET_COLUMNS:
            statements.append(
                f'SELECT \'DRYRUN|{phase}|{target}|\' || COUNT(*)::text FROM "{target}";'
            )
    statements.extend(["BEGIN;", "SET CONSTRAINTS ALL DEFERRED;"])
    for target, columns in TARGET_COLUMNS.items():
        records = rows_by_target.get(target, [])
        if not records:
            continue
        tuples: list[str] = []
        expected_columns = set(columns)
        for record in records:
            if set(record) != expected_columns:
                raise ProjectionError(f"projected columns do not match the approved schema for {target}")
            tuples.append(
                "(" + ", ".join(
                    _sql_literal(
                        record[column],
                        jsonb_value_type=JSONB_VALUE_TYPES.get((target, column)),
                    )
                    for column in columns
                ) + ")"
            )
        column_sql = ", ".join(f'"{column}"' for column in columns)
        statements.append(
            f'INSERT INTO "{target}" ({column_sql}) VALUES\n' + ",\n".join(tuples) + ";"
        )
    statements.append("SET CONSTRAINTS ALL IMMEDIATE;")
    for target in TARGET_COLUMNS:
        statements.append(
            f'SELECT \'DRYRUN|during|{target}|\' || COUNT(*)::text FROM "{target}";'
        )
    statements.append("ROLLBACK;")
    for target in TARGET_COLUMNS:
        statements.append(
            f'SELECT \'DRYRUN|after|{target}|\' || COUNT(*)::text FROM "{target}";'
        )
    return "\n".join(statements) + "\n"


def validate_scratch_migration_counts(raw_counts: str, expected_schema_migrations: int) -> dict[str, int]:
    """Require a complete, seed-free schema migration history in scratch."""
    parts = raw_counts.strip().split("|")
    if len(parts) != 4 or any(not part.isdigit() for part in parts):
        raise ProjectionError("scratch migration history returned invalid aggregate counts")
    schema_applied, seed_migrations, pending_or_failed, total = (int(part) for part in parts)
    if (
        schema_applied != expected_schema_migrations
        or seed_migrations != 0
        or pending_or_failed != 0
        or total != expected_schema_migrations
    ):
        raise ProjectionError("scratch database must contain only the complete schema-only migrations")
    return {
        "schema_applied": schema_applied,
        "seed_migrations": seed_migrations,
        "pending_or_failed": pending_or_failed,
    }


def validate_tmpfs_filesystem_output(output: str) -> None:
    """Require df to confirm the PostgreSQL data path is backed by tmpfs."""
    for line in output.splitlines()[1:]:
        columns = line.split()
        if (
            len(columns) >= 7
            and columns[1] == "tmpfs"
            and columns[-1].rstrip("/") == "/var/lib/postgresql/data"
        ):
            return
    raise ProjectionError("scratch PostgreSQL data directory is not mounted on tmpfs")


def validate_scratch_container(inspect_data: dict[str, Any]) -> None:
    """Reject any container that is not label-scoped, networkless, and ephemeral."""
    config = inspect_data.get("Config", {})
    host_config = inspect_data.get("HostConfig", {})
    labels = config.get("Labels") or {}
    if config.get("Image") != "postgis/postgis:16-3.4":
        raise ProjectionError("scratch container must use the approved PostGIS image")
    required_env = {
        "POSTGRES_DB=ki21_scratch",
        "POSTGRES_USER=postgres",
        "POSTGRES_HOST_AUTH_METHOD=trust",
    }
    if not required_env.issubset(set(config.get("Env") or [])):
        raise ProjectionError("scratch container PostgreSQL settings do not match the isolated rehearsal")
    state = inspect_data.get("State", {})
    if not state.get("Running") or (state.get("Health") or {}).get("Status") != "healthy":
        raise ProjectionError("scratch PostgreSQL container must be running and healthy")
    if labels.get("kokonut.dry-run") != "baserow-115056":
        raise ProjectionError("scratch container lacks the Baserow dry-run safety label")
    if host_config.get("NetworkMode") != "none":
        raise ProjectionError("scratch container must use network mode none")
    if host_config.get("PortBindings"):
        raise ProjectionError("scratch container must not have published ports")
    if "/var/lib/postgresql/data" not in (host_config.get("Tmpfs") or {}):
        raise ProjectionError("scratch PostgreSQL data directory must be tmpfs-backed")
    mounts = inspect_data.get("Mounts", [])
    if any(mount.get("Type") == "volume" for mount in mounts):
        raise ProjectionError("scratch container must not use Docker volumes")
    if any(mount.get("Type") == "bind" and mount.get("RW") for mount in mounts):
        raise ProjectionError("scratch container bind mounts must be read-only")
    if not any(
        mount.get("Type") == "bind"
        and mount.get("Destination") == "/scratch-schemas"
        and not mount.get("RW")
        for mount in mounts
    ):
        raise ProjectionError("scratch container must mount repository schemas read-only")


def run_postgres_transaction(
    container_name: str,
    rows_by_target: dict[str, list[dict[str, Any]]],
    expected_schema_migrations: int,
) -> dict[str, Any]:
    """Exercise target constraints in a verified isolated container, then assert rollback."""
    if not re.fullmatch(r"ki21-baserow-dryrun-[a-f0-9]{8,16}", container_name):
        raise ProjectionError("scratch container name is outside the approved dry-run namespace")
    try:
        inspect_result = subprocess.run(
            ["docker", "inspect", container_name], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectionError("could not inspect the scratch PostgreSQL container") from exc
    if inspect_result.returncode != 0:
        raise ProjectionError("scratch PostgreSQL container is unavailable")
    try:
        inspect_data = json.loads(inspect_result.stdout)[0]
    except (json.JSONDecodeError, IndexError, TypeError) as exc:
        raise ProjectionError("scratch PostgreSQL container inspection was invalid") from exc
    validate_scratch_container(inspect_data)
    migration_query = (
        "SELECT "
        "(SELECT COUNT(*)::text FROM schema_migration WHERE migration_id LIKE 'schema:%' AND status = 'applied') || '|' || "
        "(SELECT COUNT(*)::text FROM schema_migration WHERE migration_id LIKE 'seed:%') || '|' || "
        "(SELECT COUNT(*)::text FROM schema_migration WHERE status IS DISTINCT FROM 'applied') || '|' || "
        "COUNT(*)::text FROM schema_migration"
    )
    try:
        migration_result = subprocess.run(
            [
                "docker", "exec", container_name,
                "psql", "-X", "-U", "postgres", "-d", "ki21_scratch",
                "-v", "ON_ERROR_STOP=1", "-A", "-t", "-q", "-c", migration_query,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectionError("could not verify scratch schema migration state") from exc
    if migration_result.returncode != 0:
        raise ProjectionError("could not verify scratch schema migration state")
    migration_state = validate_scratch_migration_counts(migration_result.stdout, expected_schema_migrations)

    try:
        filesystem_result = subprocess.run(
            ["docker", "exec", container_name, "df", "-P", "-T", "/var/lib/postgresql/data"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectionError("could not verify scratch PostgreSQL data storage") from exc
    if filesystem_result.returncode != 0:
        raise ProjectionError("could not verify scratch PostgreSQL data storage")
    validate_tmpfs_filesystem_output(filesystem_result.stdout)

    scratch_dir = Path(os.environ.get("TMPDIR", "/home/ubuntu/.hermes/cache/scratch"))
    scratch_dir.mkdir(parents=True, exist_ok=True)
    sql = build_transaction_sql(rows_by_target)
    handle, sql_path_text = tempfile.mkstemp(prefix="ki21-baserow-projection-", suffix=".sql", dir=scratch_dir)
    sql_path = Path(sql_path_text)
    try:
        os.chmod(sql_path, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(sql)
        with sql_path.open(encoding="utf-8") as stream:
            result = subprocess.run(
                [
                    "docker", "exec", "-i", container_name,
                    "psql", "-X", "-U", "postgres", "-d", "ki21_scratch",
                    "-v", "ON_ERROR_STOP=1", "-A", "-t", "-q",
                ],
                stdin=stream,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectionError("scratch PostgreSQL transaction could not be executed") from exc
    finally:
        sql_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise ProjectionError("scratch PostgreSQL constraint rehearsal failed; raw database details suppressed")
    observed: dict[str, dict[str, int]] = {phase: {} for phase in ("before", "during", "after")}
    for line in result.stdout.splitlines():
        parts = line.split("|")
        if len(parts) == 4 and parts[0] == "DRYRUN" and parts[1] in observed and parts[2] in TARGET_COLUMNS:
            try:
                observed[parts[1]][parts[2]] = int(parts[3])
            except ValueError as exc:
                raise ProjectionError("scratch PostgreSQL returned an invalid aggregate count") from exc
    for phase in observed:
        if set(observed[phase]) != set(TARGET_COLUMNS):
            raise ProjectionError("scratch PostgreSQL omitted a target aggregate count")
    for target in TARGET_COLUMNS:
        expected = len(rows_by_target.get(target, []))
        if observed["during"][target] - observed["before"][target] != expected:
            raise ProjectionError(f"scratch PostgreSQL projected-row count did not match for {target}")
        if observed["after"][target] != observed["before"][target]:
            raise ProjectionError(f"scratch PostgreSQL rollback verification failed for {target}")
    return {
        "image": "postgis/postgis:16-3.4",
        "network_mode": "none",
        "published_ports": False,
        "database_data_storage": "tmpfs",
        "schema_migrations": migration_state,
        "transaction_result": "rolled_back",
        "constraint_rehearsal": "passed",
        "before_counts": observed["before"],
        "during_counts": observed["during"],
        "after_rollback_counts": observed["after"],
        "projected_rows": {target: len(rows_by_target.get(target, [])) for target in TARGET_COLUMNS},
        "target_row_count_delta_after_rollback": {
            target: observed["after"][target] - observed["before"][target] for target in TARGET_COLUMNS
        },
    }


def _schema_fingerprint(schema_dir: Path) -> tuple[str, int]:
    migration_files = sorted(Path(schema_dir).glob("*.sql"))
    if not migration_files:
        raise ProjectionError("target schema directory contains no SQL migrations")
    digest = hashlib.sha256()
    for migration in migration_files:
        digest.update(migration.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(migration.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest(), len(migration_files)


def run_projection_rehearsal(
    export_path: Path,
    manifest_path: Path,
    crosswalk_path: Path,
    allowlist_path: Path,
    container_name: str,
    schema_dir: Path,
) -> dict[str, Any]:
    """Run verified preflight, explicit projection, and scratch-only rollback rehearsal."""
    try:
        preflight = run_dry_run(export_path, manifest_path, crosswalk_path)
    except DryRunError as exc:
        raise ProjectionError("source preflight failed; scratch database was not used") from exc
    preflight_summary = preflight["summary"]
    if preflight_summary["structural_issue_count"] != 0:
        raise ProjectionError("source preflight reported structural issues; scratch database was not used")

    try:
        export_bytes = Path(export_path).read_bytes()
        crosswalk_bytes = Path(crosswalk_path).read_bytes()
        allowlist_bytes = Path(allowlist_path).read_bytes()
        export_data = json.loads(export_bytes)
        crosswalk_text = crosswalk_bytes.decode("utf-8")
        allowlist = _validate_allowlist_document(json.loads(allowlist_bytes))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectionError("could not read projection inputs") from exc
    source = preflight["source"]
    if hashlib.sha256(export_bytes).hexdigest() != source["snapshot_sha256"]:
        raise ProjectionError("source export changed after preflight; scratch database was not used")
    if hashlib.sha256(crosswalk_bytes).hexdigest() != source["crosswalk_sha256"]:
        raise ProjectionError("crosswalk changed after preflight; scratch database was not used")
    if str(export_data.get("id")) != DATABASE_ID:
        raise ProjectionError("source export database ID does not match the reviewed database")
    validate_allowlist(export_data, allowlist, crosswalk_text)
    projection = build_projection(export_data, allowlist)
    schema_sha256, migration_count = _schema_fingerprint(schema_dir)
    scratch_result = run_postgres_transaction(
        container_name, projection["rows_by_target"], expected_schema_migrations=migration_count
    )

    run_material = ":".join(
        [
            source["snapshot_sha256"],
            source["manifest_sha256"],
            source["crosswalk_sha256"],
            hashlib.sha256(allowlist_bytes).hexdigest(),
            schema_sha256,
            projection["projection_sha256"],
        ]
    )
    return {
        "report_version": 1,
        "run_type": "allowlisted_scratch_postgres_constraint_rehearsal",
        "run_id": hashlib.sha256(run_material.encode("ascii")).hexdigest(),
        "source": {
            "database_id": DATABASE_ID,
            "snapshot_sha256": source["snapshot_sha256"],
            "manifest_sha256": source["manifest_sha256"],
            "crosswalk_sha256": source["crosswalk_sha256"],
            "whole_export_parsed_in_memory": True,
        },
        "preflight_summary": preflight_summary,
        "allowlist": {
            "sha256": hashlib.sha256(allowlist_bytes).hexdigest(),
            "target_tables": [spec["target_table"] for spec in allowlist["target_tables"]],
            "unlisted_fields_and_tables_excluded": True,
            "import_authorized": False,
        },
        "projection": projection["report"],
        "target_schema": {"sha256": schema_sha256, "migration_files": migration_count},
        "scratch_postgres": scratch_result,
        "execution": {
            "database_connections": 1,
            "connected_only_to_verified_scratch": True,
            "transaction_rolled_back": True,
            "target_row_count_delta_after_rollback": scratch_result["target_row_count_delta_after_rollback"],
            "staging_touched": False,
            "production_touched": False,
            "raw_row_values_emitted": False,
            "import_authorized": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an allowlisted Baserow projection inside an isolated PostgreSQL transaction, then roll it back"
    )
    parser.add_argument("--export", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--crosswalk", required=True, type=Path)
    parser.add_argument("--allowlist", required=True, type=Path)
    parser.add_argument("--scratch-container", required=True)
    parser.add_argument("--schema-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        report = run_projection_rehearsal(
            args.export,
            args.manifest,
            args.crosswalk,
            args.allowlist,
            args.scratch_container,
            args.schema_dir,
        )
    except (DryRunError, ProjectionError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        os.chmod(args.output, 0o600)
    except OSError as exc:
        print("Error: could not write the aggregate-only rehearsal report", file=sys.stderr)
        return 1
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
