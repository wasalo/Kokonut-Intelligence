import hashlib
import json
from pathlib import Path

import pytest

from services.migration import runtime_role


def test_runtime_acl_policy_matches_all_recorded_migration_revokes():
    root = Path(__file__).resolve().parents[1]
    source = (root / "services/migration/runtime_role.py").read_bytes()
    report = json.loads(
        (
            root
            / "docs/refactor/builds/2026-10-26-recovery/"
            "sprint-runtime-privilege-callsite-report.json"
        ).read_text()
    )

    assert set(runtime_role._RUNTIME_PRIVATE_TABLES).isdisjoint(
        runtime_role._RUNTIME_MUTATION_TABLES
    )
    assert report["runtime_role_policy_source"]["sha256"] == hashlib.sha256(
        source
    ).hexdigest()
    assert report["summary"][
        "migration_revoked_relations_missing_or_mismatched_runtime_policy"
    ] == 0
    assert report["summary"]["migration_revoked_relations_with_runtime_policy"] == 91
    assert report["migration_revoked_relations_missing_or_mismatched_runtime_policy"] == []


def test_runtime_scoped_denials_follow_compatibility_table_grant():
    source = (
        Path(__file__).resolve().parents[1] / "services/migration/runtime_role.py"
    ).read_text()
    broad_grant = source.index(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public"
    )
    scoped_reapply = source.index(
        "scoped_write_grants = _apply_scoped_write_boundary("
    )
    scoped_verification = source.index("_verify_scoped_write_boundary(cur, runtime_user)")

    assert broad_grant < scoped_reapply < scoped_verification


def test_mobile_credential_columns_are_excluded_from_runtime_reads():
    assert "device_token_hash" not in runtime_role._MOBILE_DEVICE_READ_COLUMNS
    assert "push_token" not in runtime_role._MOBILE_DEVICE_READ_COLUMNS
    assert "code_hash" not in runtime_role._MOBILE_ENROLLMENT_READ_COLUMNS
    assert runtime_role._MOBILE_CREDENTIAL_COLUMNS == {
        "mobile_device": ("device_token_hash", "push_token"),
        "mobile_device_enrollment": ("code_hash",),
    }


def test_runtime_mobile_writes_match_current_handler_call_sites():
    assert runtime_role._MOBILE_DEVICE_UPDATE_COLUMNS == (
        "updated_at",
        "last_seen_at",
        "last_sync_at",
    )
    assert runtime_role._MOBILE_ENROLLMENT_INSERT_COLUMNS == (
        "code_hash",
        "user_id",
        "location_id",
        "tenant_organization_id",
        "created_by",
        "expires_at",
    )
    assert runtime_role._MOBILE_ENROLLMENT_UPDATE_COLUMNS == ("revoked_at",)


def test_runtime_provisioner_rebuilds_operator_function_acl_after_restore():
    source = (Path(__file__).resolve().parents[1] / "services/migration/runtime_role.py").read_text()

    assert 'REVOKE ALL ON FUNCTION {} FROM PUBLIC' in source
    assert 'REVOKE ALL ON FUNCTION {} FROM {}' in source
    assert 'GRANT EXECUTE ON FUNCTION {} TO {}' in source
    assert "_PRIVATE_RUNTIME_FUNCTIONS" in source
    assert "aclexplode" in source
    assert "acl_entry.grantee = 0" in source


def test_mobile_credential_functions_are_private_to_the_runtime_login():
    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/418_mobile_credential_function_acl.sql"
    ).read_text()

    assert set(runtime_role._MOBILE_CREDENTIAL_FUNCTIONS).issubset(
        runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    )
    assert migration.count("REVOKE ALL ON FUNCTION") == 4
    assert migration.count("FROM PUBLIC") == 4
    assert migration.count("TO kokonut_runtime") == 4
    assert "GRANT EXECUTE ON FUNCTION {} TO {}" in (
        Path(__file__).resolve().parents[1]
        / "services/migration/runtime_role.py"
    ).read_text()


def test_worker_context_helpers_are_private_to_worker_execution():
    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/419_private_worker_context_functions.sql"
    ).read_text()

    assert runtime_role._WORKER_CONTEXT_FUNCTION in runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    assert runtime_role._WORKER_SCOPE_FUNCTION in runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    assert migration.count("FROM PUBLIC") == 3
    assert migration.count("TO kokonut_worker_execution") == 3
    assert "kokonut_runtime" in migration
    assert "kokonut_worker_context_owner" in migration


def test_notification_enqueue_login_is_removed_from_both_sides_of_role_memberships():
    class Cursor:
        def __init__(self):
            self.calls = []
            self.result_rows = []

        def execute(self, statement, parameters=None):
            statement_text = str(statement)
            self.calls.append((statement_text, parameters))
            if "WHERE member.rolname = %s" in statement_text:
                self.result_rows = [("kokonut_worker_execution",)]
            elif "WHERE granted.rolname = %s" in statement_text:
                self.result_rows = [("unexpected_consumer",)]
            else:
                self.result_rows = []

        def fetchall(self):
            return self.result_rows

    cursor = Cursor()
    login = runtime_role.sql.Identifier("kokonut_notification_enqueue_login")

    runtime_role._remove_role_memberships(
        cursor,
        role_name="kokonut_notification_enqueue_login",
        identifier=login,
    )

    statements = [statement for statement, _ in cursor.calls]
    assert len(statements) == 4
    assert "REVOKE" in statements[1]
    assert "kokonut_worker_execution" in statements[1]
    assert "REVOKE" in statements[3]
    assert "kokonut_notification_enqueue_login" in statements[3]
    assert "unexpected_consumer" in statements[3]


def test_notification_enqueue_provisioning_requires_a_paired_secret_and_distinct_owner():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }
    with pytest.raises(ValueError, match="provided together"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            notification_enqueue_user="kokonut_notification_enqueue_login",
        )
    with pytest.raises(ValueError, match="differ from the notification function owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            notification_enqueue_user="kokonut_notification_enqueue_owner",
            notification_enqueue_password="n" * 32,
        )


def test_market_data_login_requires_its_paired_secret_and_distinct_function_owner():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }
    with pytest.raises(ValueError, match="market-data user and password must be provided together"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            market_data_user="kokonut_market_data_login",
        )
    with pytest.raises(ValueError, match="differ from the market-data function owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            market_data_user="kokonut_market_data_owner",
            market_data_password="m" * 32,
        )


def test_eas_indexer_login_requires_its_paired_secret_and_distinct_function_owner():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }
    with pytest.raises(ValueError, match="EAS-indexer user and password must be provided together"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            eas_indexer_user="kokonut_eas_indexer_login",
        )
    with pytest.raises(ValueError, match="differ from the EAS-indexer function owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            eas_indexer_user="kokonut_eas_indexer_owner",
            eas_indexer_password="e" * 32,
        )


def test_eas_indexer_login_uses_only_its_bounded_database_functions():
    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/433_isolated_eas_indexer.sql"
    ).read_text()
    runtime_source = (
        Path(__file__).resolve().parents[1]
        / "services/migration/runtime_role.py"
    ).read_text()

    assert len(runtime_role._EAS_INDEXER_FUNCTIONS) == 7
    assert set(runtime_role._EAS_INDEXER_FUNCTIONS) <= set(runtime_role._PRIVATE_RUNTIME_FUNCTIONS)
    assert all(
        (function, "kokonut_eas_indexer_owner") in runtime_role._SECURITY_DEFINER_OWNERS
        for function in runtime_role._EAS_INDEXER_FUNCTIONS
    )
    assert "session_user <> 'kokonut_eas_indexer_login'" in migration
    assert "EAS-indexer login retains direct relation privileges" in runtime_source
    assert "runtime role can execute EAS-indexer worker functions" in runtime_source


def test_rpc_indexer_login_requires_its_paired_secret_and_owns_only_bounded_functions():
    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/436_isolated_rpc_indexer.sql"
    ).read_text()
    runtime_source = (
        Path(__file__).resolve().parents[1]
        / "services/migration/runtime_role.py"
    ).read_text()
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }

    with pytest.raises(ValueError, match="RPC-indexer user and password must be provided together"):
        runtime_role.provision_runtime_role(
            None, **common, rpc_indexer_user="kokonut_rpc_indexer_login"
        )
    with pytest.raises(ValueError, match="differ from the RPC-indexer function owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            rpc_indexer_user="kokonut_rpc_indexer_owner",
            rpc_indexer_password="r" * 32,
        )

    assert len(runtime_role._RPC_INDEXER_FUNCTIONS) == 5
    assert set(runtime_role._RPC_INDEXER_FUNCTIONS) <= set(runtime_role._PRIVATE_RUNTIME_FUNCTIONS)
    assert all(
        (function, "kokonut_rpc_indexer_owner") in runtime_role._SECURITY_DEFINER_OWNERS
        for function in runtime_role._RPC_INDEXER_FUNCTIONS
    )
    assert "session_user <> 'kokonut_rpc_indexer_login'" in migration
    assert "RPC-indexer login retains direct relation privileges" in runtime_source
    assert "runtime role can execute RPC-indexer worker functions" in runtime_source


def test_market_data_function_is_private_and_owned_by_its_bounded_role():
    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/430_isolated_market_data_worker.sql"
    ).read_text()

    assert runtime_role._MARKET_DATA_FUNCTION in runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    assert (runtime_role._MARKET_DATA_FUNCTION, "kokonut_market_data_owner") in (
        runtime_role._SECURITY_DEFINER_OWNERS
    )
    assert "session_user <> 'kokonut_market_data_login'" in migration
    assert "REVOKE ALL ON FUNCTION" in migration
    assert "FROM PUBLIC" in migration
    assert "TO kokonut_market_data_login" in migration
    assert "REVOKE ALL (%s) ON TABLE public.%I FROM %I" in migration
    assert "market-data login must connect only to its configured database" in (
        Path(__file__).resolve().parents[1]
        / "services/migration/runtime_role.py"
    ).read_text()


def test_gnosis_indexer_has_its_own_execute_only_role_contract():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "schemas/postgres/643_isolated_gnosis_moloch_indexer.sql").read_text()
    runtime_source = (root / "services/migration/runtime_role.py").read_text()

    assert len(runtime_role._GNOSIS_INDEXER_FUNCTIONS) == 12
    assert set(runtime_role._GNOSIS_INDEXER_FUNCTIONS) <= set(
        runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    )
    assert all(
        (function, "kokonut_gnosis_indexer_owner")
        in runtime_role._SECURITY_DEFINER_OWNERS
        for function in runtime_role._GNOSIS_INDEXER_FUNCTIONS
    )
    assert "session_user <> 'kokonut_gnosis_indexer_login'" in migration
    assert "FROM PUBLIC" in migration
    assert "TO kokonut_gnosis_indexer_login" in migration
    assert "{label} login retains direct relation privileges" in runtime_source
    assert "migration 643 Gnosis-indexer functions" in runtime_source


def test_baal_indexer_has_its_own_execute_only_role_contract():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "schemas/postgres/644_isolated_baal_indexer.sql").read_text()
    runtime_source = (root / "services/migration/runtime_role.py").read_text()

    assert len(runtime_role._BAAL_INDEXER_FUNCTIONS) == 7
    assert set(runtime_role._BAAL_INDEXER_FUNCTIONS) <= set(
        runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    )
    assert all(
        (function, "kokonut_baal_indexer_owner")
        in runtime_role._SECURITY_DEFINER_OWNERS
        for function in runtime_role._BAAL_INDEXER_FUNCTIONS
    )
    assert "session_user <> 'kokonut_baal_indexer_login'" in migration
    assert "FROM PUBLIC" in migration
    assert "TO kokonut_baal_indexer_login" in migration
    assert "migration 644 Baal-indexer functions" in runtime_source
    assert "Baal-indexer login must connect only to its configured database" in runtime_source


def test_baal_indexer_provisioning_requires_paired_credentials_and_distinct_owner():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }
    with pytest.raises(ValueError, match="Baal-indexer user and password must be provided together"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            baal_indexer_user="kokonut_baal_indexer_login",
        )
    with pytest.raises(ValueError, match="differ from the Baal-indexer function owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            baal_indexer_user="kokonut_baal_indexer_owner",
            baal_indexer_password="b" * 32,
        )


def test_freshness_worker_has_an_execute_only_role_contract():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "schemas/postgres/645_isolated_data_freshness_worker.sql").read_text()
    runtime_source = (root / "services/migration/runtime_role.py").read_text()

    assert len(runtime_role._FRESHNESS_WORKER_FUNCTIONS) == 9
    assert set(runtime_role._FRESHNESS_WORKER_FUNCTIONS) <= set(
        runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    )
    assert all(
        (function, "kokonut_freshness_owner")
        in runtime_role._SECURITY_DEFINER_OWNERS
        for function in runtime_role._FRESHNESS_WORKER_FUNCTIONS
    )
    assert "session_user <> 'kokonut_freshness_login'" in migration
    assert "FROM PUBLIC" in migration
    assert "TO kokonut_freshness_login" in migration
    assert "migration 645 freshness-worker functions" in runtime_source
    assert "freshness-worker login must connect only to its configured database" in runtime_source


def test_freshness_worker_matches_canonical_date_only_source_columns():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "schemas/postgres/645_isolated_data_freshness_worker.sql").read_text()
    market_schema = (root / "schemas/postgres/010_market_data.sql").read_text()
    environment_schema = (root / "schemas/postgres/005_environmental.sql").read_text()
    marketplace_migration = (root / "schemas/postgres/142_marketplace.sql").read_text()

    assert "price_date DATE NOT NULL" in market_schema
    assert "ADD COLUMN IF NOT EXISTS location_id UUID REFERENCES location(id)" in marketplace_migration
    assert "GRANT SELECT (location_id, price_date) ON public.price_observation" in migration
    assert "max(observation.price_date)::TIMESTAMP AT TIME ZONE 'UTC'" in migration
    assert "max(observation.observation_date)::TIMESTAMP AT TIME ZONE 'UTC'" in migration
    assert "observation.observation_date) INTO latest_at" not in migration
    assert "observation_date DATE NOT NULL" in environment_schema


def test_freshness_worker_provisioning_requires_paired_credentials_and_distinct_owner():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }
    with pytest.raises(ValueError, match="freshness worker user and password must be provided together"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            freshness_user="kokonut_freshness_login",
        )
    with pytest.raises(ValueError, match="differ from the freshness function owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            freshness_user="kokonut_freshness_owner",
            freshness_password="f" * 32,
        )


def test_clickhouse_outbox_worker_has_only_bounded_claim_and_completion_functions():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "schemas/postgres/646_isolated_clickhouse_outbox_worker.sql").read_text()
    runtime_source = (root / "services/migration/runtime_role.py").read_text()

    assert len(runtime_role._CLICKHOUSE_OUTBOX_WORKER_FUNCTIONS) == 2
    assert set(runtime_role._CLICKHOUSE_OUTBOX_WORKER_FUNCTIONS) <= set(
        runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    )
    assert all(
        (function, "kokonut_clickhouse_outbox_owner")
        in runtime_role._SECURITY_DEFINER_OWNERS
        for function in runtime_role._CLICKHOUSE_OUTBOX_WORKER_FUNCTIONS
    )
    assert "session_user <> 'kokonut_clickhouse_outbox_login'" in migration
    assert "FOR UPDATE SKIP LOCKED" in migration
    assert "lease_token = gen_random_uuid()" in migration
    assert "lease_expires_at > NOW()" in migration
    assert "TO kokonut_clickhouse_outbox_login" in migration
    assert "migration 646 ClickHouse outbox functions" in runtime_source


def test_clickhouse_outbox_worker_provisioning_requires_paired_credentials_and_distinct_owner():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }
    with pytest.raises(ValueError, match="ClickHouse outbox user and password must be provided together"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            clickhouse_outbox_user="kokonut_clickhouse_outbox_login",
        )
    with pytest.raises(ValueError, match="differ from the ClickHouse outbox function owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            clickhouse_outbox_user="kokonut_clickhouse_outbox_owner",
            clickhouse_outbox_password="c" * 32,
        )


def test_notification_delivery_has_only_bounded_attempt_functions():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "schemas/postgres/647_isolated_notification_delivery_worker.sql").read_text()
    runtime_source = (root / "services/migration/runtime_role.py").read_text()

    assert len(runtime_role._NOTIFICATION_DELIVERY_FUNCTIONS) == 2
    assert set(runtime_role._NOTIFICATION_DELIVERY_FUNCTIONS) <= set(
        runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    )
    assert all(
        (function, "kokonut_notification_delivery_owner")
        in runtime_role._SECURITY_DEFINER_OWNERS
        for function in runtime_role._NOTIFICATION_DELIVERY_FUNCTIONS
    )
    assert "FOR UPDATE SKIP LOCKED" in migration
    assert "notification_outbox_attempt" in migration
    assert "session_user <> 'kokonut_notification_delivery_login'" in migration
    assert "public.notification_outbox_attempt FROM PUBLIC" in migration
    assert "FROM PUBLIC" in migration
    assert "TO kokonut_notification_delivery_login" in migration
    assert "migration 647 notification-delivery functions" in runtime_source


def test_notification_delivery_provisioning_requires_paired_credentials_and_distinct_owner():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }
    with pytest.raises(ValueError, match="notification-delivery user and password must be provided together"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            notification_delivery_user="kokonut_notification_delivery_login",
        )
    with pytest.raises(ValueError, match="differ from the notification-delivery function owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            notification_delivery_user="kokonut_notification_delivery_owner",
            notification_delivery_password="n" * 32,
        )
def test_global_indexer_logins_receive_only_configured_database_connect_grants():
    source = (
        Path(__file__).resolve().parents[1]
        / "services/migration/runtime_role.py"
    ).read_text()
    protected_login_block = source.split("protected_login_idents = [runtime_ident, auth_ident]", 1)[1]
    protected_login_block = protected_login_block.split("for name in database_names:", 1)[0]

    for role_identifier in (
        "rpc_indexer_ident",
        "gnosis_indexer_ident",
        "baal_indexer_ident",
    ):
        assert f"if {role_identifier} is not None:" in protected_login_block
        assert f"protected_login_idents.append({role_identifier})" in protected_login_block

    assert '"GRANT CONNECT ON DATABASE {} TO {}"' in source


def test_baal_indexer_dedicated_secret_stays_outside_worker_compose_profiles():
    root = Path(__file__).resolve().parents[1]
    bootstrap = (root / "docker-compose.kernel-runtime-role.yml").read_text()
    app_profiles = "\n".join(
        (root / name).read_text()
        for name in (
            "docker-compose.kernel-candidate.yml",
            "docker-compose.kernel-portability.yml",
            "docker-compose.kernel-standard.yml",
            "docker-compose.worker.yml",
        )
    )

    assert "KOKONUT_BAAL_INDEXER_PASSWORD" in bootstrap
    assert "KOKONUT_BAAL_INDEXER_DATABASE_URL" in app_profiles
    assert "KOKONUT_BAAL_INDEXER_RPC_ENDPOINT" in app_profiles
    assert "KOKONUT_FEATURE_ISOLATED_BAAL_INDEXER_WORKER" in app_profiles
    assert "KOKONUT_BAAL_INDEXER_PASSWORD" not in app_profiles


def test_market_data_dedicated_secret_reaches_only_the_runtime_role_bootstrap():
    root = Path(__file__).resolve().parents[1]
    bootstrap = (root / "docker-compose.kernel-runtime-role.yml").read_text()
    app_profiles = "\n".join(
        (root / name).read_text()
        for name in (
            "docker-compose.kernel-portability.yml",
            "docker-compose.kernel-standard.yml",
        )
    )

    assert "KOKONUT_MARKET_DATA_PASSWORD: ${KOKONUT_MARKET_DATA_PASSWORD:-}" in bootstrap
    assert "KOKONUT_MARKET_DATA_DATABASE_URL" in app_profiles
    assert "KOKONUT_FEATURE_ISOLATED_MARKET_DATA_WORKER" in app_profiles
    assert "KOKONUT_MARKET_DATA_PASSWORD" not in app_profiles


def test_sensor_ingestion_login_requires_its_paired_secret_and_distinct_function_owner():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }
    with pytest.raises(ValueError, match="sensor-ingestion user and password must be provided together"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            sensor_ingestion_user="kokonut_sensor_ingestion_login",
        )
    with pytest.raises(ValueError, match="differ from the sensor-ingestion function owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            sensor_ingestion_user="kokonut_sensor_ingestion_owner",
            sensor_ingestion_password="s" * 32,
        )


def test_sensor_ingestion_functions_are_private_and_owned_by_the_bounded_role():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "schemas/postgres/431_signed_sensor_driver_worker.sql").read_text()
    runtime_source = (root / "services/migration/runtime_role.py").read_text()

    assert set(runtime_role._SENSOR_INGESTION_FUNCTIONS) <= set(runtime_role._PRIVATE_RUNTIME_FUNCTIONS)
    assert all(
        (function, "kokonut_sensor_ingestion_owner") in runtime_role._SECURITY_DEFINER_OWNERS
        for function in runtime_role._SENSOR_INGESTION_FUNCTIONS
    )
    assert "session_user <> 'kokonut_sensor_ingestion_login'" in migration
    assert "GRANT kokonut_worker_execution TO kokonut_sensor_ingestion_login" in migration
    assert "REVOKE ALL (%s) ON TABLE public.%I FROM %I" in migration
    assert "sensor-ingestion login must connect only to its configured database" in runtime_source


def test_sensor_ingestion_password_is_bootstrap_only_and_worker_secrets_are_routed_explicitly():
    root = Path(__file__).resolve().parents[1]
    bootstrap = (root / "docker-compose.kernel-runtime-role.yml").read_text()
    app_profiles = "\n".join(
        (root / name).read_text()
        for name in (
            "docker-compose.kernel-portability.yml",
            "docker-compose.kernel-standard.yml",
        )
    )

    assert "KOKONUT_SENSOR_INGESTION_PASSWORD" in bootstrap
    assert "KOKONUT_SENSOR_INGESTION_DATABASE_URL" in app_profiles
    assert "KOKONUT_SENSOR_INGESTION_WORKER_CREDENTIAL" in app_profiles
    assert "KOKONUT_FEATURE_SIGNED_SENSOR_INGESTION_WORKER" in app_profiles
    assert "KOKONUT_SENSOR_INGESTION_PASSWORD" not in app_profiles


def test_remote_sensing_login_requires_its_paired_secret_and_distinct_owner():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }
    with pytest.raises(ValueError, match="remote-sensing user and password must be provided together"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            remote_sensing_user="kokonut_remote_sensing_login",
        )
    with pytest.raises(ValueError, match="differ from the remote-sensing function owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            remote_sensing_user="kokonut_remote_sensing_owner",
            remote_sensing_password="r" * 32,
        )


def test_remote_sensing_login_uses_only_the_signed_worker_function_boundary():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "schemas/postgres/432_signed_remote_sensing_worker.sql").read_text()
    runtime_source = (root / "services/migration/runtime_role.py").read_text()

    assert set(runtime_role._REMOTE_SENSING_FUNCTIONS) <= set(
        runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    )
    assert all(
        (function, "kokonut_remote_sensing_owner") in runtime_role._SECURITY_DEFINER_OWNERS
        for function in runtime_role._REMOTE_SENSING_FUNCTIONS
    )
    assert "session_user <> 'kokonut_remote_sensing_login'" in migration
    assert "GRANT kokonut_worker_execution TO kokonut_remote_sensing_login" in migration
    assert "WITH INHERIT FALSE, SET TRUE" in runtime_source
    assert "remote-sensing login retains application relation access" in runtime_source
    assert "runtime role can execute remote-sensing worker functions" in runtime_source


def test_sensor_anomaly_ml_source_login_requires_paired_secret_and_distinct_reader_roles():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut",
        "admin_password": "admin-password",
        "runtime_user": "kokonut_runtime",
        "runtime_password": "runtime-password",
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "operator-password",
    }
    with pytest.raises(
        ValueError, match="sensor-anomaly ML source user and password must be provided together"
    ):
        runtime_role.provision_runtime_role(
            None,
            **common,
            sensor_anomaly_ml_source_user="kokonut_sensor_anomaly_ml_source_login",
        )
    with pytest.raises(ValueError, match="differ from the sensor-anomaly ML view owner"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            sensor_anomaly_ml_source_user="kokonut_sensor_anomaly_ml_source_view_owner",
            sensor_anomaly_ml_source_password="m" * 32,
        )
    with pytest.raises(ValueError, match="differ from the sensor-anomaly ML reader role"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            sensor_anomaly_ml_source_user="kokonut_sensor_anomaly_ml_reader",
            sensor_anomaly_ml_source_password="m" * 32,
        )


def test_sensor_anomaly_ml_source_role_uses_only_signed_view_access():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "schemas/postgres/650_signed_sensor_anomaly_ml_source.sql").read_text()
    runtime_source = (root / "services/migration/runtime_role.py").read_text()
    worker_source = (root / "services/ingestion/sensor_anomaly_ml_worker.py").read_text()

    assert "GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context" in migration
    assert "CREATE OR REPLACE VIEW kokonut_anomaly_ml_source.sensor_reading" in migration
    assert "current_worker_scope('sensor_anomaly_ml', 'analyze')" in migration
    assert "TO kokonut_sensor_anomaly_ml_reader" in migration
    assert "GRANT kokonut_worker_execution TO kokonut_sensor_anomaly_ml_source_login" not in migration
    assert "migration 650 sensor-anomaly ML source view and reader role" in runtime_source
    assert "GRANT kokonut_sensor_anomaly_ml_reader TO {}" in runtime_source
    assert "SET LOCAL ROLE kokonut_sensor_anomaly_ml_reader" in worker_source
    assert "from services.ingestion.base import get_db" not in worker_source


def test_remote_sensing_password_is_bootstrap_only():
    root = Path(__file__).resolve().parents[1]
    bootstrap = (root / "docker-compose.kernel-runtime-role.yml").read_text()
    app_profiles = "\n".join(
        (root / name).read_text()
        for name in (
            "docker-compose.kernel-portability.yml",
            "docker-compose.kernel-standard.yml",
        )
    )

    assert "KOKONUT_REMOTE_SENSING_PASSWORD: ${KOKONUT_REMOTE_SENSING_PASSWORD:-}" in bootstrap
    assert "KOKONUT_REMOTE_SENSING_DATABASE_URL" in app_profiles
    assert "KOKONUT_REMOTE_SENSING_WORKER_CREDENTIAL" in app_profiles
    assert "KOKONUT_REMOTE_SENSING_PASSWORD" not in app_profiles


def test_runtime_api_key_access_is_read_only_and_column_scoped():
    assert runtime_role._API_KEY_COLUMNS == (
        "id",
        "key_hash",
        "key_prefix",
        "role_id",
        "scopes",
        "expires_at",
        "is_active",
    )

    class Cursor:
        def __init__(self):
            self.calls = []

        def execute(self, statement, parameters=None):
            self.calls.append((statement, parameters))

        def fetchall(self):
            return [(column,) for column in (
                *runtime_role._API_KEY_COLUMNS,
                "name",
                "last_used_at",
                "created_at",
                "created_by",
            )]

    cursor = Cursor()
    result = runtime_role._apply_api_key_boundary(
        cursor,
        runtime_role.sql.Identifier("kokonut_runtime"),
    )

    statements = [statement for statement, _ in cursor.calls]
    # One schema inspection, one table revoke, three column revokes per column,
    # then one narrow SELECT grant.
    assert len(statements) == 1 + 1 + 3 * 11 + 1
    assert result["select"] == list(runtime_role._API_KEY_COLUMNS)
    assert result["insert"] == []
    assert result["update"] == []
    assert result["delete"] is False


def test_runtime_solution_stage_gate_access_is_only_through_bounded_functions():
    class Cursor:
        def __init__(self):
            self.calls = []

        def execute(self, statement, parameters=None):
            self.calls.append((statement, parameters))

        def fetchone(self):
            return ("solution_stage_gate",)

        def fetchall(self):
            return [(column,) for column in ("id", "requirements", "status")]

    cursor = Cursor()
    result = runtime_role._apply_solution_stage_gate_boundary(
        cursor,
        runtime_role.sql.Identifier("kokonut_runtime"),
    )

    assert result == {
        "installed": True,
        "select": False,
        "insert": False,
        "update": False,
        "delete": False,
        "access": "bounded security-definer functions only",
    }
    assert len(cursor.calls) == 3 + 3 * 3


def test_runtime_solution_experiment_protocol_boundary_preserves_only_lifecycle_updates():
    class Cursor:
        def __init__(self):
            self.calls = []
            self.fetches = 0

        def execute(self, statement, parameters=None):
            self.calls.append((statement, parameters))

        def fetchone(self):
            self.fetches += 1
            return ("solution_experiment",)

        def fetchall(self):
            return [(column,) for column in (
                "id", "hypothesis", "solution_id", "status", "approved_by_party_id",
                "approved_at", "started_at", "completed_at", "updated_at",
            )]

    cursor = Cursor()
    result = runtime_role._apply_solution_experiment_protocol_boundary(
        cursor,
        runtime_role.sql.Identifier("kokonut_runtime"),
    )

    assert result["installed"] is True
    assert result["insert"] is False
    assert result["delete"] is False
    assert result["protocol_update"] is False
    assert result["lifecycle_update_columns"] == [
        "status", "approved_by_party_id", "approved_at", "started_at",
        "completed_at", "updated_at",
    ]
    assert len(cursor.calls) == 4 + 2 * 9


@pytest.mark.parametrize(
    "privileges,should_raise",
    [
        ((False, False, False, False, True, True, True, True, True, True), False),
        ((True, False, False, False, True, True, True, True, True, True), True),
        ((False, True, False, False, True, True, True, True, True, True), True),
        ((False, False, True, False, True, True, True, True, True, True), True),
        ((False, False, False, True, True, True, True, True, True, True), True),
        ((False, False, False, False, True, True, True, True, True, False), True),
    ],
)
def test_runtime_solution_experiment_protocol_privilege_verification(
    privileges, should_raise
):
    class Cursor:
        def __init__(self):
            self.fetches = 0

        def execute(self, _statement, _parameters=None):
            return None

        def fetchone(self):
            self.fetches += 1
            if self.fetches == 1:
                return ("solution_experiment",)
            return privileges

    cursor = Cursor()
    if should_raise:
        with pytest.raises(
            RuntimeError, match="retains direct solution_experiment protocol privileges"
        ):
            runtime_role._verify_solution_experiment_protocol_boundary(
                cursor, "kokonut_runtime"
            )
    else:
        runtime_role._verify_solution_experiment_protocol_boundary(
            cursor, "kokonut_runtime"
        )


@pytest.mark.parametrize(
    "privileges,should_raise",
    [
        ((False, False, False, False, False), False),
        ((True, False, False, False, False), True),
        ((False, False, True, False, False), True),
        ((False, False, False, False, True), True),
    ],
)
def test_runtime_solution_stage_gate_privilege_verification(privileges, should_raise):
    class Cursor:
        def __init__(self):
            self.fetches = 0

        def execute(self, _statement, _parameters=None):
            return None

        def fetchone(self):
            self.fetches += 1
            if self.fetches == 1:
                return ("solution_stage_gate",)
            return privileges

    cursor = Cursor()
    if should_raise:
        with pytest.raises(RuntimeError, match="retains direct solution_stage_gate privileges"):
            runtime_role._verify_solution_stage_gate_boundary(cursor, "kokonut_runtime")
    else:
        runtime_role._verify_solution_stage_gate_boundary(cursor, "kokonut_runtime")
