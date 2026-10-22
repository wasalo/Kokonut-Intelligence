"""gRPC server entry point for Kokonut Intelligence."""

from __future__ import annotations

import os
import signal
from concurrent import futures

import grpc
from grpc_health.v1 import health_pb2_grpc
from grpc_reflection.v1alpha import reflection

from services.common.errors import safe_exception_class
from services.common.logging import get_logger
from services.grpc.auth import APIKeyInterceptor
from services.grpc.health import HealthServicer
from services.grpc.interceptors import LoggingInterceptor

logger = get_logger("grpc.server")

DEFAULT_MAX_MESSAGE_BYTES = 4 * 1024 * 1024
MIN_MAX_MESSAGE_BYTES = 1024
MAX_MAX_MESSAGE_BYTES = 64 * 1024 * 1024


def _configured_max_message_bytes() -> int:
    """Read a bounded inbound/outbound gRPC message-size setting."""
    raw_value = os.environ.get("GRPC_MAX_MESSAGE_BYTES", str(DEFAULT_MAX_MESSAGE_BYTES))
    if not raw_value.isascii() or not raw_value.isdecimal():
        raise ValueError("GRPC_MAX_MESSAGE_BYTES must be an integer byte count")
    value = int(raw_value)
    if not MIN_MAX_MESSAGE_BYTES <= value <= MAX_MAX_MESSAGE_BYTES:
        raise ValueError(
            f"GRPC_MAX_MESSAGE_BYTES must be between {MIN_MAX_MESSAGE_BYTES} "
            f"and {MAX_MAX_MESSAGE_BYTES}"
        )
    return value


def _get_db_pool():
    from psycopg2 import pool

    from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER
    from services.grpc.database import PooledDatabaseFactory

    min_conn = int(os.environ.get("GRPC_DB_MIN_CONN", "2"))
    max_conn = int(os.environ.get("GRPC_DB_MAX_CONN", "20"))

    connection_pool = pool.ThreadedConnectionPool(
        minconn=min_conn,
        maxconn=max_conn,
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )

    return PooledDatabaseFactory(connection_pool)


def _configured_tls_credentials():
    """Load and validate TLS material before acquiring database resources."""
    cert_path = os.environ.get("GRPC_TLS_CERT")
    key_path = os.environ.get("GRPC_TLS_KEY")
    if bool(cert_path) != bool(key_path):
        raise ValueError("Both GRPC_TLS_CERT and GRPC_TLS_KEY are required for TLS")
    if not cert_path:
        return None

    try:
        with open(cert_path, "rb") as cert_file:
            cert_chain = cert_file.read()
        with open(key_path, "rb") as key_file:
            private_key = key_file.read()
    except OSError as error:
        raise RuntimeError("gRPC TLS certificate or key file is unavailable") from error

    try:
        return grpc.ssl_server_credentials([(private_key, cert_chain)])
    except Exception as error:
        raise RuntimeError(
            f"gRPC TLS credentials are invalid ({safe_exception_class(error)})"
        ) from error


def serve():
    from services.core.adapters.grpc import require_enabled

    require_enabled()

    port = int(os.environ.get("GRPC_PORT", "50051"))
    max_workers = int(os.environ.get("GRPC_MAX_WORKERS", "10"))
    max_message_bytes = _configured_max_message_bytes()

    if not 1 <= port <= 65535 or max_workers < 1:
        raise ValueError("Invalid gRPC port or worker count")
    tls_credentials = _configured_tls_credentials()
    db_factory = _get_db_pool()
    executor = None
    try:
        executor = futures.ThreadPoolExecutor(max_workers=max_workers)
        _serve_transport(
            db_factory,
            executor,
            port,
            max_workers,
            max_message_bytes,
            tls_credentials=tls_credentials,
        )
    finally:
        try:
            db_factory.close()
        finally:
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=True)


def _serve_transport(
    db_factory, executor, port, max_workers, max_message_bytes=None, tls_credentials=None
):
    server = None
    previous_signals = {}
    stopping = False
    try:
        server, service_names = _build_server(
            db_factory, executor, max_message_bytes=max_message_bytes
        )

        if tls_credentials is not None:
            bound_port = server.add_secure_port(f"[::]:{port}", tls_credentials)
            logger.info("gRPC server started on port %d with TLS (workers=%d)", port, max_workers)
        else:
            logger.warning("gRPC TLS not configured (GRPC_TLS_CERT/GRPC_TLS_KEY not set) — using insecure port")
            bound_port = server.add_insecure_port(f"[::]:{port}")
        if not bound_port:
            raise RuntimeError("gRPC port binding failed")
        server.start()
        if tls_credentials is not None:
            logger.info("gRPC server started on port %d with TLS (workers=%d)", port, max_workers)
        else:
            logger.info("gRPC server started on port %d INSECURE (workers=%d)", port, max_workers)
        logger.info("Registered services: %s", ", ".join(service_names))

        def shutdown(signum, frame):
            nonlocal stopping
            logger.info("Shutting down gRPC server...")
            server.stop(grace=0 if stopping else 30)
            stopping = True

        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_signals[signum] = signal.signal(signum, shutdown)
        server.wait_for_termination()
    finally:
        for signum, previous in previous_signals.items():
            signal.signal(signum, previous)
        if server is not None:
            server.stop(grace=0).wait(timeout=5)


def _build_server(db_factory, executor, max_message_bytes=None):
    """Create the configured server and register its optional service adapters."""
    if max_message_bytes is None:
        max_message_bytes = _configured_max_message_bytes()
    if (
        isinstance(max_message_bytes, bool)
        or not isinstance(max_message_bytes, int)
        or not MIN_MAX_MESSAGE_BYTES <= max_message_bytes <= MAX_MAX_MESSAGE_BYTES
    ):
        raise ValueError("max_message_bytes is outside the supported range")

    auth_interceptor = APIKeyInterceptor(db_factory)
    logging_interceptor = LoggingInterceptor()
    server = grpc.server(
        executor,
        interceptors=[logging_interceptor, auth_interceptor],
        options=[
            ("grpc.max_receive_message_length", max_message_bytes),
            ("grpc.max_send_message_length", max_message_bytes),
            ("grpc.keepalive_time_ms", 30000),
            ("grpc.keepalive_timeout_ms", 10000),
            ("grpc.keepalive_permit_without_calls", True),
            ("grpc.max_connection_age_ms", 3600000),
            ("grpc.max_connection_age_grace_ms", 30000),
        ],
    )

    health_servicer = HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    service_names = (
        reflection.SERVICE_NAME,
        "grpc.health.v1.Health",
    )

    try:
        from services.grpc.credit_class_service import EcocreditServiceServicer
        from services.grpc.ecocredit.v1 import service_pb2_grpc as ecocredit_pb2_grpc

        ecocredit_servicer = EcocreditServiceServicer(db_factory)
        ecocredit_pb2_grpc.add_EcocreditServiceServicer_to_server(ecocredit_servicer, server)
        service_names = service_names + ("ecocredit.v1.EcocreditService",)
    except ImportError as e:
        logger.warning(
            "Ecocredit service not available (%s)", safe_exception_class(e)
        )

    try:
        from services.grpc.data.v1 import service_pb2_grpc as data_pb2_grpc
        from services.grpc.data_service import DataServiceServicer

        data_servicer = DataServiceServicer(db_factory)
        data_pb2_grpc.add_DataServiceServicer_to_server(data_servicer, server)
        service_names = service_names + ("data.v1.DataService",)
    except ImportError as e:
        logger.warning("Data service not available (%s)", safe_exception_class(e))

    reflection.enable_server_reflection(service_names, server)
    return server, service_names


if __name__ == "__main__":
    serve()
