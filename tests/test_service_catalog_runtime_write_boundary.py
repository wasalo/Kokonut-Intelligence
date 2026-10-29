"""Runtime service-catalog mutation helpers fail before opening a database."""

import pytest

from services.analytics import service_catalog


@pytest.mark.unit
@pytest.mark.parametrize(
    "operation",
    [
        lambda: service_catalog.register_service(name="runtime-added", category="support"),
        lambda: service_catalog.update_service("gateway", status="retired"),
        lambda: service_catalog.deprecate_service("gateway"),
        lambda: service_catalog.retire_service("gateway"),
    ],
    ids=("register", "update", "deprecate", "retire"),
)
def test_runtime_mutations_fail_explicitly_before_database_access(monkeypatch, operation):
    def unexpected_database_access():
        pytest.fail("deployment-managed service catalog mutation opened a database")

    monkeypatch.setattr(service_catalog, "_conn", unexpected_database_access)

    with pytest.raises(
        service_catalog.ServiceRegistryWriteDisabled,
        match="reviewed migration or seed",
    ):
        operation()
