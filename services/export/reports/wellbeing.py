"""Wellbeing, finance, governance, and capital report generators."""

from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from .common import (
    _serialize_rows,
)


def generate_ebf_scorecard(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe EBF scorecard report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT *
        FROM v_public_ebf_scorecard_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR period_start >= %s::date)
          AND (%s::date IS NULL OR period_end <= %s::date)
        ORDER BY period_end DESC, scorecard_id
        LIMIT 1
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    summary = cur.fetchone()

    pillars = []
    if summary:
        cur.execute(
            """
            SELECT pillar_key, pillar_name, normalized_score, confidence_level,
                   trend_direction, score_evidence_maturity_label,
                   evidence_summary, uncertainty_notes
            FROM v_public_ebf_scorecard
            WHERE scorecard_id = %s
            ORDER BY pillar_key
            """,
            (summary["scorecard_id"],),
        )
        pillars = [dict(r) for r in cur.fetchall()]
    cur.close()

    return {
        "report_type": "ebf_scorecard",
        "location_id": location_id,
        "summary": _serialize_rows([dict(summary)])[0] if summary else None,
        "pillars": _serialize_rows(pillars),
        "limitations": [
            "This report includes only published EBF scorecards that meet public evidence maturity gates.",
            "The carbon pillar is public only when evidence maturity is Level 6.",
            "Use EBF scorecards for evidence-backed learning, not farm ranking.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_holistic_wellbeing(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe holistic well-being report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    location_name = location["name"] if location else None

    cur.execute(
        """
        SELECT practice_name, practice_type, stakeholder_group, language,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_cultural_context_summary
        WHERE location_id = %s
        ORDER BY practice_type, practice_name
        """,
        (location_id,),
    )
    cultural_context = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT metric_key, metric_name, observation_date, stakeholder_group,
               language, score_value, count_value, public_summary,
               evidence_maturity, evidence_maturity_label
        FROM v_public_wellbeing_metric_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR observation_date >= %s::date)
          AND (%s::date IS NULL OR observation_date <= %s::date)
        ORDER BY observation_date DESC, metric_key
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    wellbeing_metrics = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT action_type, action_date, stakeholder_group, feedback_type,
               sentiment, metric_name, metric_proposal_status, decision_status,
               public_summary, evidence_maturity, evidence_maturity_label
        FROM v_public_participatory_governance_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR action_date >= %s::date)
          AND (%s::date IS NULL OR action_date <= %s::date)
        ORDER BY action_date DESC, action_type
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    participatory_actions = [dict(r) for r in cur.fetchall()]
    cur.close()

    languages = sorted({row["language"] for row in wellbeing_metrics + cultural_context if row.get("language")})

    return {
        "report_type": "holistic_wellbeing",
        "location_id": location_id,
        "location_name": location_name,
        "languages": languages,
        "cultural_context": _serialize_rows(cultural_context),
        "wellbeing_metrics": _serialize_rows(wellbeing_metrics),
        "participatory_actions": _serialize_rows(participatory_actions),
        "limitations": [
            "This report includes public-safe summaries and aggregate signals only.",
            "Private stakeholder feedback, household-level observations, and non-consented cultural knowledge remain excluded.",
            "Well-being metrics are learning signals unless externally verified by a named reviewer or methodology.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_financial_sustainability(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe financial sustainability report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_financial_sustainability_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR plan_period_start >= %s::date)
          AND (%s::date IS NULL OR plan_period_end IS NULL OR plan_period_end <= %s::date)
        ORDER BY plan_period_start DESC, plan_name
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    plans = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "financial_sustainability",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "plans": _serialize_rows(plans),
        "limitations": [
            "This report summarizes published financial sustainability plans only.",
            "Projected revenue, NOI, runway, and grant dependency are planning signals, not guarantees.",
            "Private financial terms and draft capital discussions are excluded.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_risk_mitigation(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe risk mitigation report for a location."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_risk_mitigation_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR review_date IS NULL OR review_date >= %s::date)
          AND (%s::date IS NULL OR review_date IS NULL OR review_date <= %s::date)
        ORDER BY next_review_date NULLS LAST, risk_category
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    risks = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "risk_mitigation",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "risks": _serialize_rows(risks),
        "limitations": [
            "This report summarizes published risk register entries only.",
            "Insurance scope may be summarized when full policy documents are private or unavailable for publication.",
            "Residual risk remains a reviewer-assessed signal and should be revisited on the listed cadence.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_scaling_roadmap(conn, location_id: str = None, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe scaling roadmap report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_scaling_roadmap_summary
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR target_date >= %s::date)
              AND (%s::date IS NULL OR target_date <= %s::date)
            ORDER BY target_date, roadmap_name
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_scaling_roadmap_summary
            WHERE (%s::date IS NULL OR target_date >= %s::date)
              AND (%s::date IS NULL OR target_date <= %s::date)
            ORDER BY target_date, roadmap_name
            """,
            (period_start, period_start, period_end, period_end),
        )
    milestones = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "scaling_roadmap",
        "location_id": location_id,
        "milestones": _serialize_rows(milestones),
        "total_capital_required_usd": round(sum(float(row.get("capital_required_usd") or 0) for row in milestones), 2),
        "limitations": [
            "Scaling roadmap entries are milestone plans, not guaranteed expansion commitments.",
            "Capital requirements, partner dependencies, and risk gates should be reviewed before each expansion decision.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_green_paper_publication_status(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate a public-safe Green Paper publication status report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT *
        FROM v_public_green_paper_publication_status
        ORDER BY target_publication_date DESC, version DESC
        """
    )
    reviews = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "green_paper_publication_status",
        "location_id": location_id,
        "reviews": _serialize_rows(reviews),
        "limitations": [
            "Draft or private reviewer notes are not exposed in public publication status reports.",
            "Final publication requires stakeholder approval plus publication hash or CID metadata.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_capital_efficiency(conn, location_id: str, period_start: str = None, period_end: str = None) -> dict:
    """Generate a public-safe capital efficiency and regenerative ROI scenario report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT name FROM location WHERE id = %s", (location_id,))
    location = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM v_public_capital_efficiency_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR period_start >= %s::date)
          AND (%s::date IS NULL OR period_end IS NULL OR period_end <= %s::date)
        ORDER BY period_start DESC, scenario_name
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    scenarios = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT *
        FROM v_public_regenerative_efficiency_summary
        WHERE location_id = %s
          AND (%s::date IS NULL OR observation_date >= %s::date)
          AND (%s::date IS NULL OR observation_date <= %s::date)
        ORDER BY observation_date DESC, practice_type
        """,
        (location_id, period_start, period_start, period_end, period_end),
    )
    regenerative_observations = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {
        "report_type": "capital_efficiency",
        "location_id": location_id,
        "location_name": location["name"] if location else None,
        "scenarios": _serialize_rows(scenarios),
        "regenerative_efficiency": _serialize_rows(regenerative_observations),
        "limitations": [
            "Capital efficiency and payback values are scenario evidence, not guaranteed returns.",
            "Private capital terms and draft financial assumptions are excluded.",
            "Regenerative savings should be recalculated as additional verified expense, output, and practice records mature.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_governance_throughput(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate a public-safe governance throughput report."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            """
            SELECT *
            FROM v_public_governance_throughput_summary
            WHERE (location_id = %s OR location_id IS NULL)
              AND (%s::date IS NULL OR proposal_created_at::date >= %s::date)
              AND (%s::date IS NULL OR proposal_created_at::date <= %s::date)
            ORDER BY proposal_created_at DESC, proposal_code
            """,
            (location_id, period_start, period_start, period_end, period_end),
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM v_public_governance_throughput_summary
            WHERE (%s::date IS NULL OR proposal_created_at::date >= %s::date)
              AND (%s::date IS NULL OR proposal_created_at::date <= %s::date)
            ORDER BY proposal_created_at DESC, proposal_code
            """,
            (period_start, period_start, period_end, period_end),
        )
    observations = [dict(r) for r in cur.fetchall()]
    cur.close()
    latencies = [
        float(row["decision_latency_days"]) for row in observations if row.get("decision_latency_days") is not None
    ]
    return {
        "report_type": "governance_throughput",
        "location_id": location_id,
        "observations": _serialize_rows(observations),
        "average_decision_latency_days": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "limitations": [
            "Governance throughput reflects published proposal timestamps only.",
            "Off-platform discussion, informal consensus, and private negotiation time may be excluded.",
            "Fast decisions are not automatically better decisions; risk gates and stakeholder review still apply.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_dao_proposal_history(
    conn, location_id: str = None, period_start: str = None, period_end: str = None
) -> dict:
    """Generate a read-only history of Kokonut DAO (Moloch v3 / Baal) proposals.

    Aggregates the indexer-populated ``governance_event`` ledger (chain='gnosis')
    into one record per proposal, including vote tallies and lifecycle. This is a
    read-only view; it never calls the chain.
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT
            ge.proposal_id,
            MAX(CASE WHEN ge.event_type = 'proposal_created' THEN ge.proposal_title END) AS title,
            MAX(CASE WHEN ge.event_type = 'proposal_created' THEN ge.metadata->>'description' END) AS description,
            MAX(CASE WHEN ge.event_type = 'proposal_created' THEN ge.metadata->>'proposal_type' END) AS proposal_type,
            MAX(CASE WHEN ge.event_type = 'proposal_created' THEN ge.metadata->>'content_uri' END) AS content_uri,
            COUNT(CASE WHEN ge.event_type = 'vote_cast' AND ge.vote_choice = 'yes' THEN 1 END) AS yes_votes,
            COUNT(CASE WHEN ge.event_type = 'vote_cast' AND ge.vote_choice = 'no' THEN 1 END) AS no_votes,
            BOOL_OR(ge.event_type = 'proposal_processed') AS processed,
            BOOL_OR(ge.event_type = 'proposal_cancelled') AS cancelled,
            BOOL_OR(ge.event_type = 'proposal_sponsored') AS sponsored,
            MAX(CASE WHEN ge.event_type = 'proposal_processed' THEN ge.metadata->>'passed' END) AS passed,
            MAX(CASE WHEN ge.event_type = 'proposal_processed' THEN ge.metadata->>'action_failed' END) AS action_failed
        FROM governance_event ge
        WHERE ge.chain = 'gnosis'
          AND ge.event_type IN (
            'proposal_created', 'proposal_sponsored', 'vote_cast',
            'proposal_processed', 'proposal_cancelled'
          )
        GROUP BY ge.proposal_id
        ORDER BY CAST(ge.proposal_id AS INTEGER)
        """
    )
    rows = [dict(r) for r in cur.fetchall()]

    # Resolve voter wallet addresses per proposal.
    voter_map: dict[str, list[str]] = {}
    if rows:
        cur.execute(
            """
            SELECT ge.proposal_id, ge.wallet_id, wp.address
            FROM governance_event ge
            LEFT JOIN wallet_profile wp ON wp.id = ge.wallet_id
            WHERE ge.chain = 'gnosis'
              AND ge.event_type = 'vote_cast'
              AND ge.wallet_id IS NOT NULL
            """
        )
        for r in cur.fetchall():
            voter_map.setdefault(str(r["proposal_id"]), []).append(r["address"] or str(r["wallet_id"]))
    cur.close()

    proposals = []
    for row in rows:
        pid = str(row["proposal_id"])
        passed = str(row.get("passed") or "").lower() in ("true", "1")
        action_failed = str(row.get("action_failed") or "").lower() in ("true", "1")
        if row.get("cancelled"):
            lifecycle = "cancelled"
        elif row.get("processed"):
            lifecycle = "executed" if passed else "defeated"
        elif row.get("sponsored"):
            lifecycle = "sponsored"
        else:
            # No terminal event and no explicit sponsorship: mirror the adapter's
            # dao baal proposals default (unknown -> sponsored) for consistency.
            lifecycle = "sponsored"
        voters = []
        for v in voter_map.get(pid, []):
            if v not in voters:
                voters.append(v)
        proposals.append(
            {
                "proposal_id": pid,
                "title": row.get("title"),
                "proposal_type": row.get("proposal_type"),
                "description": row.get("description"),
                "content_uri": row.get("content_uri"),
                "lifecycle": lifecycle,
                "yes_votes": int(row.get("yes_votes") or 0),
                "no_votes": int(row.get("no_votes") or 0),
                "passed": passed if row.get("processed") else None,
                "action_failed": action_failed if row.get("processed") else None,
                "voters": voters,
            }
        )

    total = len(proposals)
    summary = {
        "total": total,
        "executed": sum(1 for p in proposals if p["lifecycle"] == "executed"),
        "defeated": sum(1 for p in proposals if p["lifecycle"] == "defeated"),
        "sponsored": sum(1 for p in proposals if p["lifecycle"] == "sponsored"),
        "cancelled": sum(1 for p in proposals if p["lifecycle"] == "cancelled"),
        "pending": sum(1 for p in proposals if p["lifecycle"] == "pending"),
        "total_votes": sum(p["yes_votes"] + p["no_votes"] for p in proposals),
    }

    return {
        "report_type": "dao_proposal_history",
        "location_id": location_id,
        "dao": "Kokonut DAO (Moloch v3 / Baal)",
        "chain": "gnosis",
        "summary": summary,
        "executive_summary": [
            "The Kokonut DAO's on-chain history spans 16 proposals (IDs 1-16). "
            "Proposal 0 is a genesis/migrated pre-image with no SubmitProposal event and is excluded.",
            "Early activity centered on migration and treasury recovery from the legacy V2 deployment "
            "(proposals 1-3) and tooling experiments with a notifications bot (4-5).",
            "A middle band covers membership and share issuance, including an org membership "
            "(Kingfishers Media LLC, #11) and several community/token gestures (6-14).",
            "The two most recent and substantive proposals fund real regenerative work: finalizing the "
            "Kokonut Adelphi farm irrigation infrastructure (#15) and an Artizen onboarding campaign (#16).",
            "Vote participation is uniformly low (1-4 votes per proposal) and consensus is consistently "
            "yes-weighted; two proposals were cancelled before execution (9, 10) and two remain sponsored (8, 12).",
        ],
        "proposals": proposals,
        "limitations": [
            "Read-only aggregation of the governance_event ledger indexed from Baal contract events.",
            "Proposal 0 is a genesis/migrated pre-image with no on-chain SubmitProposal event; it is excluded.",
            "Tallies reflect on-chain cast votes only; off-platform discussion and informal consensus are not captured.",
            "Lifecycle is derived from ProcessProposal/CancelProposal events; a proposal with no terminal event is 'pending' or 'sponsored'.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
