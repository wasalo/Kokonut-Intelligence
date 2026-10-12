"""Summarize saved Metabase content without emitting query definitions or values."""

from __future__ import annotations

import json
import os
from collections import Counter

import psycopg2


FEATURE_KEYS = ("aggregation", "breakout", "filter", "order-by", "joins", "fields")


def parse_object(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}


def collect_source_tables(value: object, found: set[int]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source-table" and isinstance(child, int):
                found.add(child)
            collect_source_tables(child, found)
    elif isinstance(value, list):
        for child in value:
            collect_source_tables(child, found)


def collect_source_reference_kinds(value: object, kinds: set[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source-table":
                if isinstance(child, int):
                    kinds.add("physical_table")
                elif isinstance(child, str) and child.startswith("card__"):
                    kinds.add("saved_question")
                elif child is None:
                    kinds.add("empty")
                else:
                    kinds.add("other")
            elif key == "source-query":
                kinds.add("nested_query")
            collect_source_reference_kinds(child, kinds)
    elif isinstance(value, list):
        for child in value:
            collect_source_reference_kinds(child, kinds)


def collect_feature_counts(value: object, counts: Counter[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FEATURE_KEYS and isinstance(child, list):
                counts[key] += len(child)
            collect_feature_counts(child, counts)
    elif isinstance(value, list):
        for child in value:
            collect_feature_counts(child, counts)


def main() -> int:
    password = os.environ.get("KOKONUT_DB_ADMIN_PASSWORD", "")
    if not password:
        raise SystemExit("isolated database admin credential is required")
    conn = psycopg2.connect(
        host=os.environ.get("PG_HOST", "database"),
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=os.environ.get("PG_DB", "metabase"),
        user=os.environ.get("KOKONUT_DB_ADMIN_USER", "kokonut"),
        password=password,
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT card.id, card.name, card.display, card.query_type,
                          card.dataset_query, card.database_id, card.archived,
                          db.engine
                   FROM public.report_card AS card
                   LEFT JOIN public.metabase_database AS db ON db.id=card.database_id
                   ORDER BY card.id"""
            )
            card_rows = cur.fetchall()
            source_table_ids: set[int] = set()
            cards = []
            for card_id, name, display, query_type, dataset_query, database_id, archived, engine in card_rows:
                definition = parse_object(dataset_query)
                query = definition.get("query", {})
                source_tables: set[int] = set()
                collect_source_tables(query, source_tables)
                source_table_ids.update(source_tables)
                source_reference_kinds: set[str] = set()
                collect_source_reference_kinds(query, source_reference_kinds)
                feature_counts: Counter[str] = Counter()
                collect_feature_counts(query, feature_counts)
                mode = "native" if "native" in definition else "query"
                cards.append(
                    {
                        "card_id": card_id,
                        "name": name,
                        "visualization": display,
                        "query_type": query_type,
                        "query_mode": mode,
                        "source_reference_kinds": sorted(source_reference_kinds) or ["unresolved"],
                        "source_engine": engine or "unassigned",
                        "source_table_ids": sorted(source_tables),
                        "feature_counts": dict(sorted(feature_counts.items())),
                        "archived": bool(archived),
                    }
                )

            tables = {}
            if source_table_ids:
                cur.execute(
                    "SELECT id, name, schema FROM public.metabase_table WHERE id = ANY(%s)",
                    (sorted(source_table_ids),),
                )
                tables = {
                    int(table_id): {"name": name, "schema": schema_name}
                    for table_id, name, schema_name in cur.fetchall()
                }
            for card in cards:
                card["source_tables"] = [
                    tables.get(table_id, {"name": "unresolved", "schema": None})
                    for table_id in card.pop("source_table_ids")
                ]

            cur.execute(
                """SELECT dashboard.id, dashboard.name, dashboard.archived,
                          card.id, card.name, slot.row, slot.col,
                          slot.size_x, slot.size_y
                   FROM public.report_dashboard AS dashboard
                   LEFT JOIN public.report_dashboardcard AS slot
                     ON slot.dashboard_id=dashboard.id
                   LEFT JOIN public.report_card AS card ON card.id=slot.card_id
                   ORDER BY dashboard.id, slot.row, slot.col, slot.id"""
            )
            dashboard_rows = cur.fetchall()
            dashboards = []
            dashboard_cards = Counter()
            for dashboard_id, dashboard_name, dashboard_archived, card_id, card_name, row, col, size_x, size_y in dashboard_rows:
                if not dashboards or dashboards[-1]["dashboard_id"] != dashboard_id:
                    dashboards.append(
                        {
                            "dashboard_id": dashboard_id,
                            "name": dashboard_name,
                            "archived": bool(dashboard_archived),
                            "placements": [],
                        }
                    )
                if card_id is not None:
                    dashboard_cards[card_id] += 1
                    dashboards[-1]["placements"].append(
                        {
                            "card_id": card_id,
                            "card_name": card_name,
                            "row": row,
                            "column": col,
                            "width": size_x,
                            "height": size_y,
                        }
                    )

            for card in cards:
                card["dashboard_placements"] = dashboard_cards[card["card_id"]]

            visualization_counts = Counter(card["visualization"] for card in cards)
            source_engine_counts = Counter(card["source_engine"] for card in cards)
            reference_kind_counts = Counter(
                kind for card in cards for kind in card["source_reference_kinds"]
            )
            feature_totals: Counter[str] = Counter()
            for card in cards:
                feature_totals.update(card["feature_counts"])

            dashboard_count = len(dashboards)
            placement_count = sum(len(dashboard["placements"]) for dashboard in dashboards)

            cur.execute("SELECT count(*) FROM public.core_user")
            users = int(cur.fetchone()[0])

        print(
            json.dumps(
                {
                    "result": "passed",
                    "scope": "isolated restored metadata; structural summary only",
                    "cards": cards,
                    "dashboards": dashboards,
                    "summary": {
                        "card_count": len(cards),
                        "dashboard_count": dashboard_count,
                        "dashboard_placement_count": placement_count,
                        "source_engine_counts": dict(sorted(source_engine_counts.items())),
                        "source_reference_kind_counts": dict(sorted(reference_kind_counts.items())),
                        "visualization_counts": dict(sorted(visualization_counts.items())),
                        "query_feature_counts": dict(sorted(feature_totals.items())),
                    },
                    "user_count": users,
                    "raw_dataset_query_or_sql_printed": False,
                    "query_filter_values_or_rows_read_from_domain_sources": False,
                    "card_descriptions_or_user_records_read": False,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
