"""Offline checks for migration-backed analytics reader projections."""

from contextlib import nullcontext
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from services.analytics import (
    governance_cockpit,
    governance_links,
    governance_roles,
    governance_tactical,
    stakeholder_decisions,
    stakeholder_representation,
    stakeholders,
    strategy_execution,
    strategy_map,
)


def _connection(*, rows=(), one=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = list(rows)
    cursor.fetchone.return_value = one
    cursor_context = MagicMock()
    cursor_context.__enter__.return_value = cursor
    connection = MagicMock()
    connection.cursor.return_value = cursor_context
    return connection, cursor


def _query(cursor):
    return " ".join(cursor.execute.call_args.args[0].split())


def _params(cursor):
    return cursor.execute.call_args.args[1]


def test_stakeholder_list_uses_migration_316_projection_and_party_status_alias():
    party_id = uuid4()
    row = {"party_id": party_id, "display_name": "Synthetic party", "party_status": "active"}
    connection, cursor = _connection(rows=[row])

    result = stakeholders.list_parties(connection, party_type="person", status="active")

    assert _query(cursor) == (
        "SELECT party_id, party_type, display_name, party_status, privacy_level, "
        "identifier_count, active_relationship_count, open_interest_count, advisory_score, "
        "salience_review_status, last_updated_at FROM v_stakeholder_landscape "
        "WHERE party_type = %s AND party_status = %s ORDER BY display_name"
    )
    assert _params(cursor) == ["person", "active"]
    assert result == [dict(row, party_id=str(party_id))]


def test_internal_governance_cockpit_uses_thirteen_migration_249_columns():
    row = {"active_circle_count": 2, "open_tactical_item_count": 1}
    connection, cursor = _connection(one=row)

    result = governance_cockpit.internal_cockpit(connection)

    assert _query(cursor) == (
        "SELECT active_circle_count, active_role_count, unassigned_role_count, "
        "overdue_assignment_review_count, unresolved_tension_count, "
        "high_severity_tension_count, proposals_awaiting_review_count, "
        "open_objection_count, material_objection_count, links_expiring_soon_count, "
        "overdue_tactical_item_count, open_tactical_item_count, generated_at "
        "FROM v_governance_cockpit_internal"
    )
    assert result == row


def test_strategy_map_execution_dashboard_preserves_filters_order_and_payload(monkeypatch):
    strategy_id = uuid4()
    created_at = datetime(2026, 10, 29, tzinfo=timezone.utc)
    row = {"strategy_id": strategy_id, "objective_statement": "Synthetic", "created_at": created_at}
    connection, cursor = _connection(rows=[row])
    monkeypatch.setattr(strategy_map, "_conn", lambda: nullcontext(connection))

    result = strategy_map.get_execution_dashboard(
        entity_type="location", entity_id=strategy_id
    )

    assert _query(cursor) == (
        "SELECT strategy_id, entity_type, entity_id, perspective, strategic_theme, "
        "objective_statement, target_value, current_value, unit, weight, objective_status, "
        "progress_pct, initiative_count, completed_initiatives, avg_initiative_progress, "
        "created_at, updated_at, capability_count FROM v_strategy_execution "
        "WHERE entity_type = %s AND entity_id = %s::uuid "
        "ORDER BY perspective, objective_statement"
    )
    assert _params(cursor) == ["location", strategy_id]
    assert result == [
        {"strategy_id": str(strategy_id), "objective_statement": "Synthetic", "created_at": created_at.isoformat()}
    ]


def test_representation_metrics_uses_exact_fourteen_column_projection():
    row = {"activity_type": "decision", "participated_count": 4}
    connection, cursor = _connection(one=row)

    result = stakeholder_representation.representation_metrics(
        connection, "decision", "a0000000-0000-0000-0000-000000000001"
    )

    assert _query(cursor) == (
        "SELECT activity_type, activity_id, invited_count, accepted_count, participated_count, "
        "declined_count, absent_count, contributing_count, access_needs_count, "
        "accessibility_request_count, minority_view_count, minority_view_preserved_count, "
        "participation_rate_pct, contribution_rate_pct FROM v_stakeholder_representation_metrics "
        "WHERE activity_type = %s AND activity_id = %s::uuid"
    )
    assert _params(cursor) == ("decision", "a0000000-0000-0000-0000-000000000001")
    assert result == row


def test_equity_distribution_summary_preserves_scope_order_and_payload():
    location_id = uuid4()
    row = {"scope_type": "location", "scope_id": location_id, "beneficiary_count": 2}
    connection, cursor = _connection(rows=[row])

    result = stakeholder_representation.list_distribution_summary(
        connection, scope_type="location", scope_id=str(location_id)
    )

    assert _query(cursor) == (
        "SELECT scope_type, scope_id, distribution_type, metric_name, unit, record_count, "
        "beneficiary_count, total_amount, earliest_period, latest_period "
        "FROM v_stakeholder_equity_distribution WHERE scope_type = %s AND scope_id = %s::uuid "
        "ORDER BY distribution_type, metric_name"
    )
    assert _params(cursor) == ["location", str(location_id)]
    assert result == [dict(row, scope_id=str(location_id))]


def test_stakeholder_decision_detail_uses_exact_twenty_six_column_projection():
    decision_id = uuid4()
    row = {"decision_id": decision_id, "title": "Synthetic decision"}
    connection, cursor = _connection(one=row)

    result = stakeholder_decisions.get_decision(connection, str(decision_id))

    projection = stakeholder_decisions._DECISION_LINEAGE_PROJECTION
    assert len(projection.split(", ")) == 26
    assert _query(cursor) == (
        f"SELECT {projection} FROM v_stakeholder_decision_lineage "
        "WHERE decision_id = %s::uuid"
    )
    assert _params(cursor) == (str(decision_id),)
    assert result == {"decision_id": str(decision_id), "title": "Synthetic decision"}


def test_stakeholder_decision_list_keeps_optional_filters_and_approved_order():
    scope_id = uuid4()
    connection, cursor = _connection(rows=[{"status": "approved", "scope_id": scope_id}])

    result = stakeholder_decisions.list_decisions(
        connection, status="approved", scope_id=str(scope_id)
    )

    projection = stakeholder_decisions._DECISION_LINEAGE_PROJECTION
    assert _query(cursor) == (
        f"SELECT {projection} FROM v_stakeholder_decision_lineage "
        "WHERE status = %s AND scope_id = %s::uuid "
        "ORDER BY approved_at DESC NULLS LAST, decision_id"
    )
    assert _params(cursor) == ["approved", str(scope_id)]
    assert result == [{"status": "approved", "scope_id": str(scope_id)}]


def test_governance_circle_registry_projection_preserves_status_and_scope_filters():
    connection, cursor = _connection(rows=[{"circle_id": uuid4(), "circle_key": "synthetic"}])

    result = governance_roles.list_circles(
        connection, status="active", scope_type="location"
    )

    assert _query(cursor) == (
        "SELECT circle_id, circle_key, name, purpose, parent_circle_id, parent_circle_key, "
        "scope_type, scope_id, status, review_due_at, active_role_count, "
        "overdue_role_review_count FROM v_governance_circle_registry "
        "WHERE status = %s AND scope_type = %s ORDER BY circle_key"
    )
    assert _params(cursor) == ["active", "location"]
    assert result[0]["circle_key"] == "synthetic"


def test_governance_role_registry_projection_preserves_filters_and_sort():
    circle_id = uuid4()
    connection, cursor = _connection(rows=[{"role_id": uuid4(), "role_key": "steward"}])

    result = governance_roles.list_roles(connection, circle_id=str(circle_id), status="active")

    assert _query(cursor) == (
        "SELECT role_id, circle_id, circle_key, circle_name, role_key, name, purpose, "
        "status, effective_from, effective_until, review_due_at, accountability_count, "
        "required_accountability_count FROM v_governance_role_registry "
        "WHERE circle_id = %s::uuid AND status = %s ORDER BY circle_key, role_key"
    )
    assert _params(cursor) == [str(circle_id), "active"]
    assert result == [{"role_id": result[0]["role_id"], "role_key": "steward"}]


def test_governance_assignment_projection_preserves_all_three_filters():
    role_id = uuid4()
    party_id = uuid4()
    connection, cursor = _connection(rows=[{"assignment_id": uuid4(), "party_name": "Reviewer"}])

    result = governance_roles.list_assignments(
        connection, role_id=str(role_id), party_id=str(party_id), status="active"
    )

    assert _query(cursor) == (
        "SELECT assignment_id, role_id, role_key, role_name, circle_id, circle_key, "
        "party_id, party_name, party_type, assignment_type, status, mandate, recusal_status, "
        "effective_from, effective_until, review_due_at, approved_by_party_id, approved_by_name "
        "FROM v_governance_role_assignments WHERE role_id = %s::uuid AND party_id = %s::uuid "
        "AND status = %s ORDER BY role_name, party_name"
    )
    assert _params(cursor) == [str(role_id), str(party_id), "active"]
    assert result[0]["party_name"] == "Reviewer"


def test_governance_circle_links_projection_preserves_scope_filters_and_order():
    source_id, target_id, party_id = uuid4(), uuid4(), uuid4()
    connection, cursor = _connection(rows=[{"link_id": uuid4(), "party_name": "Delegate"}])

    result = governance_links.list_links(
        connection,
        source_circle_id=str(source_id),
        target_circle_id=str(target_id),
        party_id=str(party_id),
        status="active",
    )

    assert _query(cursor) == (
        "SELECT link_id, source_circle_id, source_circle_key, target_circle_id, target_circle_key, "
        "link_type, role_id, role_key, party_id, party_name, mandate, scope_type, scope_id, "
        "term_start, term_end, status, recusal_status, approved_by_party_id, approved_by_name "
        "FROM v_governance_circle_links WHERE source_circle_id = %s::uuid "
        "AND target_circle_id = %s::uuid AND party_id = %s::uuid AND status = %s "
        "ORDER BY term_end NULLS LAST, source_circle_key"
    )
    assert _params(cursor) == [str(source_id), str(target_id), str(party_id), "active"]
    assert result[0]["party_name"] == "Delegate"


def test_tactical_session_health_projection_preserves_circle_and_status_filters():
    circle_id = uuid4()
    connection, cursor = _connection(rows=[{"session_id": uuid4(), "open_item_count": 2}])

    result = governance_tactical.list_sessions(
        connection, circle_id=str(circle_id), status="active"
    )

    assert _query(cursor) == (
        "SELECT session_id, circle_id, circle_key, session_type, title, scheduled_at, "
        "session_status, item_count, open_item_count, disposed_item_count, overdue_item_count "
        "FROM v_governance_tactical_health WHERE circle_id = %s::uuid AND session_status = %s "
        "ORDER BY scheduled_at NULLS LAST"
    )
    assert _params(cursor) == [str(circle_id), "active"]
    assert result[0]["open_item_count"] == 2


def test_strategy_execution_projection_preserves_plan_scope_and_order():
    plan_id, scope_id = uuid4(), uuid4()
    created_at = datetime(2026, 10, 29, tzinfo=timezone.utc)
    row = {"strategy_plan_id": plan_id, "scope_id": scope_id, "latest_execution_update": created_at}
    connection, cursor = _connection(rows=[row])

    result = strategy_execution.dashboard(
        connection,
        strategy_plan_id=str(plan_id),
        scope_type="location",
        scope_id=str(scope_id),
    )

    assert _query(cursor) == (
        "SELECT strategy_plan_id, scope_type, scope_id, name, version, plan_status, visibility, "
        "objective_count, accountable_objective_count, measured_objective_count, initiative_count, "
        "completed_initiative_count, average_initiative_completion_pct, investment_case_count, "
        "recommended_investment_count, average_investment_score, open_coherence_finding_count, "
        "critical_coherence_finding_count, latest_execution_update "
        "FROM v_strategy_kernel_execution WHERE strategy_plan_id = %s::uuid "
        "AND scope_type = %s AND scope_id = %s::uuid ORDER BY scope_type, scope_id, version DESC"
    )
    assert _params(cursor) == [str(plan_id), "location", str(scope_id)]
    assert result == [
        {
            "strategy_plan_id": str(plan_id),
            "scope_id": str(scope_id),
            "latest_execution_update": created_at,
        }
    ]
