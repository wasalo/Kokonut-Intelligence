"""gRPC server entry point for Kokonut Intelligence."""

from __future__ import annotations

import os
import signal
import sys
from concurrent import futures

import grpc
from grpc_health.v1 import health_pb2_grpc
from grpc_reflection.v1alpha import reflection

from services.common.logging import get_logger
from services.grpc.auth import APIKeyInterceptor
from services.grpc.interceptors import LoggingInterceptor
from services.grpc.health import HealthServicer

logger = get_logger("grpc.server")


def _get_db_pool():
    import psycopg2
    from psycopg2 import pool
    from services.common.db import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD

    min_conn = int(os.environ.get("GRPC_DB_MIN_CONN", "2"))
    max_conn = int(os.environ.get("GRPC_DB_MAX_CONN", "20"))

    connection_pool = pool.ThreadedConnectionPool(
        minconn=min_conn,
        maxconn=max_conn,
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )

    def factory():
        return connection_pool.getconn()

    def release(conn):
        connection_pool.putconn(conn)

    factory.release = release
    return factory


def serve():
    port = int(os.environ.get("GRPC_PORT", "50051"))
    max_workers = int(os.environ.get("GRPC_MAX_WORKERS", "10"))

    db_factory = _get_db_pool()

    auth_interceptor = APIKeyInterceptor(db_factory)
    logging_interceptor = LoggingInterceptor()

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        interceptors=[logging_interceptor, auth_interceptor],
    )

    # Register health service
    health_servicer = HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    # Register reflection
    service_names = (
        reflection.SERVICE_NAME,
        "grpc.health.v1.Health",
    )

    # Import and register ecocredit service
    try:
        from services.grpc.credit_class_service import EcocreditServiceServicer
        from services.grpc.ecocredit.v1 import service_pb2_grpc as ecocredit_pb2_grpc
        ecocredit_servicer = EcocreditServiceServicer(db_factory)
        ecocredit_pb2_grpc.add_EcocreditServiceServicer_to_server(ecocredit_servicer, server)
        service_names = service_names + ("ecocredit.v1.EcocreditService",)
    except ImportError as e:
        logger.warning("Ecocredit service not available: %s", e)

    # Import and register data service
    try:
        from services.grpc.data_service import DataServiceServicer
        from services.grpc.data.v1 import service_pb2_grpc as data_pb2_grpc
        data_servicer = DataServiceServicer(db_factory)
        data_pb2_grpc.add_DataServiceServicer_to_server(data_servicer, server)
        service_names = service_names + ("data.v1.DataService",)
    except ImportError as e:
        logger.warning("Data service not available: %s", e)

    reflection.enable_server_reflection(service_names, server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()

    logger.info("gRPC server started on port %d (workers=%d)", port, max_workers)
    logger.info("Registered services: %s", ", ".join(service_names))

    def _shutdown(signum, frame):
        logger.info("Shutting down gRPC server...")
        server.stop(grace=30)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    server.wait_for_termination()


if __name__ == "__main__":
    serve()
