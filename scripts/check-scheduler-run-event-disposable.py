"""Verify the bounded scheduler event contract on network-disabled PostgreSQL."""
import pathlib
import subprocess
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
name = 'scheduler-event-test-' + uuid.uuid4().hex[:12]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)


def sql(statement):
    return run('docker', 'exec', '-i', name, 'psql', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1', input=statement)


try:
    run('docker', 'run', '-d', '--rm', '--network', 'none', '--name', name,
        '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:16-alpine')
    for attempt in range(120):
        if subprocess.run(['docker','exec',name,'pg_isready','-U','postgres'], capture_output=True).returncode == 0:
            break
        time.sleep(.25)
    else:
        raise RuntimeError('temporary PostgreSQL not ready')
    sql('CREATE ROLE kokonut_runtime NOLOGIN; CREATE TABLE task_run(id uuid PRIMARY KEY,task_id uuid,status text,completed_at timestamptz,duration_ms integer,worker_id text); CREATE TABLE platform_event(id uuid PRIMARY KEY,event_type text,source_table text,source_id uuid,payload jsonb,priority text);')
    migration = (ROOT/'schemas/postgres/747_scheduler_run_event_boundary.sql').read_text()
    sql(migration)
    sql(migration)
    run_id, task_id = str(uuid.uuid4()), str(uuid.uuid4())
    sql(f"INSERT INTO task_run VALUES ('{run_id}','{task_id}','completed',now(),42,'executor');")
    first = sql(f"SET ROLE kokonut_scheduler_login; SELECT kokonut_security.enqueue_scheduler_run_event('{run_id}','executor');").stdout
    second = sql(f"SET ROLE kokonut_scheduler_login; SELECT kokonut_security.enqueue_scheduler_run_event('{run_id}','executor');").stdout
    assert first == second
    assert sql('SELECT count(*) FROM platform_event;').stdout.splitlines()[2].strip() == '1'
    for statement in [
        f"SELECT kokonut_security.enqueue_scheduler_run_event('{run_id}','wrong');",
        "INSERT INTO platform_event(id) VALUES(gen_random_uuid());",
        'SELECT * FROM kokonut_security.scheduler_run_event_receipt;',
    ]:
        try:
            sql('SET ROLE kokonut_scheduler_login; '+statement)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError('restricted operation unexpectedly succeeded')
    rolled_back_run = str(uuid.uuid4())
    sql(f"BEGIN; INSERT INTO task_run VALUES ('{rolled_back_run}','{task_id}','completed',now(),1,'executor'); SELECT kokonut_security.enqueue_scheduler_run_event('{rolled_back_run}','executor'); ROLLBACK;")
    assert sql('SELECT count(*) FROM platform_event;').stdout.splitlines()[2].strip() == '1'
    running_id = str(uuid.uuid4())
    sql(f"INSERT INTO task_run VALUES ('{running_id}','{task_id}','running',NULL,NULL,'executor');")
    try:
        sql(f"SET ROLE kokonut_scheduler_login; SELECT kokonut_security.enqueue_scheduler_run_event('{running_id}','executor');")
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError('running run emitted a terminal event')
    print('Scheduler event migration replay, idempotency and denied direct access passed')
finally:
    subprocess.run(['docker','rm','-f',name],capture_output=True)
