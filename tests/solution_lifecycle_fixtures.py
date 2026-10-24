"""Direct SQL setup for legacy lifecycle integration-test fixtures only."""

from __future__ import annotations

from uuid import uuid4


def create_solution_fixture(
    connection,
    canonical_key: str,
    name: str,
    solution_type: str,
    problem_statement: str,
    *,
    owner_party_id: str | None = None,
) -> dict:
    """Insert an unscoped fixture without exercising retired application writers."""
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO solution (
                       canonical_key, name, solution_type, problem_statement,
                       owner_party_id
                   ) VALUES (%s, %s, %s, %s, %s::uuid)
                   RETURNING id, canonical_key, name, solution_type, current_stage, status""",
            (canonical_key, name, solution_type, problem_statement, owner_party_id),
        )
        row = cursor.fetchone()
        columns = [item.name for item in cursor.description]
    connection.commit()
    return dict(zip(columns, row))


def create_gate_fixture(connection, solution_id: str, from_stage: str, to_stage: str) -> str:
    """Insert a gate as fixture state; production gate definition needs a scoped route."""
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO solution_stage_gate (solution_id, from_stage, to_stage)
               VALUES (%s::uuid, %s, %s) RETURNING id""",
            (solution_id, from_stage, to_stage),
        )
        gate_id = str(cursor.fetchone()[0])
    connection.commit()
    return gate_id


def fixture_key(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16]}"
