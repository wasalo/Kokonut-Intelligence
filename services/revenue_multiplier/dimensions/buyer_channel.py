"""
Buyer/Channel Selection — Dimension 3

Scores buyers by net revenue, payment speed, returns rate.
Identifies best-performing channels.
"""

import psycopg2.extras
from ..models import OpportunityDimension
from ..config import get_config


def analyze(conn, location_id: str) -> OpportunityDimension:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get sales by buyer
    cur.execute("""
        SELECT
            buyer,
            buyer_type,
            partner_id,
            SUM(total_amount) as gross_revenue,
            SUM(return_amount) as returns,
            SUM(discount_amount) as discounts,
            SUM(net_amount) as net_revenue,
            COUNT(*) as sale_count,
            COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_count,
            COUNT(CASE WHEN payment_status = 'overdue' THEN 1 END) as overdue_count
        FROM sales_event
        WHERE location_id = %s
        GROUP BY buyer, buyer_type, partner_id
        ORDER BY net_revenue DESC
    """, (location_id,))
    buyer_data = [dict(r) for r in cur.fetchall()]

    cur.close()

    if not buyer_data:
        return OpportunityDimension(
            dimension_id="buyer_channel_selection", dimension_name="Buyer/Channel Selection",
            score=0, impact_usd=0, confidence="low",
            current_state="No sales data", recommendation="Start tracking sales by buyer",
            data_points=0,
        )

    # Score each buyer
    buyer_scores = {}
    for b in buyer_data:
        buyer = b["buyer"]
        returns_rate = float(b["returns"]) / max(float(b["gross_revenue"]), 1) * 100
        payment_rate = float(b["paid_count"]) / max(b["sale_count"], 1) * 100
        net_per_sale = float(b["net_revenue"]) / max(b["sale_count"], 1)

        # Score: high net, low returns, fast payment
        score = (payment_rate * 0.4) + ((100 - returns_rate) * 0.3) + (min(net_per_sale / 100, 100) * 0.3)
        buyer_scores[buyer] = {
            "score": round(score, 1),
            "net_revenue": float(b["net_revenue"]),
            "returns_rate": round(returns_rate, 2),
            "payment_rate": round(payment_rate, 1),
            "buyer_type": b["buyer_type"],
        }

    # Find best buyer and channel type
    best_buyer = max(buyer_scores, key=lambda k: buyer_scores[k]["score"])
    worst_buyer = min(buyer_scores, key=lambda k: buyer_scores[k]["score"])

    # Channel type analysis
    channel_types = {}
    for b in buyer_data:
        ct = b["buyer_type"] or "unknown"
        if ct not in channel_types:
            channel_types[ct] = {"net": 0, "count": 0}
        channel_types[ct]["net"] += float(b["net_revenue"])
        channel_types[ct]["count"] += 1

    # Score overall
    unique_buyers = len(buyer_scores)
    overall_score = min(100, unique_buyers * 25)  # 4+ buyers = 100

    # Impact: switching from worst to best buyer
    best_net = buyer_scores[best_buyer]["net_revenue"]
    worst_net = buyer_scores[worst_buyer]["net_revenue"]
    buyer_uplift_pct = float(get_config(conn, 'buyer_uplift_pct')) / 100
    impact = max(0, best_net - worst_net) * buyer_uplift_pct

    details = {
        "buyer_scores": buyer_scores,
        "channel_types": channel_types,
        "best_buyer": best_buyer,
        "worst_buyer": worst_buyer,
    }

    return OpportunityDimension(
        dimension_id="buyer_channel_selection",
        dimension_name="Buyer/Channel Selection",
        score=round(overall_score, 1),
        impact_usd=round(impact, 2),
        confidence="medium" if unique_buyers >= 2 else "low",
        current_state=f"{unique_buyers} buyers, best={best_buyer}, channel types: {list(channel_types.keys())}",
        recommendation=f"Grow {best_buyer} relationship, evaluate {worst_buyer} performance",
        data_points=sum(b["sale_count"] for b in buyer_data),
        details=details,
    )
