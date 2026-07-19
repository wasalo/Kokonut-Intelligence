"""Visual graph descriptors for the State of Kokonut report.

This module builds structured graph descriptors (nodes, edges, layout hints)
for the visual timelines described in the Kokonut ecosystem reporting work:

1. Vertical tree timeline -- ecosystem journey 2021->2024 (and reusable for
   farm development phases and Kokonut Seeds short-cycle crop timelines).
2. Circular Ikigai-inspired timeline (v1 + v2) -- Kokonut at the center, one
   quadrant per year 2021-2024, color-coded, with v2 adding an outer foundation
   ring, an outward growth arrow, and concentric ripples.

Renderers emit dependency-free Mermaid text (mirrors
``services.workflow_specs.render.render_mermaid``) plus a JSON descriptor that
any Mermaid-capable viewer or the Data Hub can render. No charting library is
required. All builders are read-only against the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from services.common.logging import get_logger

logger = get_logger(__name__)

# Year-of-record palette for the ecosystem / Ikigai views.
YEAR_COLORS = {
    2021: "#1f77b4",  # foundation year
    2022: "#2ca02c",
    2023: "#ff7f0e",
    2024: "#9467bd",
}

ACTOR_COLORS = {
    "network": "#1f77b4",
    "dao": "#2ca02c",
    "foundation": "#ff7f0e",
    "genesis": "#9467bd",
    "seeds": "#8c564b",
}

FOUNDATION_YEARS = (2021, 2022, 2023, 2024)


@dataclass
class GraphNode:
    """A single node in a graph descriptor."""

    id: str
    label: str
    kind: str = "node"  # year, actor, round, proposal, zone, crop, stage, center, ring, ripple, growth
    parent: Optional[str] = None
    year: Optional[int] = None
    actor: Optional[str] = None
    status: Optional[str] = None
    color: Optional[str] = None
    meta: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A directed edge between two nodes."""

    source: str
    target: str
    label: Optional[str] = None
    kind: str = "parent"  # parent, growth, ripple


@dataclass
class GraphDescriptor:
    """A layout-agnostic description of a graph."""

    name: str
    layout: str  # "tree" | "circular"
    title: str
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "layout": self.layout,
            "title": self.title,
            "nodes": [vars(n) for n in self.nodes],
            "edges": [vars(e) for e in self.edges],
        }

    def to_mermaid(self) -> str:
        if self.layout == "circular":
            return _render_mermaid_circular(self)
        return _render_mermaid_tree(self)


def _escape(value: str) -> str:
    return value.replace('"', "'").replace("|", "/")


def _render_mermaid_tree(desc: GraphDescriptor) -> str:
    """Render a vertical tree (top-down) Mermaid flowchart."""
    lines = ["flowchart TD"]
    for node in desc.nodes:
        color = node.color or YEAR_COLORS.get(node.year) or ACTOR_COLORS.get(node.actor)
        label = _escape(node.label)
        shape = "((" if node.kind in ("center", "year") else "["
        close = "))" if node.kind in ("center", "year") else "]"
        lines.append(f"    {node.id}{shape}{label}{close}")
        if color:
            lines.append(f"    style {node.id} fill:{color},color:#fff")
    for edge in desc.edges:
        if edge.label:
            lines.append(
                f"    {edge.source} -->|{_escape(edge.label)}| {edge.target}"
            )
        else:
            lines.append(f"    {edge.source} --> {edge.target}")
    return "\n".join(lines) + "\n"


def _render_mermaid_circular(desc: GraphDescriptor) -> str:
    """Render a circular / radial-approximation Mermaid flowchart.

    Uses a center node flanked by year-quadrant subgraphs plus classDef color
    rings. The v2 variant adds an outer foundation ring, an outward growth
    arrow, and concentric ripple nodes.
    """
    lines = ["flowchart TD"]
    # classDef color rings per year + foundation/growth emphasis.
    for year, color in YEAR_COLORS.items():
        lines.append(f"    classDef y{year} fill:{color},color:#fff,stroke:#333")
    lines.append("    classDef foundation fill:#0b3d2e,color:#fff,stroke:#1f9d55")
    lines.append("    classDef growth fill:#17becf,color:#000,stroke:#0b6e8f")
    lines.append("    classDef ripple fill:#e377c2,color:#000,stroke:#999")
    for node in desc.nodes:
        label = _escape(node.label)
        if node.kind == "center":
            shape = "(("
            close = "))"
        elif node.kind in ("ring", "ripple"):
            shape = "(("
            close = "))"
        elif node.kind == "growth":
            shape = "(["
            close = "])"
        else:
            shape = "["
            close = "]"
        lines.append(f"    {node.id}{shape}{label}{close}")
    for edge in desc.edges:
        if edge.kind == "growth":
            lines.append(f"    {edge.source} ==>|{_escape(edge.label or 'growth')}| {edge.target}")
        elif edge.label:
            lines.append(f"    {edge.source} -->|{_escape(edge.label)}| {edge.target}")
        else:
            lines.append(f"    {edge.source} --> {edge.target}")
    # Apply year classes.
    for node in desc.nodes:
        if node.year:
            lines.append(f"    class {node.id} y{node.year}")
        elif node.kind == "center":
            lines.append(f"    class {node.id} foundation")
        elif node.kind == "growth":
            lines.append(f"    class {node.id} growth")
        elif node.kind in ("ring", "ripple"):
            lines.append(f"    class {node.id} ripple")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------


def build_ecosystem_tree(conn, period_start=None, period_end=None) -> GraphDescriptor:
    """Vertical tree of the ecosystem journey 2021->2024.

    Roots are the years in range; children are funding rounds and DAO proposals
    observed in each year, colored by actor.
    """
    years = list(FOUNDATION_YEARS)
    if period_start:
        years = [y for y in years if y >= int(str(period_start)[:4])]
    if period_end:
        years = [y for y in years if y <= int(str(period_end)[:4])]

    desc = GraphDescriptor(
        name="ecosystem_tree",
        layout="tree",
        title="Kokonut Ecosystem Journey 2021-2024",
    )
    nodes: dict = {}
    for year in years:
        yid = f"Y{year}"
        nodes[yid] = GraphNode(id=yid, label=f"{year}", kind="year", year=year)
        desc.nodes.append(nodes[yid])

    cur = conn.cursor(cursor_factory=__import__("psycopg2").extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT id, round_name, actor_type, period_start, raised_amount, currency
            FROM funding_round
            WHERE (%s IS NULL OR period_start >= %s)
              AND (%s IS NULL OR period_start <= %s)
            ORDER BY period_start, actor_type
            """,
            (period_start, period_start, period_end, period_end),
        )
        for row in cur.fetchall():
            year = int(str(row["period_start"])[:4])
            yid = f"Y{year}"
            if yid not in nodes:
                continue
            rid = f"R{row['id'].hex[:8]}"
            node = GraphNode(
                id=rid,
                label=f"{row['round_name']} ({row['actor_type']})",
                kind="round",
                parent=yid,
                year=year,
                actor=row["actor_type"],
                color=ACTOR_COLORS.get(row["actor_type"]),
                meta={
                    "raised_amount": float(row["raised_amount"] or 0),
                    "currency": row["currency"],
                },
            )
            desc.nodes.append(node)
            desc.edges.append(GraphEdge(source=yid, target=rid, label="funded"))

        cur.execute(
            """
            SELECT id, proposal_code, title, proposal_type, lifecycle_stage,
                   EXTRACT(YEAR FROM created_at) AS year
            FROM dao_proposal
            WHERE (%s IS NULL OR created_at >= %s)
              AND (%s IS NULL OR created_at <= %s)
            ORDER BY created_at
            """,
            (period_start, period_start, period_end, period_end),
        )
        for row in cur.fetchall():
            year = int(row["year"])
            yid = f"Y{year}"
            if yid not in nodes:
                continue
            pid = f"P{row['id'].hex[:8]}"
            node = GraphNode(
                id=pid,
                label=f"{row['proposal_code']}: {row['proposal_type']}",
                kind="proposal",
                parent=yid,
                year=year,
                status=row["lifecycle_stage"],
                meta={"title": row["title"], "stage": row["lifecycle_stage"]},
            )
            desc.nodes.append(node)
            desc.edges.append(GraphEdge(source=yid, target=pid, label="proposed"))
    finally:
        cur.close()
    return desc


def build_farm_phases(conn, location_id: str) -> GraphDescriptor:
    """Vertical tree of a Kokonut Farm's development phases.

    Roots at the location; children are farm zones ordered by a conventional
    build sequence (nursery -> syntropic_plot -> biofactory -> ...); leaves
    carry the zone status.
    """
    desc = GraphDescriptor(
        name="farm_phases",
        layout="tree",
        title=f"Kokonut Farm Development Phases ({location_id})",
    )
    cur = conn.cursor(cursor_factory=__import__("psycopg2").extras.RealDictCursor)
    try:
        cur.execute(
            "SELECT name FROM location WHERE id = %s", (location_id,)
        )
        loc = cur.fetchone()
        loc_label = loc["name"] if loc else f"Location {location_id}"
        root = GraphNode(id="LOC", label=loc_label, kind="center")
        desc.nodes.append(root)

        # Conventional build sequence for zone coloring/ordering.
        build_order = [
            "nursery",
            "syntropic_plot",
            "agroforestry",
            "crop_bed",
            "biofactory",
            "poultry",
            "education",
        ]
        cur.execute(
            """
            SELECT id, name, zone_type, status
            FROM farm_zone
            WHERE location_id = %s
            ORDER BY array_position(%s::text[], zone_type), name
            """,
            (location_id, build_order),
        )
        for row in cur.fetchall():
            zid = f"Z{row['id'].hex[:8]}"
            node = GraphNode(
                id=zid,
                label=f"{row['name']} ({row['zone_type']})",
                kind="zone",
                parent="LOC",
                status=row["status"],
            )
            desc.nodes.append(node)
            desc.edges.append(
                GraphEdge(source="LOC", target=zid, label=row["zone_type"])
            )
    finally:
        cur.close()
    return desc


def build_seeds_crop_timelines(
    conn, location_id: str, period_start=None, period_end=None
) -> GraphDescriptor:
    """Vertical tree of short-cycle crop timelines at a location (e.g. Seeds).

    One subtree per crop_cycle: planting -> (flowering) -> harvest, labeled
    with dates and status.
    """
    desc = GraphDescriptor(
        name="seeds_crop_timelines",
        layout="tree",
        title=f"Kokonut Seeds Short-Cycle Crop Timelines ({location_id})",
    )
    cur = conn.cursor(cursor_factory=__import__("psycopg2").extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT cc.id, cc.cycle_name, c.name AS crop_name, cc.planting_date,
                   cc.expected_harvest_date, cc.actual_harvest_date, cc.status
            FROM crop_cycle cc
            LEFT JOIN crop c ON c.id = cc.crop_id
            WHERE cc.location_id = %s
              AND (%s IS NULL OR cc.planting_date >= %s)
              AND (%s IS NULL OR COALESCE(cc.actual_harvest_date, cc.expected_harvest_date) <= %s)
            ORDER BY cc.planting_date
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
        for row in cur.fetchall():
            croot = f"C{row['id'].hex[:8]}"
            label = f"{row['crop_name'] or 'crop'}: {row['cycle_name'] or 'cycle'}"
            desc.nodes.append(
                GraphNode(id=croot, label=label, kind="crop", parent=None,
                          status=row["status"])
            )
            plant = f"{croot}P"
            desc.nodes.append(
                GraphNode(
                    id=plant,
                    label=f"Planting {row['planting_date']}",
                    kind="stage",
                    parent=croot,
                )
            )
            desc.edges.append(GraphEdge(source=croot, target=plant, label="start"))
            harvest = row["actual_harvest_date"] or row["expected_harvest_date"]
            hnode = f"{croot}H"
            desc.nodes.append(
                GraphNode(
                    id=hnode,
                    label=f"Harvest {harvest}",
                    kind="stage",
                    parent=croot,
                    status=row["status"],
                )
            )
            desc.edges.append(GraphEdge(source=plant, target=hnode, label="grow"))
    finally:
        cur.close()
    return desc


def build_ikigai_circular(
    conn, period_start=None, period_end=None, version: int = 1
) -> GraphDescriptor:
    """Circular Ikigai-inspired timeline (v1 or v2).

    Kokonut at the center; one quadrant per year 2021-2024 with that year's
    funding rounds/actors as children, color-coded by year. v2 adds an outer
    foundation ring, an outward growth arrow, and concentric ripples.
    """
    years = list(FOUNDATION_YEARS)
    if period_start:
        years = [y for y in years if y >= int(str(period_start)[:4])]
    if period_end:
        years = [y for y in years if y <= int(str(period_end)[:4])]

    desc = GraphDescriptor(
        name=f"ikigai_v{version}",
        layout="circular",
        title="Kokonut Framework Evolution (Ikigai-inspired)",
    )
    center = GraphNode(
        id="CENTER",
        label="Kokonut Framework / Foundation Phase 2021-2024",
        kind="center",
    )
    desc.nodes.append(center)

    cur = conn.cursor(cursor_factory=__import__("psycopg2").extras.RealDictCursor)
    try:
        for year in years:
            yid = f"Y{year}"
            desc.nodes.append(
                GraphNode(id=yid, label=f"{year}", kind="year", year=year)
            )
            desc.edges.append(GraphEdge(source="CENTER", target=yid, label="phase"))
            cur.execute(
                """
                SELECT id, round_name, actor_type, raised_amount, currency
                FROM funding_round
                WHERE EXTRACT(YEAR FROM period_start) = %s
                ORDER BY actor_type
                """,
                (year,),
            )
            for row in cur.fetchall():
                rid = f"R{row['id'].hex[:8]}"
                desc.nodes.append(
                    GraphNode(
                        id=rid,
                        label=f"{row['round_name']} ({row['actor_type']})",
                        kind="round",
                        parent=yid,
                        year=year,
                        actor=row["actor_type"],
                        color=ACTOR_COLORS.get(row["actor_type"]),
                        meta={
                            "raised_amount": float(row["raised_amount"] or 0),
                            "currency": row["currency"],
                        },
                    )
                )
                desc.edges.append(GraphEdge(source=yid, target=rid, label="funded"))
    finally:
        cur.close()

    if version >= 2:
        # Outer foundation-completion ring.
        desc.nodes.append(
            GraphNode(
                id="RING",
                label="Foundation Phase Complete (2021-2024)",
                kind="ring",
            )
        )
        desc.edges.append(GraphEdge(source="CENTER", target="RING", kind="ripple",
                                     label="completion"))
        # Outward growth arrow -> readiness for growth.
        desc.nodes.append(
            GraphNode(id="GROWTH", label="Ready for Growth", kind="growth")
        )
        desc.edges.append(GraphEdge(source="RING", target="GROWTH", kind="growth",
                                     label="next phase"))
        # Concentric ripples of growth.
        for i in range(1, 3):
            desc.nodes.append(
                GraphNode(id=f"RIPPLE{i}", label=f"Ripple {i}", kind="ripple")
            )
            desc.edges.append(
                GraphEdge(source="GROWTH", target=f"RIPPLE{i}", kind="ripple",
                          label=f"ripple {i}")
            )
    return desc


def build_all(conn, location_id=None, period_start=None, period_end=None) -> list:
    """Build every graph concept and return a list of GraphDescriptors.

    ``farm_phases`` and ``seeds_crop_timelines`` require a location; when
    ``location_id`` is a list, they are iterated per-location.
    """
    descriptors: list = []
    descriptors.append(build_ecosystem_tree(conn, period_start, period_end))
    descriptors.append(build_ikigai_circular(conn, period_start, period_end, version=1))
    descriptors.append(build_ikigai_circular(conn, period_start, period_end, version=2))

    location_ids = location_id or []
    if isinstance(location_id, str):
        if location_id.lower() == "all":
            cur = conn.cursor(cursor_factory=__import__("psycopg2").extras.RealDictCursor)
            try:
                cur.execute("SELECT id FROM location ORDER BY name")
                location_ids = [str(r["id"]) for r in cur.fetchall()]
            finally:
                cur.close()
        else:
            location_ids = [lid.strip() for lid in location_id.split(",") if lid.strip()]

    for lid in location_ids:
        descriptors.append(build_farm_phases(conn, lid))
        descriptors.append(
            build_seeds_crop_timelines(conn, lid, period_start, period_end)
        )
    return descriptors
