"""Shared target and schema guards for isolated recovery development loaders."""

import hashlib
import json
import subprocess
from pathlib import Path

PROJECT = "kokonut-kernel-recovery-fixture"
CONTAINER = PROJECT + "-database-1"
IMAGE = "sha256:b573e82124b3530c454ea6d5ae8aefce1fb7ee137467f66f75a5079f8569ee6b"


def query(sql, variables=None):
    command = ["docker", "exec", "-i", CONTAINER, "psql", "-X", "-qAt",
               "-v", "ON_ERROR_STOP=1", "-U", "kokonut", "-d", "kokonut_intelligence"]
    for name, value in (variables or {}).items():
        command += ["-v", f"{name}={value}"]
    return subprocess.run(command, input=sql, text=True, check=True,
                          capture_output=True).stdout



def require_fixture_database():
    root = Path(__file__).resolve().parent.parent
    container = json.loads(subprocess.run(["docker", "inspect", CONTAINER],
                                         check=True, capture_output=True, text=True).stdout)[0]
    labels = container["Config"].get("Labels", {})
    if (labels.get("com.docker.compose.project") != PROJECT
            or labels.get("com.docker.compose.service") != "database"
            or container["State"]["Status"] != "running" or container["Image"] != IMAGE
            or container["HostConfig"].get("PortBindings")
            or container["HostConfig"].get("Privileged")):
        raise RuntimeError("Require the dedicated private fixture database")
    mounts = container["Mounts"]
    if len(mounts) != 1 or mounts[0].get("Name") != PROJECT + "_fixture-postgres-data":
        raise RuntimeError("Refusing a reused or unexpected database volume")
    networks = container["NetworkSettings"]["Networks"]
    if list(networks) != [PROJECT + "_fixture"]:
        raise RuntimeError("Unexpected fixture network")
    network = json.loads(subprocess.run(["docker", "network", "inspect", *networks],
                                       check=True, capture_output=True, text=True).stdout)[0]
    if not network["Internal"]:
        raise RuntimeError("Fixture network must be internal")
    running = subprocess.run(["docker", "ps", "--filter", f"label=com.docker.compose.project={PROJECT}",
                              "--format", "{{.Names}}"], check=True, capture_output=True, text=True)
    if running.stdout.splitlines() != [CONTAINER]:
        raise RuntimeError("Stop all fixture roles except database before seeding")
    expected = {f"schema:{p.name}": hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (root / "schemas/postgres").glob("[0-9]*.sql")}
    rows = json.loads(query("BEGIN READ ONLY; SET LOCAL statement_timeout='5s'; "
                            "SELECT COALESCE(json_agg(json_build_object('id',migration_id,"
                            "'checksum',checksum,'status',status)), '[]'::json) "
                            "FROM schema_migration WHERE migration_id LIKE 'schema:%'; COMMIT;"))
    actual = {r["id"]: r["checksum"] for r in rows if r["status"] == "applied"}
    if not expected or actual != expected or len(rows) != len(expected):
        raise RuntimeError("Bundled migration inventory does not match fixture database")
    return root, len(expected)
