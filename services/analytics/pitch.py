"""Pitch & Presentation service — audience-segmented pitch generation.

Pulls live data from the Kokonut Intelligence platform to produce
structured pitch decks for different audiences: funders, operators,
developers, ReFi/Web3, impact/grant reviewers, and a generic elevator pitch.

Output formats: Markdown, HTML, PDF-ready, CLI stdout.
"""

from __future__ import annotations

import argparse
import json
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.ingestion.base import get_db

AUDIENCES = ("funders", "operators", "developers", "refi", "impact", "elevator")


# ──────────────────────────────────────────────
# Template CRUD
# ──────────────────────────────────────────────

def get_templates(conn) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, audience, hook, cta_label, cta_url, created_at, updated_at "
            "FROM pitch_template ORDER BY audience"
        )
        return [dict(r) for r in cur.fetchall()]


def get_template(conn, audience: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM pitch_template WHERE audience = %s", (audience,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


def create_template(
    conn, audience: str, hook: str, problem: str, solution: str,
    proof_headline: str, cta_label: str, cta_url: str,
    sections: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    if audience not in AUDIENCES:
        raise ValueError(f"audience must be one of {AUDIENCES}")
    sections_json = json.dumps(sections or [])
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO pitch_template (audience, hook, problem, solution,
                proof_headline, cta_label, cta_url, sections)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (audience) DO UPDATE SET
                hook = EXCLUDED.hook,
                problem = EXCLUDED.problem,
                solution = EXCLUDED.solution,
                proof_headline = EXCLUDED.proof_headline,
                cta_label = EXCLUDED.cta_label,
                cta_url = EXCLUDED.cta_url,
                sections = EXCLUDED.sections,
                updated_at = NOW()
            RETURNING id, audience, hook, cta_label, cta_url, created_at, updated_at
            """,
            (audience, hook, problem, solution, proof_headline,
             cta_label, cta_url, sections_json),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


# ──────────────────────────────────────────────
# Evidence gathering (live platform data)
# ──────────────────────────────────────────────

def gather_evidence(conn, location_id: str) -> Dict[str, Any]:
    evidence: Dict[str, Any] = {}
    evidence["farm"] = _query_farm(conn, location_id)
    evidence["crisp"] = _query_crisp(conn, location_id)
    evidence["revenue"] = _query_revenue(conn, location_id)
    evidence["harvests"] = _query_harvests(conn, location_id)
    evidence["impact_claims"] = _query_impact_claims(conn, location_id)
    evidence["attestations"] = _query_attestations(conn, location_id)
    evidence["feedback"] = _query_feedback(conn, location_id)
    evidence["carbon"] = _query_carbon(conn, location_id)
    evidence["biodiversity"] = _query_biodiversity(conn, location_id)
    return evidence


def _query_farm(conn, location_id: str) -> Dict[str, Any]:
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT location_id, location_name, country, region, "
                "total_area_ha, status "
                "FROM v_public_farm_summary WHERE location_id = %s",
                (location_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else {}
    except psycopg2.Error:
        conn.rollback()
        return {}


def _query_crisp(conn, location_id: str) -> Dict[str, Any]:
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT composite_score, rating, carbon_yield_score, "
                "climate_score, policy_score, financial_score, "
                "implementation_score, evidence_maturity_level "
                "FROM v_crisp_composite_rating "
                "WHERE location_id = %s "
                "ORDER BY score_computed_at DESC LIMIT 1",
                (location_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else {}
    except psycopg2.Error:
        conn.rollback()
        return {}


def _query_revenue(conn, location_id: str) -> Dict[str, Any]:
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT stream_name, stream_category, gross_revenue, "
                "direct_costs, net_contribution "
                "FROM v_public_revenue_streams "
                "WHERE location_id = %s",
                (location_id,),
            )
            streams = [dict(r) for r in cur.fetchall()]
            total_gross = sum(
                float(s.get("gross_revenue") or 0) for s in streams
            )
            total_net = sum(
                float(s.get("net_contribution") or 0) for s in streams
            )
            return {
                "streams": streams,
                "total_gross": total_gross,
                "total_net": total_net,
                "stream_count": len(streams),
            }
    except psycopg2.Error:
        conn.rollback()
        return {"streams": [], "total_gross": 0, "total_net": 0, "stream_count": 0}


def _query_harvests(conn, location_id: str) -> List[Dict[str, Any]]:
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, crop_name, harvest_date, quantity, unit "
                "FROM harvest_event "
                "WHERE location_id = %s "
                "ORDER BY harvest_date DESC LIMIT 10",
                (location_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    except psycopg2.Error:
        conn.rollback()
        return []


def _query_impact_claims(conn, location_id: str) -> List[Dict[str, Any]]:
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT claim_type, claim_status, impact_dimension, "
                "evidence_maturity "
                "FROM v_public_impact_claim_summary "
                "WHERE location_id = %s",
                (location_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    except psycopg2.Error:
        conn.rollback()
        return []


def _query_attestations(conn, location_id: str) -> List[Dict[str, Any]]:
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT schema_name, chain, status, created_at "
                "FROM v_public_attestation_summary "
                "WHERE location_id = %s",
                (location_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    except psycopg2.Error:
        conn.rollback()
        return []


def _query_feedback(conn, location_id: str) -> Dict[str, Any]:
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT feedback_type, COUNT(*) as count, "
                "AVG(CASE WHEN sentiment = 'positive' THEN 1 "
                "WHEN sentiment = 'neutral' THEN 0.5 "
                "WHEN sentiment = 'negative' THEN 0 END) as avg_sentiment "
                "FROM v_public_stakeholder_feedback_summary "
                "WHERE location_id = %s "
                "GROUP BY feedback_type",
                (location_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            total = sum(r.get("count", 0) for r in rows)
            return {"by_type": rows, "total": total}
    except psycopg2.Error:
        conn.rollback()
        return {"by_type": [], "total": 0}


def _query_carbon(conn, location_id: str) -> Dict[str, Any]:
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT SUM(quantity) as total_credits, "
                "SUM(retired_quantity) as retired "
                "FROM v_public_carbon_credit_inventory "
                "WHERE location_id = %s",
                (location_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else {}
    except psycopg2.Error:
        conn.rollback()
        return {}


def _query_biodiversity(conn, location_id: str) -> Dict[str, Any]:
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT species_name) as species_count, "
                "COUNT(*) as observation_count "
                "FROM species_observation "
                "WHERE location_id = %s",
                (location_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else {}
    except psycopg2.Error:
        conn.rollback()
        return {}


# ──────────────────────────────────────────────
# Pitch generation
# ──────────────────────────────────────────────

def generate_pitch(
    conn, location_id: str, audience: str = "elevator",
) -> Dict[str, Any]:
    template = get_template(conn, audience)
    if not template:
        raise ValueError(f"no pitch template for audience: {audience}")
    evidence = gather_evidence(conn, location_id)
    farm_name = evidence["farm"].get("location_name", "the farm")
    crisp = evidence["crisp"]
    revenue = evidence["revenue"]
    harvests = evidence["harvests"]
    attestations = evidence["attestations"]
    claims = evidence["impact_claims"]
    feedback = evidence["feedback"]
    carbon = evidence["carbon"]
    bio = evidence["biodiversity"]
    metrics = {}
    if crisp:
        metrics["crisp_rating"] = crisp.get("rating", "N/A")
        metrics["crisp_score"] = crisp.get("composite_score")
    if revenue.get("total_gross"):
        metrics["revenue_gross"] = revenue["total_gross"]
        metrics["revenue_net"] = revenue.get("total_net", 0)
        metrics["revenue_streams"] = revenue.get("stream_count", 0)
    if harvests:
        metrics["harvest_count"] = len(harvests)
        metrics["latest_crop"] = harvests[0].get("crop_name", "N/A")
    if attestations:
        metrics["attestation_count"] = len(attestations)
    if claims:
        metrics["impact_claim_count"] = len(claims)
    if feedback.get("total"):
        metrics["feedback_count"] = feedback["total"]
    area = evidence["farm"].get("total_area_ha")
    if area:
        metrics["area_ha"] = float(area)
    if carbon:
        metrics["carbon_credits"] = carbon.get("total_credits")
        metrics["carbon_retired"] = carbon.get("retired")
    if bio:
        metrics["species_count"] = bio.get("species_count", 0)
        metrics["observations"] = bio.get("observation_count", 0)
    sections = template.get("sections") or []
    return {
        "audience": audience,
        "location_id": location_id,
        "farm_name": farm_name,
        "hook": template["hook"],
        "problem": template["problem"],
        "solution": template["solution"],
        "proof_headline": template["proof_headline"],
        "cta_label": template["cta_label"],
        "cta_url": template["cta_url"],
        "sections": sections,
        "metrics": metrics,
        "evidence": evidence,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────
# Renderers
# ──────────────────────────────────────────────

def render_markdown(pitch: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# Kokonut Network — {pitch['audience'].title()} Pitch\n")
    lines.append(f"**{pitch['farm_name']}** | Generated {pitch['generated_at'][:10]}\n")
    lines.append(f"## {pitch['hook']}\n")
    lines.append("## The Problem\n")
    lines.append(f"{pitch['problem']}\n")
    lines.append("## The Solution\n")
    lines.append(f"{pitch['solution']}\n")
    lines.append("## Live Proof\n")
    lines.append(f"{pitch['proof_headline']}\n")
    metrics = pitch.get("metrics", {})
    if metrics:
        lines.append("### Key Metrics\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        if "crisp_rating" in metrics:
            lines.append(
                f"| CRISP Rating | {metrics['crisp_rating']}"
                f" ({metrics.get('crisp_score', 'N/A')}/100 risk) |"
            )
        if "revenue_gross" in metrics:
            lines.append(
                f"| Revenue | ${metrics['revenue_gross']:,.0f} gross"
                f" / ${metrics.get('revenue_net', 0):,.0f} net |"
            )
        if "harvest_count" in metrics:
            lines.append(
                f"| Harvests | {metrics['harvest_count']} recorded"
                f" (latest: {metrics.get('latest_crop', 'N/A')}) |"
            )
        if "attestation_count" in metrics:
            lines.append(
                f"| Attestations | {metrics['attestation_count']} on-chain |"
            )
        if "impact_claim_count" in metrics:
            lines.append(
                f"| Impact Claims | {metrics['impact_claim_count']} verified |"
            )
        if "feedback_count" in metrics:
            lines.append(
                f"| Stakeholder Feedback | {metrics['feedback_count']} signals |"
            )
        if "area_ha" in metrics:
            lines.append(f"| Farm Area | {metrics['area_ha']:.2f} ha |")
        if "carbon_credits" in metrics:
            lines.append(
                f"| Carbon Credits | {metrics.get('carbon_credits', 0)}"
                f" ({metrics.get('carbon_retired', 0)} retired) |"
            )
        if "species_count" in metrics:
            lines.append(
                f"| Biodiversity | {metrics['species_count']} species,"
                f" {metrics.get('observations', 0)} observations |"
            )
        lines.append("")
    for section in pitch.get("sections", []):
        title = section.get("title", "")
        content = section.get("content", "")
        if title and content:
            lines.append(f"## {title}\n")
            lines.append(f"{content}\n")
    lines.append("---\n")
    lines.append(f"**{pitch['cta_label']}**\n")
    lines.append(f"{pitch['cta_url']}\n")
    return "\n".join(lines)


def render_html(pitch: Dict[str, Any]) -> str:
    metrics = pitch.get("metrics", {})
    metric_cards = ""
    if metrics:
        cards = []
        if "crisp_rating" in metrics:
            cards.append(
                _metric_card("CRISP Rating",
                             f"{metrics['crisp_rating']} ({metrics.get('crisp_score', 'N/A')}/100)")
            )
        if "revenue_gross" in metrics:
            cards.append(
                _metric_card("Revenue",
                             f"${metrics['revenue_gross']:,.0f}")
            )
        if "harvest_count" in metrics:
            cards.append(
                _metric_card("Harvests", str(metrics["harvest_count"]))
            )
        if "attestation_count" in metrics:
            cards.append(
                _metric_card("Attestations", str(metrics["attestation_count"]))
            )
        if "impact_claim_count" in metrics:
            cards.append(
                _metric_card("Impact Claims", str(metrics["impact_claim_count"]))
            )
        if "area_ha" in metrics:
            cards.append(
                _metric_card("Farm Area", f"{metrics['area_ha']:.2f} ha")
            )
        if "carbon_credits" in metrics:
            cards.append(
                _metric_card("Carbon Credits", str(metrics.get("carbon_credits", 0)))
            )
        if "species_count" in metrics:
            cards.append(
                _metric_card("Biodiversity",
                             f"{metrics['species_count']} species")
            )
        metric_cards = (
            '<div class="metrics-grid">' + "\n".join(cards) + "</div>"
        )
    sections_html = ""
    for section in pitch.get("sections", []):
        title = section.get("title", "")
        content = section.get("content", "")
        if title and content:
            sections_html += f'<section class="pitch-section">\n'
            sections_html += f'<h2>{title}</h2>\n'
            sections_html += f'<p>{content}</p>\n'
            sections_html += f'</section>\n'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kokonut Network — {pitch['audience'].title()} Pitch</title>
<style>
  :root {{ --green: #009F4D; --dark: #1a1a1a; --gray: #6b7280; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         color: var(--dark); line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 2rem; }}
  h1 {{ font-size: 2rem; margin-bottom: 0.5rem; color: var(--green); }}
  h2 {{ font-size: 1.4rem; margin: 2rem 0 0.75rem; color: var(--dark); border-bottom: 2px solid var(--green);
        padding-bottom: 0.3rem; }}
  .subtitle {{ color: var(--gray); font-size: 0.9rem; margin-bottom: 1.5rem; }}
  .hook {{ font-size: 1.15rem; font-weight: 600; margin: 1.5rem 0; color: var(--dark); }}
  p {{ margin: 0.75rem 0; color: #374151; }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                   gap: 1px; background: #e5e7eb; border: 1px solid #e5e7eb; border-radius: 12px;
                   overflow: hidden; margin: 1.5rem 0; }}
  .metric-card {{ background: white; padding: 1rem; text-align: center; }}
  .metric-value {{ font-size: 1.4rem; font-weight: 700; color: var(--green); line-height: 1; }}
  .metric-label {{ font-size: 0.72rem; color: var(--gray); margin-top: 4px; font-weight: 500; }}
  .cta {{ display: inline-flex; align-items: center; gap: 6px; background: var(--green); color: white;
          padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 14px;
          text-decoration: none; margin-top: 1.5rem; }}
  .pitch-section {{ margin: 1.5rem 0; }}
  .pitch-section p {{ font-size: 0.95rem; }}
  @media print {{
    body {{ padding: 1rem; max-width: 100%; }}
    .cta {{ background: var(--green); color: white; }}
    .metrics-grid {{ break-inside: avoid; }}
    .pitch-section {{ break-inside: avoid; }}
    h2 {{ break-after: avoid; }}
  }}
</style>
</head>
<body>
<h1>Kokonut Network — {pitch['audience'].title()} Pitch</h1>
<div class="subtitle">{pitch['farm_name']} | Generated {pitch['generated_at'][:10]}</div>
<div class="hook">{pitch['hook']}</div>
<h2>The Problem</h2>
<p>{pitch['problem']}</p>
<h2>The Solution</h2>
<p>{pitch['solution']}</p>
<h2>Live Proof</h2>
<p>{pitch['proof_headline']}</p>
{metric_cards}
{sections_html}
<a href="{pitch['cta_url']}" class="cta">{pitch['cta_label']}</a>
</body>
</html>"""


def _metric_card(value: str, label: str) -> str:
    return (
        f'<div class="metric-card">'
        f'<div class="metric-value">{value}</div>'
        f'<div class="metric-label">{label}</div>'
        f'</div>'
    )


def render_pdf_ready(pitch: Dict[str, Any]) -> str:
    html = render_html(pitch)
    print_css = """
@media print {
  body { padding: 0.5in; max-width: 100%; font-size: 11pt; }
  h1 { font-size: 20pt; page-break-after: avoid; }
  h2 { font-size: 14pt; page-break-after: avoid; }
  .metrics-grid { page-break-inside: avoid; }
  .pitch-section { page-break-inside: avoid; }
  .cta { background: #009F4D !important; color: white !important; -webkit-print-color-adjust: exact; }
  .metric-card { -webkit-print-color-adjust: exact; }
}
"""
    return html.replace("</style>", print_css + "\n</style>")


def render_cli(pitch: Dict[str, Any]) -> str:
    lines = []
    w = min(78, 80)
    lines.append("=" * w)
    lines.append(f"  KOKONUT NETWORK — {pitch['audience'].upper()} PITCH")
    lines.append(f"  {pitch['farm_name']}")
    lines.append("=" * w)
    lines.append("")
    lines.append(f"  {pitch['hook']}")
    lines.append("")
    lines.append("-" * w)
    lines.append("  THE PROBLEM")
    lines.append("-" * w)
    for para in pitch["problem"].split("\n\n"):
        lines.append(textwrap.fill(para.strip(), width=w - 2, initial_indent="  ",
                                    subsequent_indent="  "))
        lines.append("")
    lines.append("-" * w)
    lines.append("  THE SOLUTION")
    lines.append("-" * w)
    for para in pitch["solution"].split("\n\n"):
        lines.append(textwrap.fill(para.strip(), width=w - 2, initial_indent="  ",
                                    subsequent_indent="  "))
        lines.append("")
    lines.append("-" * w)
    lines.append("  LIVE PROOF")
    lines.append("-" * w)
    lines.append(textwrap.fill(pitch["proof_headline"], width=w - 2,
                                initial_indent="  ", subsequent_indent="  "))
    lines.append("")
    metrics = pitch.get("metrics", {})
    if metrics:
        lines.append("  Key Metrics:")
        lines.append("  " + "." * (w - 4))
        fmt = "  {:<24} {}"
        if "crisp_rating" in metrics:
            lines.append(fmt.format("CRISP Rating",
                         f"{metrics['crisp_rating']} ({metrics.get('crisp_score', 'N/A')}/100)"))
        if "revenue_gross" in metrics:
            lines.append(fmt.format("Revenue",
                         f"${metrics['revenue_gross']:,.0f} gross"))
        if "harvest_count" in metrics:
            lines.append(fmt.format("Harvests",
                         f"{metrics['harvest_count']} recorded"))
        if "attestation_count" in metrics:
            lines.append(fmt.format("Attestations",
                         f"{metrics['attestation_count']} on-chain"))
        if "impact_claim_count" in metrics:
            lines.append(fmt.format("Impact Claims",
                         str(metrics["impact_claim_count"])))
        if "area_ha" in metrics:
            lines.append(fmt.format("Farm Area",
                         f"{metrics['area_ha']:.2f} ha"))
        if "carbon_credits" in metrics:
            lines.append(fmt.format("Carbon Credits",
                         str(metrics.get("carbon_credits", 0))))
        if "species_count" in metrics:
            lines.append(fmt.format("Biodiversity",
                         f"{metrics['species_count']} species"))
        lines.append("")
    for section in pitch.get("sections", []):
        title = section.get("title", "")
        content = section.get("content", "")
        if title and content:
            lines.append(f"  {title.upper()}")
            lines.append("  " + "-" * (w - 4))
            for para in content.split("\n\n"):
                lines.append(textwrap.fill(para.strip(), width=w - 2,
                                            initial_indent="  ",
                                            subsequent_indent="  "))
                lines.append("")
    lines.append("=" * w)
    lines.append(f"  {pitch['cta_label']}")
    lines.append(f"  {pitch['cta_url']}")
    lines.append("=" * w)
    return "\n".join(lines)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def _cmd(args) -> None:
    conn = get_db()
    try:
        if args.command == "generate":
            audience = args.audience or "elevator"
            pitch = generate_pitch(conn, args.location_id, audience)
            fmt = args.format or "cli"
            if fmt == "markdown":
                print(render_markdown(pitch))
            elif fmt == "html":
                print(render_html(pitch))
            elif fmt == "pdf":
                print(render_pdf_ready(pitch))
            else:
                print(render_cli(pitch))
        elif args.command == "elevator":
            pitch = generate_pitch(conn, args.location_id, "elevator")
            print(render_cli(pitch))
        elif args.command == "evidence":
            evidence = gather_evidence(conn, args.location_id)
            print(json.dumps(evidence, indent=2, default=str))
        elif args.command == "templates":
            _cmd_templates(args, conn)
        else:
            print("{}")
    finally:
        conn.close()


def _cmd_templates(args, conn) -> None:
    if args.templates_command == "list":
        out = get_templates(conn)
        print(json.dumps(out, indent=2, default=str))
    elif args.templates_command == "get":
        out = get_template(conn, args.audience)
        print(json.dumps(out, indent=2, default=str))
    elif args.templates_command == "create":
        sections = None
        if args.sections:
            sections = json.loads(args.sections)
        out = create_template(
            conn, args.audience, args.hook, args.problem,
            args.solution, args.proof, args.cta_label,
            args.cta_url, sections=sections,
        )
        print(json.dumps(out, indent=2, default=str))


def main() -> None:
    p = argparse.ArgumentParser(
        description="Pitch & Presentation — audience-segmented pitch generation"
    )
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--location-id", required=True)
    g.add_argument("--audience", default="elevator", choices=list(AUDIENCES))
    g.add_argument("--format", default="cli",
                   choices=["cli", "markdown", "html", "pdf"])

    e = sub.add_parser("elevator")
    e.add_argument("--location-id", required=True)

    ev = sub.add_parser("evidence")
    ev.add_argument("--location-id", required=True)

    t = sub.add_parser("templates")
    ts = t.add_subparsers(dest="templates_command", required=True)
    ts.add_parser("list")
    tg = ts.add_parser("get")
    tg.add_argument("--audience", required=True, choices=list(AUDIENCES))
    tc = ts.add_parser("create")
    tc.add_argument("--audience", required=True, choices=list(AUDIENCES))
    tc.add_argument("--hook", required=True)
    tc.add_argument("--problem", required=True)
    tc.add_argument("--solution", required=True)
    tc.add_argument("--proof", required=True)
    tc.add_argument("--cta-label", required=True)
    tc.add_argument("--cta-url", required=True)
    tc.add_argument("--sections", default=None,
                    help='JSON array of {"title": ..., "content": ...} objects')

    args = p.parse_args()
    _cmd(args)


if __name__ == "__main__":
    main()
