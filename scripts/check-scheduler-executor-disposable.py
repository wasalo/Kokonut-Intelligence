"""Exercise the real scheduler engine under its restricted role on disposable PG."""
import pathlib
import subprocess
import sys
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]


def client():
    import psycopg2

    from services.migration.scheduler_role import provision_scheduler_role
    from services.scheduler.engine import SchedulerEngine

    admin = psycopg2.connect(host='127.0.0.1', user='postgres', dbname='postgres')
    with admin.cursor() as cur:
        cur.execute('REVOKE CONNECT ON DATABASE template1 FROM PUBLIC')
        cur.execute('CREATE TABLE schema_migration(migration_id text,checksum text,status text)')
        cur.execute((ROOT/'schemas/postgres/116_event_bus.sql').read_text().split('-- Seed default event')[0])
        cur.execute('ALTER TABLE platform_event ADD COLUMN lease_expires_at timestamptz')
        cur.execute('CREATE TABLE notification_outbox(status text,lease_expires_at timestamptz,available_at timestamptz)')
        for number in ('117','164','337','371','747','748'):
            path = next((ROOT/'schemas/postgres').glob(number+'_*.sql'))
            cur.execute(path.read_text())
    admin.commit()
    password = 'synthetic-scheduler-password-0123456789'
    with admin.cursor() as cur:
        cur.execute("""CREATE FUNCTION kokonut_security.unreviewed_scheduler_probe()
            RETURNS text LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog
            AS $$ SELECT 'not approved'::text $$""")
    admin.commit()
    try:
        provision_scheduler_role(admin, database='postgres', password=password)
    except RuntimeError as exc:
        assert 'unexpected SECURITY DEFINER function' in str(exc)
    else:
        raise AssertionError('scheduler provisioning accepted a PUBLIC callable SECURITY DEFINER function')
    with admin.cursor() as cur:
        cur.execute('REVOKE EXECUTE ON FUNCTION kokonut_security.unreviewed_scheduler_probe() FROM PUBLIC')
    admin.commit()
    provision_scheduler_role(admin, database='postgres', password=password)
    admin.autocommit = True
    provision_scheduler_role(admin, database='postgres', password=password)
    assert admin.autocommit
    admin.autocommit = False
    with admin.cursor() as cur:
        cur.execute("INSERT INTO scheduled_task(name,module_path,cron_expression,next_run_at) VALUES('fixture','services.metrics.noi_snapshot_worker','* * * * *',now()-interval '1 minute') RETURNING id")
        task_id = cur.fetchone()[0]
    admin.commit()
    connection = psycopg2.connect(host='127.0.0.1', user='kokonut_scheduler_login', dbname='postgres')
    engine = SchedulerEngine(connection, worker_id='fixture-executor')
    claim = engine._claim_next()
    assert claim and str(claim[1]) == str(task_id)
    assert engine._resources.acquire('db_connection')
    engine._resources.release('db_connection')
    engine._complete_task(task_id, claim[0], 'completed', 42)
    for statement in ["UPDATE scheduled_task SET module_path='unsafe'",'DELETE FROM task_run',
                      'UPDATE task_resource SET max_concurrent=100',
                      "INSERT INTO platform_event(event_type) VALUES('forged')",
                      'SELECT payload FROM platform_event']:
        try:
            with connection.cursor() as cur:
                cur.execute(statement)
        except psycopg2.errors.InsufficientPrivilege:
            connection.rollback()
        else:
            raise AssertionError('restricted operation succeeded: '+statement)
    from services.core.worker_progress import _progress_sql
    with connection.cursor() as cur:
        cur.execute(_progress_sql(('scheduler','events','notifications')), (300,))
        assert len(cur.fetchall()) == 3
    connection.rollback()
    from services.core.schema_readiness import _require_non_admin_runtime_role
    with connection.cursor() as cur:
        _require_non_admin_runtime_role(cur)
        cur.execute('SELECT migration_id,checksum,status FROM schema_migration')
    connection.rollback()
    with admin.cursor() as cur:
        cur.execute('SELECT count(*) FROM platform_event')
        assert cur.fetchone()[0] == 1
    with admin.cursor() as cur:
        cur.execute('GRANT UPDATE ON scheduled_task TO kokonut_scheduler_login')
    admin.commit()
    try:
        provision_scheduler_role(admin, database='postgres', password=password)
    except RuntimeError:
        pass
    else:
        raise AssertionError('provisioning accepted a stale broad scheduler grant')
    connection.close()
    admin.close()
    print('Restricted scheduler provisioning/reprovision, claim, resource, completion/event, health and denial checks passed')


def main():
    name = 'scheduler-executor-test-'+uuid.uuid4().hex[:12]
    try:
        subprocess.run(['docker','run','-d','--rm','--network','none','--name',name,
            '-e','POSTGRES_HOST_AUTH_METHOD=trust','postgres:16-alpine'],check=True,capture_output=True)
        for _ in range(120):
            if subprocess.run(['docker','exec',name,'pg_isready','-U','postgres'],capture_output=True).returncode == 0:
                break
            time.sleep(.25)
        else:
            raise RuntimeError('temporary database did not start')
        subprocess.run(['docker','run','--rm','--network','container:'+name,
            '-v',str(ROOT)+':/work:ro','-w','/work','-e','PYTHONPATH=/work','-e','KOKONUT_ENV=development',
            '-e','KOKONUT_ENV_SECRETS_NOT_REQUIRED=true',
            'kokonut-kernel-candidate-app:latest','python3',
            'scripts/check-scheduler-executor-disposable.py','--client'],check=True)
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True)


if __name__ == '__main__':
    if '--client' in sys.argv:
        client()
    else:
        main()
