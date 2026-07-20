"""CLI for Threatcasting service — threat management, cross-impact analysis,
flag monitoring, signals, narratives, horizons, backcasting, cascades, intelligence."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def _get_conn():
    from services.common.env import get_db
    return get_db()


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def cmd_create_threat(args):
    from services.threatcasting.cross_impact import CrossImpactAnalyzer
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO threat (location_id, threat_name, threat_type, description,
            severity_potential, probability, velocity, reversibility, time_horizon_years, tags)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            args.location_id, args.name, args.type, args.description,
            args.severity, args.probability, args.velocity,
            args.reversibility, args.horizon, args.tags or [],
        ),
    )
    threat_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    print(f"Created threat: {threat_id}")


def cmd_list_threats(args):
    conn = _get_conn()
    cur = conn.cursor()
    conditions = ["is_active = TRUE"]
    params = []
    if args.location_id:
        conditions.append("location_id = %s")
        params.append(args.location_id)
    if args.type:
        conditions.append("threat_type = %s")
        params.append(args.type)
    where = " AND ".join(conditions)
    cur.execute(f"SELECT * FROM threat WHERE {where} ORDER BY threat_name", params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    cur.close()
    for row in rows:
        print(_json(dict(zip(cols, row))))


def cmd_get_threat(args):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM threat WHERE id = %s", (args.threat_id,))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    cur.close()
    if row:
        print(_json(dict(zip(cols, row))))
    else:
        print("Threat not found")


def cmd_cross_impact(args):
    from services.threatcasting.cross_impact import CrossImpactAnalyzer
    analyzer = CrossImpactAnalyzer(conn=_get_conn())
    result = analyzer.analyze_cross_impact_matrix(args.location_id)
    print(_json(result))


def cmd_simulate_interaction(args):
    from services.threatcasting.cross_impact import CrossImpactAnalyzer
    analyzer = CrossImpactAnalyzer(conn=_get_conn())
    threat_ids = [t.strip() for t in args.threat_ids.split(",")]
    result = analyzer.simulate_threat_interaction(threat_ids)
    print(_json(result))


def cmd_create_flag(args):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO threat_flag (threat_id, flag_name, description, indicator_type,
            threshold_critical, threshold_warning, threshold_normal, unit, data_source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            args.threat_id, args.name, args.description, args.indicator_type,
            args.threshold_critical, args.threshold_warning, args.threshold_normal,
            args.unit, args.source,
        ),
    )
    flag_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    print(f"Created flag: {flag_id}")


def cmd_list_flags(args):
    from services.threatcasting.flags import FlagMonitor
    monitor = FlagMonitor(conn=_get_conn())
    flags = monitor.get_flags(
        location_id=args.location_id,
        threat_id=args.threat_id,
        status=args.status,
    )
    print(_json(flags))


def cmd_flag_status(args):
    from services.threatcasting.flags import FlagMonitor
    monitor = FlagMonitor(conn=_get_conn())
    result = monitor.get_flag_status_summary(args.location_id)
    print(_json(result))


def cmd_evaluate_flag(args):
    from services.threatcasting.flags import FlagMonitor
    monitor = FlagMonitor(conn=_get_conn())
    result = monitor.evaluate_flag(args.flag_id)
    print(_json(result))


def cmd_ingest_signal(args):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO threat_signal (threat_id, signal_source, source_reference,
            signal_type, content, confidence, signal_date)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        RETURNING id
        """,
        (args.threat_id, args.source, args.reference, args.signal_type, args.content, args.confidence),
    )
    signal_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    print(f"Ingested signal: {signal_id}")


def cmd_list_signals(args):
    conn = _get_conn()
    cur = conn.cursor()
    conditions = []
    params = []
    if args.location_id:
        conditions.append("t.location_id = %s")
        params.append(args.location_id)
    if args.source:
        conditions.append("s.signal_source = %s")
        params.append(args.source)
    if args.unclassified:
        conditions.append("s.classified = FALSE")
    where = " AND ".join(conditions) if conditions else "TRUE"
    join = "LEFT JOIN threat t ON t.id = s.threat_id" if args.location_id else ""
    cur.execute(f"SELECT s.* FROM threat_signal s {join} WHERE {where} ORDER BY s.signal_date DESC LIMIT 50", params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    cur.close()
    for row in rows:
        print(_json(dict(zip(cols, row))))


def cmd_create_narrative(args):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO threat_narrative (threat_id, narrative_type, title, summary,
            detailed_story, timeline_years, probability_estimate, impact_severity,
            key_indicators, recommended_preparedness, recommended_response)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            args.threat_id, args.type, args.title, args.summary,
            args.story, args.years, args.probability, args.severity,
            args.indicators or [], args.preparedness, args.response,
        ),
    )
    narrative_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    print(f"Created narrative: {narrative_id}")


def cmd_list_narratives(args):
    from services.threatcasting.narratives import NarrativeEngine
    engine = NarrativeEngine(conn=_get_conn())
    narratives = engine.get_narratives(
        threat_id=args.threat_id,
        narrative_type=args.type,
        location_id=args.location_id,
    )
    print(_json(narratives))


def cmd_evaluate_narrative(args):
    from services.threatcasting.desirability import DesirabilityAssessor
    assessor = DesirabilityAssessor(conn=_get_conn())
    result = assessor.assess(args.narrative_id, framework=args.framework)
    print(_json(result))


def cmd_create_horizon(args):
    from services.threatcasting.horizons import HorizonPlanner
    planner = HorizonPlanner(conn=_get_conn())
    result = planner.create_horizon(
        location_id=args.location_id,
        horizon_name=args.name,
        horizon_years=args.years,
        description=args.description,
        focus_areas=args.focus,
    )
    print(_json(result))


def cmd_horizon_overview(args):
    from services.threatcasting.horizons import HorizonPlanner
    planner = HorizonPlanner(conn=_get_conn())
    result = planner.get_horizon_overview(args.horizon_id)
    print(_json(result))


def cmd_create_backcast(args):
    from services.threatcasting.backcasting import Backcaster
    backcaster = Backcaster(conn=_get_conn())
    milestones = json.loads(args.milestones) if args.milestones else []
    result = backcaster.create_plan(
        narrative_id=args.narrative_id,
        location_id=args.location_id,
        plan_name=args.name,
        future_state_description=args.future_state,
        current_gap_analysis=args.gaps,
        milestones=milestones,
    )
    plan_id = result[0]["plan_id"] if result else None
    print(_json({"plan_id": plan_id, "milestones": result}))


def cmd_backcast_progress(args):
    from services.threatcasting.backcasting import Backcaster
    backcaster = Backcaster(conn=_get_conn())
    result = backcaster.get_progress(args.plan_id or args.narrative_id)
    print(_json(result))


def cmd_model_cascade(args):
    from services.threatcasting.cascades import CascadeModeler
    modeler = CascadeModeler(conn=_get_conn())
    chain = [t.strip() for t in args.chain.split(",")] if args.chain else []
    result = modeler.model_cascade(args.trigger_id, chain)
    print(_json(result))


def cmd_cascade_risk(args):
    from services.threatcasting.cascades import CascadeModeler
    modeler = CascadeModeler(conn=_get_conn())
    result = modeler.get_cascade_risk_score(args.location_id)
    print(_json(result))


def cmd_intelligence(args):
    from services.threatcasting.intelligence import ThreatIntelligence
    ti = ThreatIntelligence(conn=_get_conn())
    result = ti.get_threat_intelligence(args.location_id, days=args.days)
    print(_json(result))


def cmd_briefing(args):
    from services.threatcasting.intelligence import ThreatIntelligence
    ti = ThreatIntelligence(conn=_get_conn())
    result = ti.generate_threat_briefing(args.location_id)
    print(_json(result))


def cmd_landscape(args):
    from services.threatcasting.intelligence import ThreatIntelligence
    ti = ThreatIntelligence(conn=_get_conn())
    result = ti.get_threat_landscape(args.location_id)
    print(_json(result))


def cmd_preempt(args):
    from services.threatcasting.preempt import plan_preemptive_actions
    result = plan_preemptive_actions(_get_conn(), location_id=args.location_id)
    print(_json(result))


# ------------------------------------------------------------------
# Backcasting enhancements — Principles
# ------------------------------------------------------------------

def cmd_create_principle(args):
    from services.threatcasting.principles import PrincipleManager
    pm = PrincipleManager(conn=_get_conn())
    result = pm.create_principle(
        narrative_id=args.narrative_id,
        location_id=args.location_id,
        principle_name=args.name,
        description=args.description,
        principle_type=args.type,
        metric_key=args.metric_key,
        comparison_operator=args.operator,
        target_value=args.target,
        target_value_upper=args.target_upper,
        invert_direction=args.invert,
        weight=args.weight,
        source_system=args.source_system,
        crisp_dimension=args.crisp_dimension,
    )
    print(_json(result))


def cmd_list_principles(args):
    from services.threatcasting.principles import PrincipleManager
    pm = PrincipleManager(conn=_get_conn())
    results = pm.list_principles(
        narrative_id=args.narrative_id,
        location_id=args.location_id,
    )
    print(_json(results))


def cmd_align_milestone(args):
    from services.threatcasting.principles import PrincipleManager
    pm = PrincipleManager(conn=_get_conn())
    results = pm.align_milestone(
        milestone_id=args.milestone_id,
        principle_id=args.principle_id,
    )
    print(_json(results))


def cmd_align_all(args):
    from services.threatcasting.principles import PrincipleManager
    pm = PrincipleManager(conn=_get_conn())
    results = pm.align_all_milestones(args.narrative_id)
    print(_json(results))


def cmd_check_direction(args):
    from services.threatcasting.principles import PrincipleManager
    pm = PrincipleManager(conn=_get_conn())
    result = pm.check_direction(args.plan_id)
    print(_json(result))


def cmd_gap_analysis(args):
    from services.threatcasting.principles import PrincipleManager
    pm = PrincipleManager(conn=_get_conn())
    result = pm.automated_gap_analysis(args.plan_id)
    print(_json(result))


def cmd_effectiveness(args):
    from services.threatcasting.principles import PrincipleManager
    pm = PrincipleManager(conn=_get_conn())
    result = pm.effectiveness_score(args.plan_id)
    print(_json(result))


# ------------------------------------------------------------------
# Backcasting enhancements — Assumption challenges
# ------------------------------------------------------------------

def cmd_challenge_assumption(args):
    from services.threatcasting.backcasting import Backcaster
    backcaster = Backcaster(conn=_get_conn())
    result = backcaster.challenge_assumption(
        plan_id=args.plan_id,
        narrative_id=args.narrative_id,
        original_assumption=args.original,
        challenged_assumption=args.challenged,
        reason=args.reason,
    )
    print(_json(result))


def cmd_list_challenges(args):
    from services.threatcasting.backcasting import Backcaster
    backcaster = Backcaster(conn=_get_conn())
    results = backcaster.list_challenges(args.plan_id)
    print(_json(results))


def cmd_resolve_challenge(args):
    from services.threatcasting.backcasting import Backcaster
    backcaster = Backcaster(conn=_get_conn())
    result = backcaster.resolve_challenge(
        challenge_id=args.challenge_id,
        outcome=args.outcome,
        approved_by=args.approved_by,
        revised_milestone_id=args.revised_milestone_id,
        impact_on_principles=args.impact,
    )
    print(_json(result))


# ------------------------------------------------------------------
# Backcasting enhancements — Path comparison
# ------------------------------------------------------------------

def cmd_compare_paths(args):
    from services.threatcasting.path_comparison import PathComparator
    pc = PathComparator(conn=_get_conn())
    criteria = json.loads(args.criteria) if args.criteria else None
    result = pc.create_comparison(
        location_id=args.location_id,
        comparison_name=args.name,
        narrative_ids=[n.strip() for n in args.narrative_ids.split(",")],
        criteria=criteria,
    )
    print(_json(result))


def cmd_evaluate_paths(args):
    from services.threatcasting.path_comparison import PathComparator
    pc = PathComparator(conn=_get_conn())
    result = pc.evaluate_paths(args.comparison_id)
    print(_json(result))


def cmd_manual_compare(args):
    from services.threatcasting.path_comparison import PathComparator
    pc = PathComparator(conn=_get_conn())
    scores = json.loads(args.scores)
    result = pc.manual_compare(
        comparison_id=args.comparison_id,
        user_scores=scores,
    )
    print(_json(result))


def cmd_list_comparisons(args):
    from services.threatcasting.path_comparison import PathComparator
    pc = PathComparator(conn=_get_conn())
    results = pc.list_comparisons(location_id=args.location_id)
    print(_json(results))


def cmd_delete_comparison(args):
    from services.threatcasting.path_comparison import PathComparator
    pc = PathComparator(conn=_get_conn())
    deleted = pc.delete_comparison(args.comparison_id)
    print(f"Deleted: {deleted}")


def cmd_create_premortem(args):
    from services.threatcasting.path_comparison import PathComparator
    pc = PathComparator(conn=_get_conn())
    result = pc.upsert_premortem(
        comparison_id=args.comparison_id,
        narrative_id=args.narrative_id,
        failure_modes=json.loads(args.failure_modes),
        assumptions=json.loads(args.assumptions),
        early_warning_signals=json.loads(args.warning_signals),
        mitigations=json.loads(args.mitigations),
        residual_risk_notes=args.residual_risk_notes,
        evidence_notes=args.evidence_notes,
    )
    print(_json(result))


def cmd_list_premortems(args):
    from services.threatcasting.path_comparison import PathComparator
    pc = PathComparator(conn=_get_conn())
    print(_json(pc.list_premortems(args.comparison_id, args.status)))


def cmd_submit_premortem(args):
    from services.threatcasting.path_comparison import PathComparator
    pc = PathComparator(conn=_get_conn())
    print(_json(pc.submit_premortem(args.premortem_id, args.submitted_by)))


def cmd_review_premortem(args):
    from services.threatcasting.path_comparison import PathComparator
    pc = PathComparator(conn=_get_conn())
    print(_json(pc.review_premortem(args.premortem_id, args.result, args.reviewer_id, args.notes)))


def cmd_forecast_question_create(args):
    from services.threatcasting.probability import ProbabilityResolver
    resolver = ProbabilityResolver(_get_conn())
    result = resolver.create_question(
        args.location_id, args.domain, args.question, args.event_definition,
        args.resolution_criteria, args.resolution_source,
        datetime.fromisoformat(args.opens_at), datetime.fromisoformat(args.closes_at),
        datetime.fromisoformat(args.resolves_by), args.created_by,
        args.threat_id, args.narrative_id,
    )
    print(_json(result))


def cmd_forecast_question_status(args):
    from services.threatcasting.probability import ProbabilityResolver
    print(_json(ProbabilityResolver(_get_conn()).set_question_status(args.question_id, args.status)))


def cmd_probability_forecast(args):
    from services.threatcasting.probability import ProbabilityResolver
    result = ProbabilityResolver(_get_conn()).issue_forecast(
        args.question_id, args.probability, args.source_type, args.methodology_version, args.source_id
    )
    print(_json(result))


def cmd_forecast_resolve(args):
    from services.threatcasting.probability import ProbabilityResolver
    outcome = None if args.outcome is None else float(args.outcome)
    result = ProbabilityResolver(_get_conn()).resolve(
        args.question_id, outcome, args.status, json.loads(args.evidence), args.notes, args.resolved_by
    )
    print(_json(result))


def cmd_expert_calibrate(args):
    from services.threatcasting.probability import ProbabilityResolver
    print(_json(ProbabilityResolver(_get_conn()).calibrate_expert(args.panel_member_id, args.domain)))


def main():
    parser = argparse.ArgumentParser(description="Threatcasting Service")
    sub = parser.add_subparsers(dest="command", help="Command")

    # Threats
    p = sub.add_parser("create-threat", help="Create a threat")
    p.add_argument("--location-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--type", required=True, choices=["climate","policy","market","technology","ecological","social","health","security"])
    p.add_argument("--description")
    p.add_argument("--severity", default="medium", choices=["low","medium","high","critical"])
    p.add_argument("--probability", type=float)
    p.add_argument("--velocity", default="moderate", choices=["slow","moderate","fast","rapid"])
    p.add_argument("--reversibility", default="partially", choices=["reversible","partially","irreversible"])
    p.add_argument("--horizon", type=int, default=5)
    p.add_argument("--tags", nargs="*")
    p.set_defaults(func=cmd_create_threat)

    p = sub.add_parser("list-threats", help="List threats")
    p.add_argument("--location-id")
    p.add_argument("--type")
    p.set_defaults(func=cmd_list_threats)

    p = sub.add_parser("get-threat", help="Get a threat")
    p.add_argument("--threat-id", required=True)
    p.set_defaults(func=cmd_get_threat)

    # Cross-impact
    p = sub.add_parser("cross-impact", help="Analyze cross-impact matrix")
    p.add_argument("--location-id", required=True)
    p.set_defaults(func=cmd_cross_impact)

    p = sub.add_parser("simulate-interaction", help="Simulate threat interaction")
    p.add_argument("--threat-ids", required=True)
    p.set_defaults(func=cmd_simulate_interaction)

    # Flags
    p = sub.add_parser("create-flag", help="Create a flag")
    p.add_argument("--threat-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--description")
    p.add_argument("--indicator-type", default="quantitative")
    p.add_argument("--threshold-critical", type=float)
    p.add_argument("--threshold-warning", type=float)
    p.add_argument("--threshold-normal", type=float)
    p.add_argument("--unit")
    p.add_argument("--source")
    p.set_defaults(func=cmd_create_flag)

    p = sub.add_parser("list-flags", help="List flags")
    p.add_argument("--location-id")
    p.add_argument("--threat-id")
    p.add_argument("--status")
    p.set_defaults(func=cmd_list_flags)

    p = sub.add_parser("flag-status", help="Flag status summary")
    p.add_argument("--location-id", required=True)
    p.set_defaults(func=cmd_flag_status)

    p = sub.add_parser("evaluate-flag", help="Evaluate a flag")
    p.add_argument("--flag-id", required=True)
    p.set_defaults(func=cmd_evaluate_flag)

    # Signals
    p = sub.add_parser("ingest-signal", help="Ingest a signal")
    p.add_argument("--source", required=True)
    p.add_argument("--content", required=True)
    p.add_argument("--threat-id")
    p.add_argument("--reference")
    p.add_argument("--signal-type", default="text")
    p.add_argument("--confidence", type=float)
    p.set_defaults(func=cmd_ingest_signal)

    p = sub.add_parser("list-signals", help="List signals")
    p.add_argument("--location-id")
    p.add_argument("--source")
    p.add_argument("--unclassified", action="store_true")
    p.set_defaults(func=cmd_list_signals)

    # Narratives
    p = sub.add_parser("create-narrative", help="Create a narrative")
    p.add_argument("--threat-id", required=True)
    p.add_argument("--type", required=True, choices=["desirable","undesirable","baseline","wildcard"])
    p.add_argument("--title", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--story", required=True)
    p.add_argument("--years", type=int, required=True)
    p.add_argument("--probability", type=float)
    p.add_argument("--severity")
    p.add_argument("--indicators", nargs="*")
    p.add_argument("--preparedness")
    p.add_argument("--response")
    p.set_defaults(func=cmd_create_narrative)

    p = sub.add_parser("list-narratives", help="List narratives")
    p.add_argument("--threat-id")
    p.add_argument("--type")
    p.add_argument("--location-id")
    p.set_defaults(func=cmd_list_narratives)

    p = sub.add_parser("evaluate-narrative", help="Evaluate narrative desirability")
    p.add_argument("--narrative-id", required=True)
    p.add_argument("--framework", default="gnh", choices=["gnh","8_forms_capital","sdg","composite"])
    p.set_defaults(func=cmd_evaluate_narrative)

    # Horizons
    p = sub.add_parser("create-horizon", help="Create a horizon")
    p.add_argument("--location-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--years", type=int, required=True)
    p.add_argument("--description")
    p.add_argument("--focus", nargs="*")
    p.set_defaults(func=cmd_create_horizon)

    p = sub.add_parser("horizon-overview", help="Horizon overview")
    p.add_argument("--horizon-id", required=True)
    p.set_defaults(func=cmd_horizon_overview)

    # Backcasting
    p = sub.add_parser("create-backcast", help="Create backcast plan")
    p.add_argument("--narrative-id", required=True)
    p.add_argument("--location-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--future-state", required=True)
    p.add_argument("--gaps", required=True)
    p.add_argument("--milestones")
    p.set_defaults(func=cmd_create_backcast)

    p = sub.add_parser("backcast-progress", help="Backcast progress")
    identifier = p.add_mutually_exclusive_group(required=True)
    identifier.add_argument("--plan-id", help="Canonical backcast plan UUID (preferred)")
    identifier.add_argument("--narrative-id", help="Legacy narrative UUID; fails if it has multiple plans")
    p.set_defaults(func=cmd_backcast_progress)

    # Cascades
    p = sub.add_parser("model-cascade", help="Model a cascade")
    p.add_argument("--trigger-id", required=True)
    p.add_argument("--chain")
    p.set_defaults(func=cmd_model_cascade)

    p = sub.add_parser("cascade-risk", help="Cascade risk score")
    p.add_argument("--location-id", required=True)
    p.set_defaults(func=cmd_cascade_risk)

    # Intelligence
    p = sub.add_parser("intelligence", help="Get intelligence")
    p.add_argument("--location-id", required=True)
    p.add_argument("--days", type=int, default=30)
    p.set_defaults(func=cmd_intelligence)

    p = sub.add_parser("briefing", help="Generate briefing")
    p.add_argument("--location-id", required=True)
    p.set_defaults(func=cmd_briefing)

    p = sub.add_parser("landscape", help="Threat landscape")
    p.add_argument("--location-id", required=True)
    p.set_defaults(func=cmd_landscape)

    # Backcasting enhancements — Principles
    p = sub.add_parser("create-principle", help="Create a sustainability principle")
    p.add_argument("--narrative-id", required=True)
    p.add_argument("--location-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--type", default="custom", choices=["sustainability","operational","financial","ecological","social","custom"])
    p.add_argument("--metric-key")
    p.add_argument("--operator", default="gte", choices=["gt","gte","lt","lte","eq","neq","between"])
    p.add_argument("--target", type=float)
    p.add_argument("--target-upper", type=float)
    p.add_argument("--invert", action="store_true")
    p.add_argument("--weight", type=float, default=1.0)
    p.add_argument("--source-system", default="manual", choices=["metric","crisp","manual"])
    p.add_argument("--crisp-dimension")
    p.set_defaults(func=cmd_create_principle)

    p = sub.add_parser("list-principles", help="List principles")
    p.add_argument("--narrative-id")
    p.add_argument("--location-id")
    p.set_defaults(func=cmd_list_principles)

    p = sub.add_parser("align-milestone", help="Align milestone to principles")
    p.add_argument("--milestone-id", required=True)
    p.add_argument("--principle-id")
    p.set_defaults(func=cmd_align_milestone)

    p = sub.add_parser("align-all", help="Align all milestones for a narrative")
    p.add_argument("--narrative-id", required=True)
    p.set_defaults(func=cmd_align_all)

    p = sub.add_parser("check-direction", help="Check direction toward principles")
    p.add_argument("--plan-id", required=True)
    p.set_defaults(func=cmd_check_direction)

    p = sub.add_parser("gap-analysis", help="Automated gap analysis")
    p.add_argument("--plan-id", required=True)
    p.set_defaults(func=cmd_gap_analysis)

    p = sub.add_parser("effectiveness", help="Effectiveness score for completed milestones")
    p.add_argument("--plan-id", required=True)
    p.set_defaults(func=cmd_effectiveness)

    # Backcasting enhancements — Assumption challenges
    p = sub.add_parser("challenge-assumption", help="Record an assumption challenge")
    p.add_argument("--plan-id", required=True)
    p.add_argument("--narrative-id", required=True)
    p.add_argument("--original", required=True, help="Original assumption")
    p.add_argument("--challenged", required=True, help="Challenged assumption")
    p.add_argument("--reason", help="Reason for challenge")
    p.set_defaults(func=cmd_challenge_assumption)

    p = sub.add_parser("list-challenges", help="List assumption challenges")
    p.add_argument("--plan-id", required=True)
    p.set_defaults(func=cmd_list_challenges)

    p = sub.add_parser("resolve-challenge", help="Resolve assumption challenge (requires approval)")
    p.add_argument("--challenge-id", required=True)
    p.add_argument("--outcome", required=True, choices=["confirmed","modified","rejected"])
    p.add_argument("--approved-by", required=True, help="Human approver")
    p.add_argument("--revised-milestone-id")
    p.add_argument("--impact", help="Impact on principles")
    p.set_defaults(func=cmd_resolve_challenge)

    # Backcasting enhancements — Path comparison
    p = sub.add_parser("compare-paths", help="Create path comparison")
    p.add_argument("--location-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--narrative-ids", required=True, help="Comma-separated narrative UUIDs")
    p.add_argument("--criteria", help="JSON criteria weights")
    p.set_defaults(func=cmd_compare_paths)

    p = sub.add_parser("evaluate-paths", help="Auto-evaluate and rank paths")
    p.add_argument("--comparison-id", required=True)
    p.set_defaults(func=cmd_evaluate_paths)

    p = sub.add_parser("manual-compare", help="Apply manual scores to paths")
    p.add_argument("--comparison-id", required=True)
    p.add_argument("--scores", required=True, help="JSON {narrative_id: {criterion: score}}")
    p.set_defaults(func=cmd_manual_compare)

    p = sub.add_parser("list-comparisons", help="List path comparisons")
    p.add_argument("--location-id")
    p.set_defaults(func=cmd_list_comparisons)

    p = sub.add_parser("delete-comparison", help="Delete path comparison")
    p.add_argument("--comparison-id", required=True)
    p.set_defaults(func=cmd_delete_comparison)

    p = sub.add_parser("premortem-create", help="Create or revise a path premortem draft")
    p.add_argument("--comparison-id", required=True)
    p.add_argument("--narrative-id", required=True)
    p.add_argument("--failure-modes", required=True, help="JSON array with description fields")
    p.add_argument("--assumptions", default="[]")
    p.add_argument("--warning-signals", default="[]")
    p.add_argument("--mitigations", default="[]")
    p.add_argument("--residual-risk-notes")
    p.add_argument("--evidence-notes")
    p.set_defaults(func=cmd_create_premortem)

    p = sub.add_parser("premortem-list", help="List private premortem records")
    p.add_argument("--comparison-id", required=True)
    p.add_argument("--status", choices=["draft", "submitted", "verified", "rejected"])
    p.set_defaults(func=cmd_list_premortems)

    p = sub.add_parser("premortem-submit", help="Submit a premortem for human review")
    p.add_argument("--premortem-id", required=True)
    p.add_argument("--submitted-by", required=True)
    p.set_defaults(func=cmd_submit_premortem)

    p = sub.add_parser("premortem-review", help="Verify or reject a submitted premortem")
    p.add_argument("--premortem-id", required=True)
    p.add_argument("--result", required=True, choices=["verified", "rejected"])
    p.add_argument("--reviewer-id", required=True)
    p.add_argument("--notes", required=True)
    p.set_defaults(func=cmd_review_premortem)

    p = sub.add_parser("forecast-question-create", help="Create a resolvable threat forecast question")
    p.add_argument("--location-id", required=True)
    p.add_argument("--threat-id")
    p.add_argument("--narrative-id")
    p.add_argument("--domain", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--event-definition", required=True)
    p.add_argument("--resolution-criteria", required=True)
    p.add_argument("--resolution-source", required=True)
    p.add_argument("--opens-at", required=True)
    p.add_argument("--closes-at", required=True)
    p.add_argument("--resolves-by", required=True)
    p.add_argument("--created-by", required=True)
    p.set_defaults(func=cmd_forecast_question_create)

    p = sub.add_parser("forecast-question-status", help="Open or close a forecast question")
    p.add_argument("--question-id", required=True)
    p.add_argument("--status", required=True, choices=["open", "closed"])
    p.set_defaults(func=cmd_forecast_question_status)

    p = sub.add_parser("probability-forecast", help="Issue an immutable probability forecast")
    p.add_argument("--question-id", required=True)
    p.add_argument("--probability", required=True, type=float)
    p.add_argument("--source-type", required=True, choices=["delphi_member","delphi_unweighted_consensus","delphi_weighted_consensus","analyst","model"])
    p.add_argument("--source-id")
    p.add_argument("--methodology-version", default="v1")
    p.set_defaults(func=cmd_probability_forecast)

    p = sub.add_parser("forecast-resolve", help="Resolve, cancel, or invalidate a forecast question")
    p.add_argument("--question-id", required=True)
    p.add_argument("--status", required=True, choices=["resolved", "cancelled", "invalid"])
    p.add_argument("--outcome", choices=["0", "1"])
    p.add_argument("--evidence", default="[]")
    p.add_argument("--notes", required=True)
    p.add_argument("--resolved-by", required=True)
    p.set_defaults(func=cmd_forecast_resolve)

    p = sub.add_parser("expert-calibrate", help="Calibrate a Delphi expert from resolved forecasts")
    p.add_argument("--panel-member-id", required=True)
    p.add_argument("--domain", required=True)
    p.set_defaults(func=cmd_expert_calibrate)

    # Preemptive Intervention Planner — "best defense is a good offense"
    p = sub.add_parser(
        "preempt",
        help="Plan DRAFT preemptive interventions from warning-band flags (read-only)",
    )
    p.add_argument("--location-id", help="Limit to a single location")
    p.set_defaults(func=cmd_preempt)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
