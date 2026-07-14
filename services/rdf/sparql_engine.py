"""SPARQL-to-SQL translator for basic graph pattern queries."""

from __future__ import annotations

import json
import re

from services.common.logging import get_logger

logger = get_logger("rdf.sparql_engine")

DEFAULT_LIMIT = 1000
MAX_LIMIT = 1000
_TERM = r'(?:\?[A-Za-z_][\w-]*|<[^<>\s]+>|"(?:[^"\\]|\\.)*")'
_QUERY = re.compile(
    rf"^\s*SELECT\s+(?P<select>\?[A-Za-z_][\w-]*(?:\s+\?[A-Za-z_][\w-]*)*)"
    rf"\s+WHERE\s*\{{(?P<body>.*?)\}}\s*(?:LIMIT\s+(?P<limit>\d+))?\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_TRIPLE = re.compile(rf"\s*({_TERM})\s+({_TERM})\s+({_TERM})\s*(?:\.|$)", re.DOTALL)


def _parse_term(token: str) -> tuple[str, bool, str]:
    if token.startswith("?"):
        return token[1:], True, "variable"
    if token.startswith("<"):
        return token[1:-1], False, "iri"
    # The supported literal form is a quoted string, with common escapes decoded.
    try:
        value = json.loads(token)
    except json.JSONDecodeError as exc:
        raise ValueError("Malformed string literal in SPARQL query") from exc
    return value, False, "literal"


def parse_select_query(query: str) -> dict:
    """Parse the intentionally small SELECT/WHERE basic graph pattern subset."""
    match = _QUERY.fullmatch(query)
    if not match:
        raise ValueError("Only SELECT variables WHERE { basic triple patterns } [LIMIT n] is supported")

    variables = [token[1:] for token in match.group("select").split()]
    if len(set(variables)) != len(variables):
        raise ValueError("SELECT variables must be unique")

    body = match.group("body").strip()
    patterns = []
    position = 0
    while position < len(body):
        triple = _TRIPLE.match(body, position)
        if not triple or triple.end() == position:
            raise ValueError("Malformed or unsupported triple pattern in WHERE clause")
        terms = [_parse_term(token) for token in triple.groups()]
        if terms[0][2] == "literal":
            raise ValueError("A triple subject cannot be a literal")
        if terms[1][2] == "literal":
            raise ValueError("A triple predicate cannot be a literal")
        patterns.append({
            "subject": terms[0][0], "subject_is_var": terms[0][1], "subject_type": terms[0][2],
            "predicate": terms[1][0], "predicate_is_var": terms[1][1], "predicate_type": terms[1][2],
            "object": terms[2][0], "object_is_var": terms[2][1], "object_type": terms[2][2],
        })
        position = triple.end()
    if not patterns:
        raise ValueError("WHERE clause must contain at least one triple pattern")

    bound = {term[0] for pattern in patterns for term in (
        (pattern["subject"], pattern["subject_is_var"]),
        (pattern["predicate"], pattern["predicate_is_var"]),
        (pattern["object"], pattern["object_is_var"]),
    ) if term[1]}
    if not set(variables).issubset(bound):
        raise ValueError("Every SELECT variable must be bound in the WHERE clause")

    requested_limit = int(match.group("limit") or DEFAULT_LIMIT)
    if requested_limit < 1:
        raise ValueError("LIMIT must be at least 1")
    return {"variables": variables, "patterns": patterns, "limit": min(requested_limit, MAX_LIMIT)}


def _term_sql(alias: str, position: str) -> tuple[str, str]:
    if position == "object":
        return f"COALESCE({alias}.object_iri, {alias}.object_value)", (
            f"CASE WHEN {alias}.object_iri IS NOT NULL THEN 'iri' ELSE 'literal:' || {alias}.object_type END"
        )
    return f"{alias}.{position}", "'iri'"


def translate_basic_graph_pattern(patterns: list[dict], variables: list[str]) -> str:
    if not patterns:
        raise ValueError("At least one triple pattern is required")

    conditions = []
    bindings: dict[str, tuple[str, str]] = {}
    for i, pattern in enumerate(patterns):
        alias = f"t{i}"
        for position in ("subject", "predicate", "object"):
            value = pattern[position]
            value_sql, kind_sql = _term_sql(alias, position)
            if pattern[f"{position}_is_var"]:
                previous = bindings.get(value)
                if previous:
                    conditions.extend((f"{value_sql} = {previous[0]}", f"{kind_sql} = {previous[1]}"))
                else:
                    bindings[value] = (value_sql, kind_sql)
            elif position == "object":
                column = "object_iri" if pattern["object_type"] == "iri" else "object_value"
                conditions.append(f"{alias}.{column} = :o{i}")
            else:
                conditions.append(f"{alias}.{position} = :{position[0]}{i}")

    select = ", ".join(f'{bindings[var][0]} AS "{var}"' for var in variables)
    from_clause = ", ".join(f"rdf_triple AS t{i}" for i in range(len(patterns)))
    where = " AND ".join(conditions) if conditions else "TRUE"
    return f"SELECT {select} FROM {from_clause} WHERE {where}"


def execute_sparql(conn, query: str) -> dict:
    parsed = parse_select_query(query)
    sql = translate_basic_graph_pattern(parsed["patterns"], parsed["variables"])
    params = {"limit": parsed["limit"]}
    for i, pattern in enumerate(parsed["patterns"]):
        for position, prefix in (("subject", "s"), ("predicate", "p"), ("object", "o")):
            if not pattern[f"{position}_is_var"]:
                params[f"{prefix}{i}"] = pattern[position]
    result = conn.execute(conn.text(f"{sql} LIMIT :limit"), params)
    return {"variables": parsed["variables"], "results": [dict(row) for row in result.mappings()]}


def list_named_graphs(conn) -> list[dict]:
    result = conn.execute(conn.text("SELECT * FROM rdf_named_graph ORDER BY triple_count DESC"))
    return [dict(row) for row in result.mappings()]
