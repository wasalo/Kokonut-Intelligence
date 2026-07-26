"""CLI for gRPC server."""

from __future__ import annotations

import argparse
import sys


def cmd_serve(args):
    from services.grpc.server import serve
    serve()


def cmd_health(args):
    import grpc
    from grpc_health.v1 import health_pb2, health_pb2_grpc

    target = args.target or "localhost:50051"
    channel = grpc.insecure_channel(target)
    stub = health_pb2_grpc.HealthStub(channel)
    try:
        response = stub.Check(health_pb2.HealthCheckRequest(), timeout=5)
        if response.status != health_pb2.HealthCheckResponse.SERVING:
            print(f"Health check returned non-serving status: {response.status}")
            sys.exit(1)
        print(f"Status: {response.status}")
    except grpc.RpcError as e:
        print(f"Health check failed: {e}")
        sys.exit(1)
    finally:
        channel.close()


def main():
    parser = argparse.ArgumentParser(description="Kokonut gRPC Server")
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="Start gRPC server")
    p_serve.set_defaults(func=cmd_serve)

    p_health = sub.add_parser("health", help="Check gRPC server health")
    p_health.add_argument("--target", default=None, help="gRPC server target (default: localhost:50051)")
    p_health.set_defaults(func=cmd_health)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
