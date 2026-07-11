"""RDF serialization: Turtle, N-Triples, JSON-LD."""

from __future__ import annotations

import json
from typing import Any


def to_turtle(triples: list[dict], namespaces: dict = None) -> str:
    ns = namespaces or {}
    lines = []
    for prefix, uri in ns.items():
        lines.append(f"@prefix {prefix}: <{uri}> .")
    if ns:
        lines.append("")

    subjects = {}
    for t in triples:
        s = t["subject"]
        if s not in subjects:
            subjects[s] = []
        subjects[s].append(t)

    for s, stmts in subjects.items():
        lines.append(f"<{s}>")
        for i, t in enumerate(stmts):
            p = t["predicate"]
            if t.get("object_iri"):
                o = f"<{t['object_iri']}>"
            elif t.get("object_type") == "integer":
                o = f'"{t["object_value"]}"^^xsd:integer'
            elif t.get("object_type") == "decimal":
                o = f'"{t["object_value"]}"^^xsd:decimal'
            elif t.get("object_type") == "boolean":
                o = f'"{t["object_value"]}"^^xsd:boolean'
            else:
                o = f'"{t.get("object_value", "")}"'
            sep = " ;" if i < len(stmts) - 1 else " ."
            lines.append(f"    <{p}> {o}{sep}")
        lines.append("")

    return "\n".join(lines)


def to_ntriples(triples: list[dict]) -> str:
    lines = []
    for t in triples:
        s = f"<{t['subject']}>"
        p = f"<{t['predicate']}>"
        if t.get("object_iri"):
            o = f"<{t['object_iri']}>"
        else:
            escaped = (t.get("object_value") or "").replace("\\", "\\\\").replace('"', '\\"')
            o = f'"{escaped}"'
        lines.append(f"{s} {p} {o} .")
    return "\n".join(lines)


def to_jsonld(triples: list[dict], context: dict = None) -> dict:
    graph = []
    subjects = {}
    for t in triples:
        s = t["subject"]
        if s not in subjects:
            subjects[s] = {"@id": s}
            graph.append(subjects[s])
        prop = t["predicate"].split("#")[-1].split("/")[-1]
        if t.get("object_iri"):
            subjects[s][prop] = {"@id": t["object_iri"]}
        else:
            val = t.get("object_value", "")
            if t.get("object_type") == "integer":
                val = int(val)
            elif t.get("object_type") == "decimal":
                val = float(val)
            elif t.get("object_type") == "boolean":
                val = val.lower() == "true"
            subjects[s][prop] = val

    doc = {"@graph": graph}
    if context:
        doc["@context"] = context
    return doc


def from_jsonld(jsonld_doc: dict, graph_name: str = "default") -> list[dict]:
    triples = []
    graph = jsonld_doc.get("@graph", [])
    for entity in graph:
        subject = entity.get("@id", "")
        for key, value in entity.items():
            if key in ("@id", "@type", "@context"):
                continue
            predicate = key
            if isinstance(value, dict) and "@id" in value:
                triples.append({
                    "subject": subject, "predicate": predicate,
                    "object_iri": value["@id"], "graph_name": graph_name,
                })
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and "@id" in item:
                        triples.append({
                            "subject": subject, "predicate": predicate,
                            "object_iri": item["@id"], "graph_name": graph_name,
                        })
                    else:
                        triples.append({
                            "subject": subject, "predicate": predicate,
                            "object_value": str(item), "graph_name": graph_name,
                        })
            else:
                triples.append({
                    "subject": subject, "predicate": predicate,
                    "object_value": str(value), "graph_name": graph_name,
                })
    return triples
