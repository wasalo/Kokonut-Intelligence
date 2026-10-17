from pathlib import Path

import pytest

from services.migration import runtime_role


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
