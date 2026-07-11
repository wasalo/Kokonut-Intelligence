"""SPARQL-to-SQL translator for basic graph pattern queries."""

from __future__ import annotations

import re
from typing import Any

from services.common.logging import get_logger

logger = get_logger("rdf.sparql_engine")


def parse_select_query(query: str) -> dict:
    query = query.strip().rstrip(";")
    variables = []
    patterns = []
    limit = 1000

    select_match = re.match(r"SELECT\s+(.*?)\s+WHERE", query, re.IGNORECASE | re.DOTALL)
    if select_match:
        variables = [v.strip().lstrip("?") for v in select_match.group(1).split() if v.strip().startswith("?")]

    where_match = re.search(r"WHERE\s*\{(.*?)\}", query, re.IGNORECASE | re.DOTALL)
    if where_match:
        body = where_match.group(1)
        triple_pattern = re.findall(r"(\?\w+|<[^>]+>|\"[^\"]*\")\s+(\?\w+|<[^>]+>)\s+(\?\w+|<[^>]+>|\"[^\"]*\")\s*\.?", body)
        for s, p, o in triple_pattern:
            patterns.append({
                "subject": s.strip("?") if s.startswith("?") else s.strip("<>"),
                "predicate": p.strip("?") if p.startswith("?") else p.strip("<>"),
                "object": o.strip("?") if o.startswith("?") else o.strip("<>"),
                "subject_is_var": s.startswith("?"),
                "predicate_is_var": p.startswith("?"),
                "object_is_var": o.startswith("?"),
            })

    limit_match = re.search(r"LIMIT\s+(\d+)", query, re.IGNORECASE)
    if limit_match:
        limit = int(limit_match.group(1))

    return {"variables": variables, "patterns": patterns, "limit": limit}


def translate_basic_graph_pattern(patterns: list[dict], variables: list[str]) -> str:
    if not patterns:
        return "SELECT * FROM rdf_triple LIMIT 1000"

    joins = []
    conditions = []
    select_cols = []
    aliases = {}

    for i, pat in enumerate(patterns):
        alias = f"t{i}"
        aliases[i] = alias

        if not pat["subject_is_var"]:
            conditions.append(f"{alias}.subject = :s{i}")
        elif pat["subject"] in variables:
            select_cols.append(f"{alias}.subject AS ?{pat['subject']}")

        if not pat["predicate_is_var"]:
            conditions.append(f"{alias}.predicate = :p{i}")
        elif pat["predicate"] in variables:
            select_cols.append(f"{alias}.predicate AS ?{pat['predicate']}")

        if not pat["object_is_var"]:
            if pat["object"].startswith("kokonut:") or pat["object"].startswith("http"):
                conditions.append(f"{alias}.object_iri = :o{i}")
            else:
                conditions.append(f"{alias}.object_value = :o{i}")
        elif pat["object"] in variables:
            select_cols.append(f"{alias}.object_value AS ?{pat['object']}")

    select = ", ".join(select_cols) if select_cols else "*"
    from_clause = f"rdf_triple t0"
    where = " AND ".join(conditions) if conditions else "TRUE"

    return f"SELECT {select} FROM {from_clause} WHERE {where}"


def execute_sparql(conn, query: str) -> dict:
    parsed = parse_select_query(query)
    if not parsed["patterns"]:
        return {"variables": [], "results": []}

    sql = translate_basic_graph_pattern(parsed["patterns"], parsed["variables"])
    params = {}
    for i, pat in enumerate(parsed["patterns"]):
        if not pat["subject_is_var"]:
            params[f"s{i}"] = pat["subject"]
        if not pat["predicate_is_var"]:
            params[f"p{i}"] = pat["predicate"]
        if not pat["object_is_var"]:
            params[f"o{i}"] = pat["object"]

    params["limit"] = parsed["limit"]
    sql_with_limit = f"{sql} LIMIT :limit"

    result = conn.execute(conn.text(sql_with_limit), params)
    rows = [dict(r) for r in result.mappings()]

    return {"variables": parsed["variables"], "results": rows}


def list_named_graphs(conn) -> list[dict]:
    result = conn.execute(
        conn.text("SELECT * FROM rdf_named_graph ORDER BY triple_count DESC")
    )
    return [dict(r) for r in result.mappings()]
