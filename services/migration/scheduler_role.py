"""Provision the migration-backed global scheduler executor identity."""
from psycopg2 import sql

from services.migration.runtime_role import _ensure_login_role, _remove_role_memberships, _verify_role_attributes


def provision_scheduler_role(conn, *, database: str, password: str, forbidden_passwords=()):
    if not isinstance(password, str) or len(password.encode('utf-8')) < 32:
        raise ValueError('scheduler password must contain at least 32 UTF-8 bytes')
    if password in forbidden_passwords:
        raise ValueError('scheduler password must be distinct from other runtime credentials')
    name = 'kokonut_scheduler_login'
    ident = sql.Identifier(name)
    was_autocommit = conn.autocommit
    if was_autocommit:
        conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT has_column_privilege(%s,'public.scheduled_task','lease_owner','UPDATE')", (name,))
            if not cur.fetchone()[0]:
                raise RuntimeError('scheduler executor migration is required')
            _ensure_login_role(cur, name=name, identifier=ident, password=password)
            _remove_role_memberships(cur, role_name=name, identifier=ident)
            _verify_role_attributes(cur, name)
            execution_columns = {
                "scheduled_task": (set(), set("last_run_at last_status next_run_at retry_at retry_attempt run_window_at lease_owner lease_token lease_expires_at updated_at last_duration_ms consecutive_failures".split())),
                "task_run": (set("id task_id status worker_id lease_token heartbeat_at attempt_count retry_count allow_overlap scheduled_for".split()), set("status completed_at duration_ms error_message stdout heartbeat_at".split())),
                "task_resource": (set(), {"current_running"}),
            }
            for relation, (insert_columns, update_columns) in execution_columns.items():
                cur.execute(
                    """SELECT attname,
                              has_column_privilege(%s,attrelid,attnum,'INSERT'),
                              has_column_privilege(%s,attrelid,attnum,'UPDATE')
                         FROM pg_attribute WHERE attrelid=%s::regclass
                           AND attnum>0 AND NOT attisdropped""",
                    (name, name, "public." + relation),
                )
                for column, can_insert, can_update in cur.fetchall():
                    if (can_insert != (column in insert_columns)
                            or can_update != (column in update_columns)):
                        raise RuntimeError("scheduler execution column contract differs from migration")
            for relation, column, privilege in (
                ("scheduled_task", "module_path", "UPDATE"),
                ("scheduled_task", "is_enabled", "UPDATE"),
                ("task_resource", "max_concurrent", "UPDATE"),
                ("platform_event", "payload", "SELECT"),
                ("platform_event", "event_type", "INSERT"),
                ("schema_migration", "checksum", "UPDATE"),
            ):
                cur.execute("SELECT has_column_privilege(%s,%s,%s,%s)",
                            (name, "public." + relation, column, privilege))
                if cur.fetchone()[0]:
                    raise RuntimeError("scheduler retains an unexpected column privilege")
            for relation in ("scheduled_task", "task_run", "task_resource", "platform_event"):
                for privilege in ("DELETE", "TRUNCATE", "TRIGGER", "REFERENCES"):
                    cur.execute("SELECT has_table_privilege(%s,%s,%s)",
                                (name, "public." + relation, privilege))
                    if cur.fetchone()[0]:
                        raise RuntimeError("scheduler retains an unexpected table privilege")

            cur.execute(
                """SELECT EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname IN ('public','kokonut_security')
                      AND c.relkind IN ('r','p','v','m','f')
                      AND NOT (n.nspname='public' AND c.relname IN
                               ('scheduled_task','task_run','task_resource'))
                      AND (has_any_column_privilege(%s,c.oid,'INSERT,UPDATE,REFERENCES')
                           OR has_table_privilege(%s,c.oid,'DELETE,TRUNCATE,TRIGGER'))
                )""", (name, name),
            )
            if cur.fetchone()[0]:
                raise RuntimeError("scheduler retains mutation privileges outside execution state")
            cur.execute(
                """SELECT p.oid::regprocedure::text
                     FROM pg_proc AS p
                     JOIN pg_namespace AS n ON n.oid=p.pronamespace
                    WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                      AND n.nspname NOT LIKE 'pg_toast%%'
                      AND has_schema_privilege(%s,n.oid,'USAGE')
                      AND p.prosecdef
                      AND p.prorettype NOT IN ('trigger'::regtype,'event_trigger'::regtype)
                      AND has_function_privilege(%s,p.oid,'EXECUTE')
                      AND p.oid <> 'kokonut_security.enqueue_scheduler_run_event(uuid,text)'::regprocedure
                    ORDER BY p.oid::regprocedure::text
                    LIMIT 1""",
                (name, name),
            )
            unexpected_function = cur.fetchone()
            if unexpected_function:
                raise RuntimeError(
                    "scheduler can execute an unexpected SECURITY DEFINER function: "
                    + unexpected_function[0]
                )
            cur.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database),ident))
            cur.execute("SELECT datname FROM pg_database WHERE datallowconn AND datname <> %s", (database,))
            for (other,) in cur.fetchall():
                cur.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM {}').format(sql.Identifier(other),ident))
                cur.execute('SELECT has_database_privilege(%s,%s,\'CONNECT\')', (name,other))
                if cur.fetchone()[0]:
                    raise RuntimeError('scheduler can connect to another database through public privileges')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if was_autocommit:
            conn.autocommit = True
    return {'scheduler_user':name}
