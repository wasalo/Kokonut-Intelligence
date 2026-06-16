"""
Partner Sponsorship — Dimension 9

Scores partner ROI, tracks sponsorship pipeline value.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get partner sales performance
    cur.execute("""
        SELECT
            p.name as partner_name,
            p.partner_type,
            SUM(se.net_amount) as net_revenue,
            COUNT(se.id) as sales_count,
            SUM(se.return_amount) as returns,
            SUM(se.discount_amount) as discounts
        FROM sales_event se
        LEFT JOIN partner p ON se.partner_id = p.id
        WHERE se.location_id = %s AND se.partner_id IS NOT NULL
        GROUP BY p.name, p.partner_type
    """, (location_id,))
    partner_sales = [dict(r) for r in cur.fetchall()]

    # Get partner expenses (vendor relationships)
    cur.execute("""
        SELECT
            p.name as partner_name,
            SUM(ee.amount) as total_spend
        FROM expense_event ee
        LEFT JOIN partner p ON ee.vendor_id = p.id
        WHERE ee.location_id = %s AND ee.vendor_id IS NOT NULL
        GROUP BY p.name
    """, (location_id,))
    partner_expenses = [dict(r) for r in cur.fetchall()]

    # Get capital sources by partner
    cur.execute("""
        SELECT source_type, SUM(amount) as total_amount
        FROM capital_source
        WHERE location_id = %s
        GROUP BY source_type
    """, (location_id,))
    capital = {r["source_type"]: float(r["total_amount"]) for r in cur.fetchall()}

    cur.close()

    # Calculate partner ROI
    total_partner_revenue = sum(float(p["net_revenue"] or 0) for p in partner_sales)
    total_partner_spend = sum(float(p["total_spend"] or 0) for p in partner_expenses)
    unique_partners = len(set(p["partner_name"] for p in partner_sales))

    # Score: more partners = higher score
    score = min(100, unique_partners * 15 + (20 if total_partner_revenue > 0 else 0))

    # Impact: sponsorship potential from new partners
    avg_partner_value = total_partner_revenue / max(unique_partners, 1)
    new_partners_potential = int(get_config(conn, 'new_partners_potential'))
    impact = avg_partner_value * new_partners_potential

    details = {
        "partner_revenue": round(total_partner_revenue, 2),
        "partner_spend": round(total_partner_spend, 2),
        "unique_partners": unique_partners,
        "capital_sources": capital,
        "avg_partner_value": round(avg_partner_value, 2),
        "partner_sales": {p["partner_name"]: round(float(p["net_revenue"] or 0), 2) for p in partner_sales},
        "partner_expenses": {p["partner_name"]: round(float(p["total_spend"] or 0), 2) for p in partner_expenses},
    }

    return OpportunityDimension(
        dimension_id="partner_sponsorship",
        dimension_name="Partner Sponsorship",
        score=round(score, 1),
        impact_usd=round(impact, 2),
        confidence="medium",
        current_state=f"{unique_partners} partners, revenue: ${total_partner_revenue:,.0f}, spend: ${total_partner_spend:,.0f}",
        recommendation=f"Add {new_partners_potential} new partners for +${impact:,.0f} revenue",
        data_points=unique_partners,
        details=details,
    )
