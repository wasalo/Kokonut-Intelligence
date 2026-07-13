"""CLI for Threatcasting service — threat management, cross-impact analysis,
flag monitoring, signals, narratives, horizons, backcasting, cascades, intelligence."""

from __future__ import annotations

import argparse
import json
import sys
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
    print(_json(result))


def cmd_backcast_progress(args):
    from services.threatcasting.backcasting import Backcaster
    backcaster = Backcaster(conn=_get_conn())
    result = backcaster.get_progress(args.narrative_id)
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
    p.add_argument("--narrative-id", required=True)
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

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
